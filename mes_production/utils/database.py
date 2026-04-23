"""
MES Production System — Database utility
PostgreSQL backend.

Handles operations for orders, stations, and station logs.
Supports sub-stations (e.g. 1.1, 1.2, 3.1) via REAL-valued station IDs.
"""
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
        config: a dict with PostgreSQL DB config containing:
            engine: 'postgresql'
            host, port, name, user, password
        """
        self.logger = logger or logging.getLogger('mes_db')

        if isinstance(config, str):
            raise RuntimeError("SQLite is no longer supported. Please use PostgreSQL configuration.")
        
        self.engine = config.get('engine', 'postgresql')
        if self.engine != 'postgresql':
            raise RuntimeError("Only PostgreSQL engine is supported")
            
        if not HAS_PSYCOPG2:
            raise RuntimeError("psycopg2-binary is required for PostgreSQL support")
        self.pg_config = config

        self.init_db()

    # ── Connection helpers ─────────────────────────────────────

    def get_connection(self):
        conn = psycopg2.connect(
            host=self.pg_config['host'],
            port=self.pg_config['port'],
            dbname=self.pg_config['name'],
            user=self.pg_config['user'],
            password=self.pg_config['password']
        )
        return conn

    def _cursor(self, conn):
        return conn.cursor(cursor_factory=RealDictCursor)

    def _table_exists(self, cursor, table_name: str) -> bool:
        cursor.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (table_name,)
        )
        return cursor.fetchone() is not None

    def _column_exists(self, cursor, table_name: str, column_name: str) -> bool:
        cursor.execute(
            """SELECT 1 FROM information_schema.columns
               WHERE table_name = %s AND column_name = %s""",
            (table_name, column_name)
        )
        return cursor.fetchone() is not None

    def _lastrowid(self, cursor) -> int:
        return cursor.fetchone()['id']

    def _placeholder(self, n: int = 1) -> Union[str, tuple]:
        """Return SQL placeholders. For single value returns string, for multiple returns tuple string."""
        return '%s'

    def _insert_or_ignore(self, table: str, columns: List[str], values: tuple) -> str:
        """Build INSERT OR IGNORE / ON CONFLICT query."""
        cols = ', '.join(columns)
        ph = ', '.join(['%s'] * len(columns))
        return f"INSERT INTO {table} ({cols}) VALUES ({ph}) ON CONFLICT DO NOTHING"

    # ── Table init ──────────────────────────────────────────────

    def init_db(self):
        """Initialize database tables."""
        conn = self.get_connection()
        try:
            cursor = self._cursor(conn)

            # ── Migration: Add role_permissions table ─────────────
            if not self._table_exists(cursor, 'role_permissions'):
                self.logger.info("Migration: creating role_permissions table")
                cursor.execute('''
                    CREATE TABLE role_permissions (
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS qr_scans (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER NOT NULL REFERENCES orders(id),
                    station_id REAL NOT NULL DEFAULT 6.1,
                    qr_data TEXT NOT NULL,
                    result TEXT DEFAULT 'OK',
                    scanned_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
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

    def _get_target_station(self, target_main_id: float) -> float:
        """Get the actual target station ID.
        If target_main_id has sub-stations, return the first sub-station.
        Otherwise, return target_main_id itself.
        This ensures orders always go to sub-stations when available."""
        subs = self._sub_stations_of(target_main_id)
        if subs:
            return min(subs)  # First sub-station
        return target_main_id

    def move_order_to_station(self, order_id: int, target_station: float) -> Dict[str, Any]:
        """Move order to a specific station.
        If target_station is a main station with sub-stations, 
        automatically redirect to the first sub-station.
        
        This method ensures orders always go to sub-stations when available,
        regardless of whether the target is specified as main or sub station ID."""
        conn = self.get_connection()
        try:
            order = self.get_order(order_id)
            if not order or order['status'] != 'production':
                return {'success': False, 'message': 'Order not in production'}

            current_station = order['current_station']
            
            # Get the actual target station (with sub-station if available)
            actual_target = self._get_target_station(target_station)
            
            # If target is a sub-station, get its parent for comparison
            target_parent = float(int(target_station))
            
            # Check if order is already at the target (or its sub-station)
            if current_station == actual_target:
                return {'success': True, 'message': f'Order already at station {actual_target}'}
            
            # If moving to a sub-station, verify order is at the parent station
            if actual_target != target_station and current_station != target_parent:
                # Order is not at parent, but check if it's at a sibling sub-station
                if math.floor(current_station) == target_parent:
                    pass  # Allow moving between sibling sub-stations
                else:
                    return {'success': False, 'message': f'Order is not at parent station {target_parent}'}

            cursor = self._cursor(conn)
            ph = self._placeholder()
            exited_at = datetime.now().isoformat()

            # Close current station log entry if exists
            cursor.execute(f'''
                UPDATE station_log
                SET exited_at = {ph}, result = 'OK'
                WHERE order_id = {ph} AND station_id = {ph} AND exited_at IS NULL
            ''', (exited_at, order_id, current_station))

            # Update order station
            cursor.execute(f'''
                UPDATE orders SET current_station = {ph} WHERE id = {ph}
            ''', (actual_target, order_id))

            # Log entry to new station
            entered_at = datetime.now().isoformat()
            cursor.execute(f'''
                INSERT INTO station_log (order_id, station_id, entered_at, result)
                VALUES ({ph}, {ph}, {ph}, 'OK')
            ''', (order_id, actual_target, entered_at))

            conn.commit()
            if actual_target != target_station:
                self.logger.info(f"Order {order_id} moved from {current_station} to {actual_target} (redirected from {target_station})")
                return {'success': True, 'message': f'Order moved to sub-station {actual_target}', 'redirected': True, 'actual_station': actual_target}
            else:
                self.logger.info(f"Order {order_id} moved from {current_station} to {actual_target}")
                return {'success': True, 'message': f'Order moved to station {actual_target}'}
        except Exception as e:
            self.logger.error(f"move_order_to_station({order_id}, {target_station}) failed: {e}", exc_info=True)
            conn.rollback()
            return {'success': False, 'message': f'Error: {str(e)}'}
        finally:
            conn.close()

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

                cursor.execute(f'''
                    INSERT INTO orders (batch, order_number, product_code, color, quantity, status, current_station, created_at)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, 'buffer', NULL, {ph})
                    RETURNING id
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
        """Launch an order to the first station (or first sub-station if exists)."""
        conn = self.get_connection()
        try:
            all_ids = self._station_ids_sorted()
            if not all_ids:
                return False
            
            first_id = all_ids[0]
            # If first station is a main station with subs, use first sub-station
            if first_id == int(first_id):
                subs = self._sub_stations_of(first_id)
                if subs:
                    first_id = min(subs)  # First sub-station
            
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
        """Move order to the next station (or first sub-station if exists)."""
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

            # If next station is a main station with subs, move to first sub-station instead
            if next_station == int(next_station):
                next_subs = self._sub_stations_of(next_station)
                if next_subs:
                    next_station = min(next_subs)  # First sub-station

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
        """Get all stations with their current orders.
        For all stations in a group (main station and its sub-stations), 
        includes orders from the entire group (main station + all sub-stations).
        This ensures orders are visible on all related stations."""
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
                station_id = station['id']
                # Get the main station ID (integer part)
                main_id = int(station_id)
                
                # Find all sub-stations for this main station
                cursor.execute('''
                    SELECT s.id FROM stations s 
                    WHERE s.id > %s AND s.id < %s
                    ORDER BY s.id
                ''', (float(main_id), float(main_id + 1)))
                sub_ids = [row['id'] for row in cursor.fetchall()]
                
                # Build list of all station IDs in this group (main + all subs)
                ids = [float(main_id)] + sub_ids
                
                # Get orders from all stations in the group
                if len(ids) > 1:
                    placeholders = ','.join(['%s'] * len(ids))
                    cursor.execute(f'''
                        SELECT id, order_number, product_code, color, quantity, batch
                        FROM orders
                        WHERE current_station IN ({placeholders}) AND status = 'production'
                        ORDER BY id
                    ''', ids)
                else:
                    # Only main station exists, no sub-stations
                    cursor.execute(f'''
                        SELECT id, order_number, product_code, color, quantity, batch
                        FROM orders
                        WHERE current_station = {ph} AND status = 'production'
                        ORDER BY id
                    ''', (float(main_id),))
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

    # ── QR Scan operations ──────────────────────────────────────

    def save_qr_scan(self, order_id: int, qr_data: str, result: str = 'OK', station_id: float = 6.1) -> Dict[str, Any]:
        """Save a QR scan result to the database."""
        conn = self.get_connection()
        try:
            order = self.get_order(order_id)
            if not order:
                return {'success': False, 'message': 'Order not found'}

            if order['status'] != 'production':
                return {'success': False, 'message': 'Order is not in production'}

            if order['current_station'] != station_id:
                return {'success': False, 'message': f'Order is not at station {station_id}'}

            now = datetime.now().isoformat()
            cursor = self._cursor(conn)
            ph = self._placeholder()

            if self.engine == 'postgresql':
                cursor.execute(f'''
                    INSERT INTO qr_scans (order_id, station_id, qr_data, result, scanned_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (order_id, station_id, qr_data, result, now, now))
                scan_id = cursor.fetchone()['id']
            else:
                cursor.execute('''
                    INSERT INTO qr_scans (order_id, station_id, qr_data, result, scanned_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (order_id, station_id, qr_data, result, now, now))
                scan_id = cursor.lastrowid

            conn.commit()
            self.logger.info(f"QR scan saved: order_id={order_id}, qr_data={qr_data}, scan_id={scan_id}")
            return {'success': True, 'scan_id': scan_id, 'message': 'QR scan saved successfully'}
        except Exception as e:
            self.logger.error(f"save_qr_scan({order_id}, {qr_data}) failed: {e}", exc_info=True)
            conn.rollback()
            return {'success': False, 'message': str(e)}
        finally:
            conn.close()

    def get_qr_scans(self, order_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get QR scans, optionally filtered by order_id."""
        conn = self.get_connection()
        try:
            cursor = self._cursor(conn)
            ph = self._placeholder()

            if order_id:
                cursor.execute(f'''
                    SELECT * FROM qr_scans WHERE order_id = {ph}
                    ORDER BY scanned_at DESC
                    LIMIT {ph}
                ''', (order_id, limit))
            else:
                cursor.execute(f'''
                    SELECT * FROM qr_scans
                    ORDER BY scanned_at DESC
                    LIMIT {ph}
                ''', (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_qr_scan(self, scan_id: int) -> Optional[Dict[str, Any]]:
        """Get a single QR scan by ID."""
        conn = self.get_connection()
        try:
            cursor = self._cursor(conn)
            ph = self._placeholder()
            cursor.execute(f'SELECT * FROM qr_scans WHERE id = {ph}', (scan_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()