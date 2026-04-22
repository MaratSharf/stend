"""
MES Production System — Unified DB Connection utility
Supports both SQLite and PostgreSQL backends with a common interface.
"""
import sqlite3
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
