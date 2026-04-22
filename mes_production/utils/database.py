"""
MES Production System — Database utility
Supports both SQLite and PostgreSQL backends.

Handles operations for orders, stations, and station logs.
Supports sub-stations (e.g. 1.1, 1.2, 3.1) via REAL-valued station IDs.
"""
import sqlite3
import math
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class Database:
    def __init__(self, config: Union[str, dict], logger: logging.Logger = None):
        """
        config: either a SQLite file path (str) or a dict with DB config.
        For PostgreSQL, config must contain:
            engine: 'postgresql'
            host, port, name, user, password
        For SQLite (legacy):
            path: 'data/mes.db'
        """
        self.logger = logger or logging.getLogger('mes_db')

        if isinstance(config, str):
            self.engine = 'sqlite'
            self.db_path = config
            os.makedirs(os.path.dirname(config) or '.', exist_ok=True)
        else:
            self.engine = config.get('engine', 'sqlite')
            if self.engine == 'postgresql':
                if not HAS_PSYCOPG2:
                    raise RuntimeError("psycopg2-binary is required for PostgreSQL support")
                self.pg_config = config
            else:
                self.db_path = config.get('path', 'data/mes.db')
                os.makedirs(os.path.dirname(self.db_path) or '.', exist_ok=True)

        self.init_db()

    # ── Connection helpers ─────────────────────────────────────

    def get_connection(self):
        if self.engine == 'postgresql':
            conn = psycopg2.connect(
                host=self.pg_config['host'],
                port=self.pg_config['port'],
                dbname=self.pg_config['name'],
                user=self.pg_config['user'],
                password=self.pg_config['password']
            )
            return conn
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn

    def _cursor(self, conn):
        if self.engine == 'postgresql':
            return conn.cursor(cursor_factory=RealDictCursor)
        return conn.cursor()

    def _table_exists(self, cursor, table_name: str) -> bool:
        if self.engine == 'postgresql':
            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (table_name,)
            )
        else:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
        return cursor.fetchone() is not None

    def _column_exists(self, cursor, table_name: str, column_name: str) -> bool:
        if self.engine == 'postgresql':
            cursor.execute(
                """SELECT 1 FROM information_schema.columns
                   WHERE table_name = %s AND column_name = %s""",
                (table_name, column_name)
            )
            return cursor.fetchone() is not None
        else:
            cursor.execute(f"PRAGMA table_info({table_name})")
            col_names = [row['name'] for row in cursor.fetchall()]
            return column_name in col_names

    def _lastrowid(self, cursor) -> int:
        if self.engine == 'postgresql':
            return cursor.fetchone()['id']
        return cursor.lastrowid

    def _placeholder(self, n: int = 1) -> Union[str, tuple]:
        """Return SQL placeholders. For single value returns string, for multiple returns tuple string."""
        if self.engine == 'postgresql':
            return '%s'
        return '?'

    def _insert_or_ignore(self, table: str, columns: List[str], values: tuple) -> str:
        """Build INSERT OR IGNORE / ON CONFLICT query."""
        cols = ', '.join(columns)
        if self.engine == 'postgresql':
            ph = ', '.join(['%s'] * len(columns))
            return f"INSERT INTO {table} ({cols}) VALUES ({ph}) ON CONFLICT DO NOTHING"
        else:
            ph = ', '.join(['?'] * len(columns))
            return f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({ph})"

    # ── Table init ──────────────────────────────────────────────

    def init_db(self):
        """Initialize database tables."""
        conn = self.get_connection()
        try:
            cursor = self._cursor(conn)

            # ── Migration: Add role_permissions table ─────────────
            if not self._table_exists(cursor, 'role_permissions'):
                self.logger.info("Migration: creating role_permissions table")
                if self.engine == 'postgresql':
                    cursor.execute('''
                        CREATE TABLE role_permissions (
                            role TEXT NOT NULL,
                            permission TEXT NOT NULL,
                            PRIMARY KEY (role, permission)
                        )
                    ''')
                else:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS role_permissions (
                            role TEXT NOT NULL,
                            permission TEXT NOT NULL,
                            PRIMARY KEY (role, permission)
                        )
                    ''')
                try:
                    from utils.permissions import DEFAULT_ROLE_PERMISSIONS
                    for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
                        for perm in perms:
                            cursor.execute(
                                self._insert_or_ignore('role_permissions', ['role', 'permission'], (role, perm)),
                                (role, perm)
                            )
                except ImportError:
                    pass

            # ── Normal table creation ─────────────────────────────
            if self.engine == 'postgresql':
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS orders (
                        id SERIAL PRIMARY KEY,
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
                        order_id INTEGER REFERENCES orders(id)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS station_log (
                        id SERIAL PRIMARY KEY,
                        order_id INTEGER NOT NULL REFERENCES orders(id),
                        station_id REAL NOT NULL REFERENCES stations(id),
                        entered_at TEXT NOT NULL,
                        exited_at TEXT,
                        result TEXT DEFAULT 'OK'
                    )
                ''')
            else:
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

            # ── Migration: add completed_subs column ──
            if not self._column_exists(cursor, 'orders', 'completed_subs'):
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
        """
        result = []
        main_idx = 0
        for entry in station_names:
            main_idx += 1
            if isinstance(entry, dict):
                name = entry.get('name', '')
                subs = entry.get('subs', [])
                for si, sname in enumerate(subs, 1):
                    result.append((float(f"{main_idx}.{si}"), sname))
                result.append((float(main_idx), name))
            else:
                result.append((float(main_idx), entry))
        return result

    def _station_ids_sorted(self) -> List[float]:
        """Return sorted list of station IDs from DB."""
        conn = self.get_connection()
        try:
            cursor = self._cursor(conn)
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
        """Get sub-station IDs for a main station."""
        ids = self._station_ids_sorted()
        return [sid for sid in ids if math.floor(sid) == int(main_id) and sid != float(int(main_id))]

    def complete_sub_station(self, order_id: int, sub_station_id: float) -> Dict[str, Any]:
        """Mark a sub-station as completed for an order."""
        conn = self.get_connection()
        try:
            order = self.get_order(order_id)
            if not order or order['status'] != 'production':
                return {'success': False, 'message': 'Order not in production'}

            parent = float(int(sub_station_id))
            if order['current_station'] != parent and order['current_station'] != sub_station_id:
                return {'success': False, 'message': 'Order is not at the parent station or sub-station'}

            completed = set()
            if order.get('completed_subs'):
                completed = set(float(x) for x in order['completed_subs'].split(',') if x.strip())

            if sub_station_id in completed:
                return {'success': False, 'message': 'Sub-station already completed'}

            completed.add(sub_station_id)
            completed_str = ','.join(str(s) for s in sorted(completed))

            cursor = self._cursor(conn)
            ph = self._placeholder()
            cursor.execute(f'''
                UPDATE orders SET completed_subs = {ph} WHERE id = {ph}
            ''', (completed_str, order_id))

            now = datetime.now().isoformat()
            cursor.execute(f'''
                INSERT INTO station_log (order_id, station_id, entered_at, exited_at, result)
                VALUES ({ph}, {ph}, {ph}, {ph}, 'SUB_COMPLETED')
            ''', (order_id, sub_station_id, now, now))

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
        - List[str] — simple names
        - List[dict] — with sub-stations
        """
        if station_config and isinstance(station_config[0], dict):
            flat = self.flatten_stations(station_config)
        else:
            flat = [(float(i), name) for i, name in enumerate(station_config, 1)]

        conn = self.get_connection()
        try:
            cursor = self._cursor(conn)
            for sid, name in flat:
                sql = self._insert_or_ignore('stations', ['id', 'name', 'order_id'], (sid, name, None))
                cursor.execute(sql, (sid, name, None))
            conn.commit()
            self.logger.info(f"Initialized {len(flat)} station(s): {[f[1] for f in flat]}")
        finally:
            conn.close()

    # ── Order creation ──────────────────────────────────────────

    def create_order(self, batch: str, product_code: str, color: str, quantity: int) -> List[Dict[str, Any]]:
        """Create multiple orders. Order numbers assigned atomically."""
        created_orders = []

        for _ in range(quantity):
            created_at = datetime.now().isoformat()
            conn = self.get_connection()
            try:
                cursor = self._cursor(conn)
                ph = self._placeholder()

                if self.engine == 'postgresql':
                    cursor.execute(f'''
                        INSERT INTO orders (batch, order_number, product_code, color, quantity, status, current_station, created_at)
                        VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, 'buffer', NULL, {ph})
                        RETURNING id
                    ''', (batch, '', product_code, color, 1, created_at))
                else:
                    cursor.execute(f'''
                        INSERT INTO orders (batch, order_number, product_code, color, quantity, status, current_station, created_at)
                        VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, 'buffer', NULL, {ph})
                    ''', (batch, '', product_code, color, 1, created_at))

                order_id = self._lastrowid(cursor)
                order_number = f"ORD-{order_id:04d}"

                cursor.execute(f'''
                    UPDATE orders SET order_number = {ph} WHERE id = {ph}
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
            cursor = self._cursor(conn)
            ph = self._placeholder()
            if status:
                cursor.execute(f'SELECT * FROM orders WHERE status = {ph} ORDER BY id DESC', (status,))
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
            cursor = self._cursor(conn)
            ph = self._placeholder()
            cursor.execute(f'SELECT * FROM orders WHERE id = {ph}', (order_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ── State transitions ───────────────────────────────────────

    def launch_order(self, order_id: int) -> bool:
        """Launch an order to the first station."""
        conn = self.get_connection()
        try:
            first_id = self._station_ids_sorted()[0] if self._station_ids_sorted() else 1.0
            cursor = self._cursor(conn)
            started_at = datetime.now().isoformat()
            ph = self._placeholder()

            cursor.execute(f'''
                UPDATE orders
                SET status = 'production', current_station = {ph}, started_at = {ph}, completed_subs = ''
                WHERE id = {ph} AND status = 'buffer'
            ''', (first_id, started_at, order_id))

            if cursor.rowcount == 0:
                return False

            cursor.execute(f'''
                INSERT INTO station_log (order_id, station_id, entered_at, result)
                VALUES ({ph}, {ph}, {ph}, 'OK')
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
        """Move order to the next station."""
        conn = self.get_connection()
        try:
            order = self.get_order(order_id)
            if not order or order['status'] != 'production':
                return {'success': False, 'message': 'Order not in production'}

            current_station = order['current_station']
            if current_station is None:
                return {'success': False, 'message': 'Order has no current station'}

            # Check sub-stations completion for main stations
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
                    all_ids = self._station_ids_sorted()
                    current_int = int(current_station)
                    next_station = None
                    for sid in all_ids:
                        if sid > current_station and sid == math.floor(sid):
                            next_station = sid
                            break
                else:
                    next_station = self._next_station_id(current_station)
            else:
                next_station = self._next_station_id(current_station)

            if next_station is None:
                return {'success': False, 'message': 'Order is already at the last station'}

            cursor = self._cursor(conn)
            ph = self._placeholder()
            exited_at = datetime.now().isoformat()

            is_main_with_subs = (current_station == math.floor(current_station) and
                                 self._sub_stations_of(current_station) and
                                 order.get('completed_subs'))
            if is_main_with_subs:
                cursor.execute(f'''
                    UPDATE station_log
                    SET exited_at = {ph}, result = 'OK'
                    WHERE order_id = {ph} AND station_id = {ph} AND exited_at IS NULL
                ''', (exited_at, order_id, current_station))
                cursor.execute(f'''
                    UPDATE orders SET current_station = {ph}, completed_subs = {ph} WHERE id = {ph}
                ''', (next_station, '', order_id))
            else:
                cursor.execute(f'''
                    UPDATE station_log
                    SET exited_at = {ph}, result = 'OK'
                    WHERE order_id = {ph} AND station_id = {ph} AND exited_at IS NULL
                ''', (exited_at, order_id, current_station))
                cursor.execute(f'''
                    UPDATE orders SET current_station = {ph} WHERE id = {ph}
                ''', (next_station, order_id))

            entered_at = datetime.now().isoformat()
            cursor.execute(f'''
                INSERT INTO station_log (order_id, station_id, entered_at, result)
                VALUES ({ph}, {ph}, {ph}, 'OK')
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
            cursor = self._cursor(conn)
            ph = self._placeholder()

            cursor.execute(f'''
                UPDATE orders
                SET status = 'completed', current_station = NULL, completed_at = {ph}
                WHERE id = {ph}
            ''', (completed_at, order_id))

            if current_station:
                cursor.execute(f'''
                    UPDATE station_log
                    SET exited_at = {ph}, result = 'OK'
                    WHERE order_id = {ph} AND station_id = {ph} AND exited_at IS NULL
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

            cursor = self._cursor(conn)
            ph = self._placeholder()
            cursor.execute(f'''
                UPDATE orders SET status = 'cancelled', current_station = NULL
                WHERE id = {ph}
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
        """Get all stations with their current orders."""
        conn = self.get_connection()
        try:
            cursor = self._cursor(conn)
            cursor.execute('''
                SELECT s.id, s.name
                FROM stations s
                ORDER BY s.id
            ''')
            stations = [dict(row) for row in cursor.fetchall()]

            ph = self._placeholder()
            for station in stations:
                cursor.execute(f'''
                    SELECT id, order_number, product_code, color, quantity, batch
                    FROM orders
                    WHERE current_station = {ph} AND status = 'production'
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
            cursor = self._cursor(conn)
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