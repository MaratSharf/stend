#!/usr/bin/env python
"""
Проверка точного типа current_station в БД
"""
from utils.db_connection import DBConnection

db = DBConnection('data/mes.db')
conn = db.get_connection()
cur = db.cursor(conn)

# Проверить точное значение current_station
cur.execute("SELECT id, order_number, current_station, typeof(current_station) as station_type FROM orders WHERE id = 5")
row = cur.fetchone()
print(f"Заказ 5: {dict(row)}")

# Проверить, как SQL сравнивает 6.1
cur.execute("SELECT id, order_number, current_station FROM orders WHERE current_station = 6.1")
rows = cur.fetchall()
print(f"\nЗаказы где current_station = 6.1: {[dict(r) for r in rows]}")

cur.execute("SELECT id, order_number, current_station FROM orders WHERE current_station = '6.1'")
rows = cur.fetchall()
print(f"Заказы где current_station = '6.1': {[dict(r) for r in rows]}")

conn.close()
