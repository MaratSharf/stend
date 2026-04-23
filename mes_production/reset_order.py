#!/usr/bin/env python
"""
Сброс заказа на станцию 6.0 для тестирования логики подстанций - PostgreSQL версия
"""
from utils.db_connection import DBConnection
from config import load_config

def reset_order_to_station_6(order_id):
    """Сбросить заказ на станцию 6.0."""
    try:
        config = load_config()
        db = DBConnection(config['database'])
    except Exception:
        print("Ошибка загрузки конфигурации. Используйте PostgreSQL конфигурацию в config.yaml")
        exit(1)
    
    conn = db.get_connection()
    cur = db.cursor(conn)
    
    # Обновить станцию заказа на 6.0
    cur.execute(
        "UPDATE orders SET current_station = %s WHERE id = %s",
        (6.0, order_id)
    )
    
    conn.commit()
    
    # Подтверждение
    cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    updated_order = cur.fetchone()
    
    print(f"Заказ {order_id} сброшен на станцию 6.0")
    print(f"  Новый статус: {dict(updated_order)}")
    
    conn.close()

if __name__ == '__main__':
    reset_order_to_station_6(5)