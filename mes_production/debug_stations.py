import sqlite3

conn = sqlite3.connect('data/mes.db')
c = conn.cursor()

print("=== Orders in production ===")
c.execute('SELECT id, order_number, current_station, status FROM orders WHERE status = "production"')
for row in c.fetchall():
    print(row)

print("\n=== All Stations ===")
c.execute('SELECT id, name FROM stations ORDER BY id')
for row in c.fetchall():
    print(row)

print("\n=== Sub-stations for station 6 ===")
c.execute('SELECT id, name FROM stations WHERE id > 6 AND id < 7 ORDER BY id')
for row in c.fetchall():
    print(row)

print("\n=== Orders at station 6.0 ===")
c.execute('SELECT id, order_number, current_station FROM orders WHERE current_station = 6.0 AND status = "production"')
for row in c.fetchall():
    print(row)

print("\n=== Orders at station 6.1 ===")
c.execute('SELECT id, order_number, current_station FROM orders WHERE current_station = 6.1 AND status = "production"')
for row in c.fetchall():
    print(row)

conn.close()
