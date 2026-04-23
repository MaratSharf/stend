"""
MES Production System — Unified DB Connection utility
Supports both SQLite and PostgreSQL backends with a common interface.
"""
import sqlite3
import math
from datetime import datetime
from typing import Optional, Union, List, Dict, Any

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


class DBConnection:
    """
    Unified database connection handler.
    Accepts either a SQLite path (str) or a PostgreSQL config dict.
    """

    def __init__(self, config: Union[str, dict]):
        if isinstance(config, str):
            self.engine = 'sqlite'
            self.db_path = config
        else:
            self.engine = config.get('engine', 'sqlite')
            if self.engine == 'postgresql':
                if not HAS_PSYCOPG2:
                    raise RuntimeError("psycopg2-binary is required for PostgreSQL support")
                self.pg_config = config
            else:
                self.db_path = config.get('path', 'data/mes.db')

    def get_connection(self):
        if self.engine == 'postgresql':
            return psycopg2.connect(
                host=self.pg_config['host'],
                port=self.pg_config['port'],
                dbname=self.pg_config['name'],
                user=self.pg_config['user'],
                password=self.pg_config['password']
            )
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def cursor(self, conn):
        if self.engine == 'postgresql':
            return conn.cursor(cursor_factory=RealDictCursor)
        return conn.cursor()

    def table_exists(self, conn, table_name: str) -> bool:
        cur = self.cursor(conn)
        if self.engine == 'postgresql':
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (table_name,)
            )
        else:
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
        return cur.fetchone() is not None

    def column_exists(self, conn, table_name: str, column_name: str) -> bool:
        cur = self.cursor(conn)
        if self.engine == 'postgresql':
            cur.execute(
                """SELECT 1 FROM information_schema.columns
                   WHERE table_name = %s AND column_name = %s""",
                (table_name, column_name)
            )
            return cur.fetchone() is not None
        else:
            cur.execute(f"PRAGMA table_info({table_name})")
            return any(row['name'] == column_name for row in cur.fetchall())

    def placeholder(self) -> str:
        return '%s' if self.engine == 'postgresql' else '?'

    def lastrowid(self, cursor) -> int:
        if self.engine == 'postgresql':
            return cursor.fetchone()['id']
        return cursor.lastrowid

    def insert_or_ignore_sql(self, table: str, columns: List[str]) -> str:
        cols = ', '.join(columns)
        ph = ', '.join([self.placeholder()] * len(columns))
        if self.engine == 'postgresql':
            return f"INSERT INTO {table} ({cols}) VALUES ({ph}) ON CONFLICT DO NOTHING"
        return f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({ph})"

    def executemany(self, conn, sql: str, params_list: List[tuple]):
        """Execute many. For PostgreSQL we do individual inserts for ON CONFLICT support."""
        if self.engine == 'postgresql':
            cur = self.cursor(conn)
            for params in params_list:
                cur.execute(sql, params)
        else:
            cur = self.cursor(conn)
            cur.executemany(sql, params_list)

    def dict_row(self, row) -> Dict[str, Any]:
        return dict(row)

    # ── Sub-station helpers ─────────────────────────────────────

    def _get_sub_stations_of(self, conn, main_id: float) -> List[float]:
        """Get sub-station IDs for a main station."""
        cur = self.cursor(conn)
        cur.execute('SELECT id FROM stations ORDER BY id')
        ids = [row['id'] for row in cur.fetchall()]
        return [sid for sid in ids if math.floor(sid) == int(main_id) and sid != float(int(main_id))]

    def _get_target_station(self, conn, target_main_id: float) -> float:
        """Get the actual target station ID.
        If target_main_id has sub-stations, return the first sub-station.
        Otherwise, return target_main_id itself."""
        subs = self._get_sub_stations_of(conn, target_main_id)
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
            cur = self.cursor(conn)
            ph = self.placeholder()

            # Get current order status
            cur.execute(f'SELECT * FROM orders WHERE id = {ph}', (order_id,))
            row = cur.fetchone()
            if not row:
                return {'success': False, 'message': 'Order not found'}

            order = dict(row)
            if order['status'] != 'production':
                return {'success': False, 'message': 'Order not in production'}

            current_station = order['current_station']

            # Get the actual target station (with sub-station if available)
            actual_target = self._get_target_station(conn, target_station)

            # If order is already at the target, nothing to do
            if current_station == actual_target:
                return {'success': True, 'message': f'Order already at station {actual_target}'}

            # Close current station log entry if exists
            exited_at = datetime.now().isoformat()
            cur.execute(f'''
                UPDATE station_log
                SET exited_at = {ph}, result = 'OK'
                WHERE order_id = {ph} AND station_id = {ph} AND exited_at IS NULL
            ''', (exited_at, order_id, current_station))

            # Update order station
            cur.execute(f'''
                UPDATE orders SET current_station = {ph} WHERE id = {ph}
            ''', (actual_target, order_id))

            # Log entry to new station
            entered_at = datetime.now().isoformat()
            cur.execute(f'''
                INSERT INTO station_log (order_id, station_id, entered_at, result)
                VALUES ({ph}, {ph}, {ph}, 'OK')
            ''', (order_id, actual_target, entered_at))

            conn.commit()
            if actual_target != target_station:
                return {
                    'success': True,
                    'message': f'Order moved to sub-station {actual_target}',
                    'redirected': True,
                    'actual_station': actual_target
                }
            else:
                return {'success': True, 'message': f'Order moved to station {actual_target}'}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'message': f'Error: {str(e)}'}
        finally:
            conn.close()
