#!/usr/bin/env python
"""
Тест новой логики: при перемещении на основную станцию заказ автоматически попадает на подстанцию
"""
from utils.db_connection import DBConnection

def test_move_to_station_6():
    """Тест: перемещение заказа на станцию 6.0 должно перенаправить на 6.1"""
    db = DBConnection('data/mes.db')
    conn = db.get_connection()
    cur = db.cursor(conn)
    
    # Получить текущий статус заказа
    cur.execute("SELECT * FROM orders WHERE id = 5")
    order = cur.fetchone()
    print(f"До: заказ {order['order_number']} на станции {order['current_station']}")
    conn.close()
    
    # Используем новый метод move_order_to_station
    result = db.move_order_to_station(5, 6.0)  # Перемещаем на станцию 6.0
    
    print(f"\nРезультат: {result}")
    
    # Проверить новый статус заказа
    cur = db.cursor(db.get_connection())
    cur.execute("SELECT * FROM orders WHERE id = 5")
    order = cur.fetchone()
    print(f"После: заказ {order['order_number']} на станции {order['current_station']}")
    db.get_connection().close()
    
    if order['current_station'] == 6.1:
        print("\n✓ Успех! Заказ автоматически перенаправлен на подстанцию 6.1")
    else:
        print(f"\n✗ Ошибка! Заказ на станции {order['current_station']}, ожидалось 6.1")

if __name__ == '__main__':
    test_move_to_station_6()
