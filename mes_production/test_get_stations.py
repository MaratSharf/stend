#!/usr/bin/env python
"""
Тест запроса get_stations для подстанции 6.1 - PostgreSQL версия
"""
from utils.db_connection import DBConnection
from config import load_config
import logging

# Создаем logger
logger = logging.getLogger('test')
logger.setLevel(logging.INFO)

try:
    config = load_config()
    db = DBConnection(config['database'])
except Exception:
    print("Ошибка загрузки конфигурации. Используйте PostgreSQL конфигурацию в config.yaml")
    exit(1)

conn = db.get_connection()
cur = db.cursor(conn)

# Получаем станции
cur.execute('SELECT * FROM stations ORDER BY id')
stations = [dict(row) for row in cur.fetchall()]

print("Результат get_stations():")
for station in stations:
    if station['id'] in [6.0, 6.1]:
        # Получаем заказы для этой станции
        cur.execute("SELECT order_number FROM orders WHERE current_station = %s", (station['id'],))
        orders = [row['order_number'] for row in cur.fetchall()]
        print(f"  Станция {station['id']} ({station['name']}): {len(orders)} заказ(ов)")
        for order_number in orders:
            print(f"    - {order_number}")

conn.close()