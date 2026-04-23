```
"""
Debug script for checking stations - PostgreSQL version.
"""
from utils.db_connection import DBConnection
from config import load_config

config = load_config()
db = DBConnection(config['database'])

conn = db.get_connection()
try:
    cursor = db.cursor(conn)
    ph = db.placeholder()

    print("=== Orders in production ===")
    cursor.execute('SELECT id, order_number, current_station, status FROM orders WHERE status = %s', ('production',))
    for row in cursor.fetchall():
        print(dict(row))

    print("\n=== All Stations ===")
    cursor.execute('SELECT id, name FROM stations ORDER BY id')
    for row in cursor.fetchall():
        print(dict(row))

    print("\n=== Sub-stations for station 6 ===")
    cursor.execute('SELECT id, name FROM stations WHERE id > 6 AND id < 7 ORDER BY id')
    for row in cursor.fetchall():
        print(dict(row))

    print("\n=== Orders at station 6.0 ===")
    cursor.execute('SELECT id, order_number, current_station FROM orders WHERE current_station = 6.0 AND status = %s', ('production',))
    for row in cursor.fetchall():
        print(dict(row))

    print("\n=== Orders at station 6.1 ===")
    cursor.execute('SELECT id, order_number, current_station FROM orders WHERE current_station = 6.1 AND status = %s', ('production',))
    for row in cursor.fetchall():
        print(dict(row))
finally:
    conn.close()
```