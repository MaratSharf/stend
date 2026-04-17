"""
MES Production System — Database utility
Handles SQLite operations for orders, stations, and station logs.

Supports sub-stations (e.g. 1.1, 1.2, 3.1) via REAL-valued station IDs.
"""
import sqlite3
import math
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

            # ── Migration: Add role_permissions table ─────────────
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='role_permissions'")
            if not cursor.fetchone():
                self.logger.info("Migration: creating role_permissions table")
                cursor.execute('''
                    CREATE TABLE role_permissions (
                        role TEXT NOT NULL,
                        permission TEXT NOT NULL,
                        PRIMARY KEY (role, permission)
                    )
                ''')
                # Insert default permissions
                from utils.permissions import DEFAULT_ROLE_PERMISSIONS
                for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
                    for perm in perms:
                        cursor.execute(
                            'INSERT INTO role_permissions (role, permission) VALUES (?, ?)',
                            (role, perm)
                        )

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
            # ── Normal table creation (always runs first) ─────────────
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
                    completed_subs TEXT DEFAULT '',
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

            # ── Migration: add completed_subs column (after table exists) ──
            cursor.execute("PRAGMA table_info(orders)")
            col_names = [col['name'] for col in cursor.fetchall()]
            if 'completed_subs' not in col_names:
                self.logger.info("Migration: adding completed_subs column to orders")
                cursor.execute("ALTER TABLE orders ADD COLUMN completed_subs TEXT DEFAULT ''")

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

    def _sub_stations_of(self, main_id: float) -> List[float]:
        """Get sub-station IDs for a main station (e.g. 1.1, 1.2 for main 1.0)."""
        ids = self._station_ids_sorted()
        return [sid for sid in ids if math.floor(sid) == int(main_id) and sid != float(int(main_id))]

    def complete_sub_station(self, order_id: int, sub_station_id: float) -> Dict[str, Any]:
        """Mark a sub-station as completed for an order."""
        conn = self.get_connection()
        try:
            order = self.get_order(order_id)
            if not order or order['status'] != 'production':
                return {'success': False, 'message': 'Order not in production'}

            # Verify the order is at the parent station
            parent = float(int(sub_station_id))
            if order['current_station'] != parent:
                return {'success': False, 'message': 'Order is not at the parent station'}

            # Get current completed_subs
            completed = set()
            if order.get('completed_subs'):
                completed = set(float(x) for x in order['completed_subs'].split(',') if x.strip())

            if sub_station_id in completed:
                return {'success': False, 'message': 'Sub-station already completed'}

            completed.add(sub_station_id)
            completed_str = ','.join(str(s) for s in sorted(completed))

            cursor = conn.cursor()
            cursor.execute('''
                UPDATE orders SET completed_subs = ? WHERE id = ?
            ''', (completed_str, order_id))

            # Log the completion
            cursor.execute('''
                INSERT INTO station_log (order_id, station_id, entered_at, exited_at, result)
                VALUES (?, ?, ?, ?, 'SUB_COMPLETED')
            ''', (order_id, sub_station_id, datetime.now().isoformat(), datetime.now().isoformat()))

            conn.commit()
            self.logger.info(f"Order {order_id} completed sub-station {sub_station_id}")
            return {'success': True, 'message': f'Sub-station {sub_station_id} completed'}
        except Exception as e:
            self.logger.error(f"complete_sub_station({order_id}, {sub_station_id}) failed: {e}", exc_info=True)
            conn.rollback()
            return {'success': False, 'message': str(e)}
        finally:
            conn.close()

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
                    'completed_subs': '',
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
                SET status = 'production', current_station = ?, started_at = ?, completed_subs = ''
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

    def move_order(self, order_id: int) -> Dict[str, Any]:
        """
        Move order to the next station.
        If the current main station has sub-stations, all must be completed first.
        Returns dict with success bool and optional message.
        """
        conn = self.get_connection()
        try:
            order = self.get_order(order_id)
            if not order or order['status'] != 'production':
                return {'success': False, 'message': 'Order not in production'}

            current_station = order['current_station']
            if current_station is None:
                return {'success': False, 'message': 'Order has no current station'}

            # If on a main station that has sub-stations, check completion
            if current_station == math.floor(current_station):
                subs = self._sub_stations_of(current_station)
                if subs:
                    completed = set()
                    if order.get('completed_subs'):
                        completed = set(float(x) for x in order['completed_subs'].split(',') if x.strip())
                    pending = [s for s in subs if s not in completed]
                    if pending:
                        pending_str = ', '.join(str(s) for s in pending)
                        return {'success': False, 'message': f'Сначала завершите подстанции: {pending_str}'}
                    # All subs completed — skip to next main station
                    all_ids = self._station_ids_sorted()
                    # Find the next station with integer ID (main station)
                    current_int = int(current_station)
                    for sid in all_ids:
                        if sid > current_station and sid == math.floor(sid):
                            next_station = sid
                            break
                    else:
                        next_station = None
                else:
                    next_station = self._next_station_id(current_station)
            else:
                # On a sub-station — move to next station in sequence
                next_station = self._next_station_id(current_station)

            if next_station is None:
                return {'success': False, 'message': 'Order is already at the last station'}

            cursor = conn.cursor()

            # If moving from a main station with completed subs to next main, clear completed_subs
            is_main_with_subs = (current_station == math.floor(current_station) and
                                 self._sub_stations_of(current_station) and
                                 order.get('completed_subs'))
            if is_main_with_subs:
                exited_at = datetime.now().isoformat()
                cursor.execute('''
                    UPDATE station_log
                    SET exited_at = ?, result = 'OK'
                    WHERE order_id = ? AND station_id = ? AND exited_at IS NULL
                ''', (exited_at, order_id, current_station))
                cursor.execute('UPDATE orders SET current_station = ?, completed_subs = ? WHERE id = ?', (next_station, '', order_id))
            else:
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
            return {'success': True, 'message': 'Order moved successfully'}
        except Exception as e:
            self.logger.error(f"move_order({order_id}) failed: {e}", exc_info=True)
            conn.rollback()
            return {'success': False, 'message': f'Error: {str(e)}'}
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
