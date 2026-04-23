#!/usr/bin/env python
"""
Перемещение заказа на станцию 6 (Контроль) для тестирования QR-сканера
"""
from utils.db_connection import DBConnection

def move_order_to_station_6(order_id, target_station=6.0):
    """Переместить заказ на станцию 6."""
    db = DBConnection('data/mes.db')
    conn = db.get_connection()
    cur = db.cursor(conn)
    
    # Получить текущий статус заказа
    cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,)) if db.engine == 'postgresql' else cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cur.fetchone()
    
    if not order:
        print(f"Заказ {order_id} не найден")
        conn.close()
        return
    
    order_dict = dict(order)
    print(f"Текущий заказ: {order_dict}")
    
    # Обновить станцию заказа
    if db.engine == 'postgresql':
        cur.execute(
            "UPDATE orders SET current_station = %s, status = 'production' WHERE id = %s",
            (target_station, order_id)
        )
    else:
        cur.execute(
            "UPDATE orders SET current_station = ?, status = 'production' WHERE id = ?",
            (target_station, order_id)
        )
    
    conn.commit()
    
    # Добавить запись в station_log
    from datetime import datetime
    entered_at = datetime.now().isoformat()
    
    if db.engine == 'postgresql':
        cur.execute(
            "INSERT INTO station_log (order_id, station_id, entered_at) VALUES (%s, %s, %s)",
            (order_id, target_station, entered_at)
        )
    else:
        cur.execute(
            "INSERT INTO station_log (order_id, station_id, entered_at) VALUES (?, ?, ?)",
            (order_id, target_station, entered_at)
        )
    
    conn.commit()
    
    # Подтверждение
    cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,)) if db.engine == 'postgresql' else cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    updated_order = cur.fetchone()
    
    print(f"\n✓ Заказ {order_dict['order_number']} перемещён на станцию {target_station} (Контроль)")
    print(f"  Новый статус: {dict(updated_order)}")
    
    conn.close()

if __name__ == '__main__':
    # Переместить заказ ORD-4982-016 (id=5) на станцию 6
    print("Перемещение заказа на станцию 6 (Контроль)...")
    move_order_to_station_6(5, 6.0)