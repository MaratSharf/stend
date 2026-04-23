#!/usr/bin/env python
"""
Проверка станций и заказов
"""
from utils.db_connection import DBConnection

db = DBConnection('data/mes.db')
conn = db.get_connection()
cur = db.cursor(conn)

# Проверить все станции с order_id != NULL
cur.execute('SELECT * FROM stations WHERE order_id IS NOT NULL ORDER BY id')
rows = cur.fetchall()
print('Станции с заказами:')
for row in rows:
    print(dict(row))

# Проверить заказы в production
cur.execute("SELECT id, order_number, current_station, status FROM orders WHERE status = 'production'")
rows = cur.fetchall()
print('\nЗаказы в production:')
for row in rows:
    print(dict(row))

# Проверить все станции (включая 6.1)
cur.execute('SELECT * FROM stations ORDER BY id')
rows = cur.fetchall()
print('\nВсе станции:')
for row in rows:
    print(dict(row))

conn.close()
