#!/usr/bin/env python
"""
Сброс заказа на станцию 6.0 для тестирования логики подстанций
"""
from utils.db_connection import DBConnection

def reset_order_to_station_6(order_id):
    """Сбросить заказ на станцию 6.0."""
    db = DBConnection('data/mes.db')
    conn = db.get_connection()
    cur = db.cursor(conn)
    
    # Обновить станцию заказа на 6.0
    if db.engine == 'postgresql':
        cur.execute(
            "UPDATE orders SET current_station = %s WHERE id = %s",
            (6.0, order_id)
        )
    else:
        cur.execute(
            "UPDATE orders SET current_station = ? WHERE id = ?",
            (6.0, order_id)
        )
    
    conn.commit()
    
    # Подтверждение
    if db.engine == 'postgresql':
        cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    else:
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    updated_order = cur.fetchone()
    
    print(f"Заказ {order_id} сброшен на станцию 6.0")
    print(f"  Новый статус: {dict(updated_order)}")
    
    conn.close()

if __name__ == '__main__':
    reset_order_to_station_6(5)