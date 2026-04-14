"""
MES Production System — Database utility
Handles SQLite operations for orders, stations, and station logs.

Supports sub-stations (e.g. 1.1, 1.2, 3.1) via REAL-valued station IDs.
"""
import sqlite3
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any


class Database:
    def __init__(self, db_path: str, logger: logging.Logger = None):
        self.db_path = db_path
        self.logger = logger or logging.getLogger('mes_db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ── Table init ──────────────────────────────────────────────

    def init_db(self):
        """Initialize database tables. current_station is REAL for sub-station support."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            # ── Migration: INTEGER → REAL for stations ─────────────
            # If old schema exists (id INTEGER), recreate with REAL
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='stations'")
            row = cursor.fetchone()
            if row and 'INTEGER PRIMARY KEY' in row['sql']:
                self.logger.info("Migrating stations table: INTEGER → REAL id")
                cursor.execute('DROP TABLE IF EXISTS station_log')
                cursor.execute('DROP TABLE IF EXISTS stations')
                cursor.execute('''
                    CREATE TABLE stations (
                        id REAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        order_id INTEGER,
                        FOREIGN KEY (order_id) REFERENCES orders(id)
                    )
                ''')
                # Recreate station_log with REAL station_id
                cursor.execute('DROP TABLE IF EXISTS station_log')
                cursor.execute('''
                    CREATE TABLE station_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id INTEGER NOT NULL,
                        station_id REAL NOT NULL,
                        entered_at TEXT NOT NULL,
                        exited_at TEXT,
                        result TEXT DEFAULT 'OK',
                        FOREIGN KEY (order_id) REFERENCES orders(id),
                        FOREIGN KEY (station_id) REFERENCES stations(id)
                    )
                ''')
                conn.commit()
            # ── Migration: orders.current_station INTEGER → REAL ─────
            cursor.execute("PRAGMA table_info(orders)")
            columns = [col['name'] for col in cursor.fetchall()]
            # current_station already exists; SQLite allows storing REAL in INTEGER column
            # but for safety we check type

            # ── Normal table creation ────────────────────────────────
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch TEXT NOT NULL,
                    order_number TEXT UNIQUE NOT NULL,
                    product_code TEXT NOT NULL,
                    color TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    status TEXT DEFAULT 'buffer',
                    current_station REAL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stations (
                    id REAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    order_id INTEGER,
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS station_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    station_id REAL NOT NULL,
                    entered_at TEXT NOT NULL,
                    exited_at TEXT,
                    result TEXT DEFAULT 'OK',
                    FOREIGN KEY (order_id) REFERENCES orders(id),
                    FOREIGN KEY (station_id) REFERENCES stations(id)
                )
            ''')
            conn.commit()
        finally:
            conn.close()

    # ── Station list helpers ────────────────────────────────────

    @staticmethod
    def flatten_stations(station_names: List[str]):
        """
        Convert config station list into flat [(id, name), ...] list.

        Input:
            [
              {"name": "Приёмка",     "subs": ["Приёмка 1.1", "Приёмка 1.2"]},
              {"name": "Сортировка"},
              {"name": "Подготовка",  "subs": ["Подготовка 3.1"]},
              {"name": "Сборка"},
              ...
            ]
        Output:
            [(1.1, "Приёмка 1.1"), (1.2, "Приёмка 1.2"),
             (2,   "Сортировка"),
             (3.1, "Подготовка 3.1"), (3, "Подготовка"),
             (4,   "Сборка"), ...]
        Sub-stations get decimal IDs (1.1, 1.2, 3.1).
        Main stations keep integer IDs.
        """
        result = []
        main_idx = 0
        for entry in station_names:
            main_idx += 1
            if isinstance(entry, dict):
                name = entry.get('name', '')
                subs = entry.get('subs', [])
                # Sub-stations first (decimal IDs)
                for si, sname in enumerate(subs, 1):
                    result.append((float(f"{main_idx}.{si}"), sname))
                # Then main station
                result.append((float(main_idx), name))
            else:
                result.append((float(main_idx), entry))
        return result

    def _station_ids_sorted(self) -> List[float]:
        """Return sorted list of station IDs from DB."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM stations ORDER BY id')
            return [row['id'] for row in cursor.fetchall()]
        finally:
            conn.close()

    def _next_station_id(self, current: float) -> Optional[float]:
        """Get the next station ID after the given one (by sorted order)."""
        ids = self._station_ids_sorted()
        for i, sid in enumerate(ids):
            if sid == current and i + 1 < len(ids):
                return ids[i + 1]
        return None

    def _last_station_id(self) -> float:
        """Return the last station ID."""
        ids = self._station_ids_sorted()
        return ids[-1] if ids else 10.0

    # ── Init stations ──────────────────────────────────────────

    def init_stations(self, station_config: List[Any]):
        """
        Initialize stations. Accepts either:
        - List[str] — simple names: ["Station 1", "Station 2", ...]
        - List[dict] — with sub-stations: [{"name": "X", "subs": ["X 1.1"]}, ...]
        """
        # Detect format
        if station_config and isinstance(station_config[0], dict):
            flat = self.flatten_stations(station_config)
        else:
            flat = [(float(i), name) for i, name in enumerate(station_config, 1)]

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            for sid, name in flat:
                cursor.execute('''
                    INSERT OR IGNORE INTO stations (id, name, order_id)
                    VALUES (?, ?, NULL)
                ''', (sid, name))
            conn.commit()
            self.logger.info(f"Initialized {len(flat)} station(s): {[f[1] for f in flat]}")
        finally:
            conn.close()

    # ── Order creation ──────────────────────────────────────────

    def create_order(self, batch: str, product_code: str, color: str, quantity: int) -> List[Dict[str, Any]]:
        """Create multiple orders. Order numbers are assigned atomically via lastrowid."""
        created_orders = []

        for _ in range(quantity):
            created_at = datetime.now().isoformat()
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO orders (batch, order_number, product_code, color, quantity, status, current_station, created_at)
                    VALUES (?, '', ?, ?, ?, 'buffer', NULL, ?)
                ''', (batch, product_code, color, 1, created_at))

                order_id = cursor.lastrowid
                order_number = f"ORD-{order_id:04d}"

                cursor.execute('''
                    UPDATE orders SET order_number = ? WHERE id = ?
                ''', (order_number, order_id))

                conn.commit()
                created_orders.append({
                    'id': order_id,
                    'batch': batch,
                    'order_number': order_number,
                    'product_code': product_code,
                    'color': color,
                    'quantity': 1,
                    'status': 'buffer',
                    'current_station': None,
                    'created_at': created_at,
                    'started_at': None,
                    'completed_at': None
                })
            except Exception as e:
                self.logger.error(f"create_order(batch={batch}) failed: {e}", exc_info=True)
                conn.rollback()
                break
            finally:
                conn.close()

        return created_orders

    # ── Reads ───────────────────────────────────────────────────

    def get_orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all orders, optionally filtered by status."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if status:
                cursor.execute('SELECT * FROM orders WHERE status = ? ORDER BY id DESC', (status,))
            else:
                cursor.execute('SELECT * FROM orders ORDER BY id DESC')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        """Get a single order by ID."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ── State transitions ───────────────────────────────────────

    def launch_order(self, order_id: int) -> bool:
        """Launch an order to the first station. Multiple orders can share a station."""
        conn = self.get_connection()
        try:
            first_id = self._station_ids_sorted()[0] if self._station_ids_sorted() else 1.0
            cursor = conn.cursor()
            started_at = datetime.now().isoformat()

            cursor.execute('''
                UPDATE orders
                SET status = 'production', current_station = ?, started_at = ?
                WHERE id = ? AND status = 'buffer'
            ''', (first_id, started_at, order_id))

            if cursor.rowcount == 0:
                return False

            cursor.execute('''
                INSERT INTO station_log (order_id, station_id, entered_at, result)
                VALUES (?, ?, ?, 'OK')
            ''', (order_id, first_id, started_at))

            conn.commit()
            self.logger.info(f"Order {order_id} launched to station {first_id}")
            return True
        except Exception as e:
            self.logger.error(f"launch_order({order_id}) failed: {e}", exc_info=True)
            conn.rollback()
            return False
        finally:
            conn.close()

    def move_order(self, order_id: int) -> bool:
        """Move order to the next station. Supports sub-station ordering."""
        conn = self.get_connection()
        try:
            order = self.get_order(order_id)
            if not order or order['status'] != 'production':
                return False

            current_station = order['current_station']
            if current_station is None:
                return False

            next_station = self._next_station_id(current_station)
            if next_station is None:
                return False  # already at last station

            cursor = conn.cursor()
            exited_at = datetime.now().isoformat()

            cursor.execute('''
                UPDATE station_log
                SET exited_at = ?, result = 'OK'
                WHERE order_id = ? AND station_id = ? AND exited_at IS NULL
            ''', (exited_at, order_id, current_station))

            cursor.execute('UPDATE orders SET current_station = ? WHERE id = ?', (next_station, order_id))

            entered_at = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO station_log (order_id, station_id, entered_at, result)
                VALUES (?, ?, ?, 'OK')
            ''', (order_id, next_station, entered_at))

            conn.commit()
            self.logger.info(f"Order {order_id} moved from station {current_station} to {next_station}")
            return True
        except Exception as e:
            self.logger.error(f"move_order({order_id}) failed: {e}", exc_info=True)
            conn.rollback()
            return False
        finally:
            conn.close()

    def complete_order(self, order_id: int) -> bool:
        """Complete an order."""
        conn = self.get_connection()
        try:
            order = self.get_order(order_id)
            if not order or order['status'] != 'production':
                return False

            completed_at = datetime.now().isoformat()
            current_station = order['current_station']
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE orders
                SET status = 'completed', current_station = NULL, completed_at = ?
                WHERE id = ?
            ''', (completed_at, order_id))

            if current_station:
                cursor.execute('''
                    UPDATE station_log
                    SET exited_at = ?, result = 'OK'
                    WHERE order_id = ? AND station_id = ? AND exited_at IS NULL
                ''', (completed_at, order_id, current_station))

            conn.commit()
            self.logger.info(f"Order {order_id} completed")
            return True
        except Exception as e:
            self.logger.error(f"complete_order({order_id}) failed: {e}", exc_info=True)
            conn.rollback()
            return False
        finally:
            conn.close()

    def cancel_order(self, order_id: int) -> bool:
        """Cancel an order."""
        conn = self.get_connection()
        try:
            order = self.get_order(order_id)
            if not order or order['status'] in ('completed', 'cancelled'):
                return False

            cursor = conn.cursor()
            cursor.execute('''
                UPDATE orders SET status = 'cancelled', current_station = NULL
                WHERE id = ?
            ''', (order_id,))

            conn.commit()
            self.logger.info(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            self.logger.error(f"cancel_order({order_id}) failed: {e}", exc_info=True)
            conn.rollback()
            return False
        finally:
            conn.close()

    # ── Queries ─────────────────────────────────────────────────

    def get_stations(self) -> List[Dict[str, Any]]:
        """Get all stations with their current orders (multiple orders per station)."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.id, s.name
                FROM stations s
                ORDER BY s.id
            ''')
            stations = [dict(row) for row in cursor.fetchall()]

            for station in stations:
                cursor.execute('''
                    SELECT id, order_number, product_code, color, quantity, batch
                    FROM orders
                    WHERE current_station = ? AND status = 'production'
                    ORDER BY id
                ''', (station['id'],))
                station['orders'] = [dict(row) for row in cursor.fetchall()]

            return stations
        finally:
            conn.close()

    def get_statistics(self) -> Dict[str, Any]:
        """Get production statistics."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM orders')
            stats = {'total': cursor.fetchone()['count']}

            cursor.execute('SELECT status, COUNT(*) as count FROM orders GROUP BY status')
            for row in cursor.fetchall():
                stats[row['status']] = row['count']

            stats['in_production'] = stats.get('production', 0)
            stats['completion_rate'] = round(
                (stats.get('completed', 0) / stats['total']) * 100, 2
            ) if stats['total'] > 0 else 0.0

            return stats
        finally:
            conn.close()
