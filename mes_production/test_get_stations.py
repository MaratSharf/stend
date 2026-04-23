#!/usr/bin/env python
"""
Тест запроса get_stations для подстанции 6.1
"""
from utils.database import Database
import logging

# Создаем logger
logger = logging.getLogger('test')
logger.setLevel(logging.INFO)

# Создаем Database instance
db = Database('data/mes.db', logger)

# Получаем станции
stations = db.get_stations()

print("Результат get_stations():")
for station in stations:
    if station['id'] in [6.0, 6.1]:
        print(f"  Станция {station['id']} ({station['name']}): {len(station['orders'])} заказ(ов)")
        for order in station['orders']:
            print(f"    - {order['order_number']}")
