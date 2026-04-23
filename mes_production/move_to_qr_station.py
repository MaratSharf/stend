#!/usr/bin/env python
"""
Перемещение заказа на подстанцию 6.1 (QR-scanner)
"""
from utils.db_connection import DBConnection
from datetime import datetime

def move_order_to_sub_station_6_1(order_id, sub_station_id=6.1):
    """Переместить заказ на подстанцию 6.1."""
    db = DBConnection('data/mes.db')
    conn = db.get_connection()
    cur = db.cursor(conn)
    
    # Получить текущий статус заказа
    if db.engine == 'postgresql':
        cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    else:
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cur.fetchone()
    
    if not order:
        print(f"Заказ {order_id} не найден")
        conn.close()
        return
    
    order_dict = dict(order)
    print(f"Текущий заказ: {order_dict}")
    
    # Освободить текущую станцию (обновить station.log)
    cur.execute("SELECT * FROM station_log WHERE order_id = ? AND exited_at IS NULL", (order_id,)) if db.engine != 'postgresql' else cur.execute("SELECT * FROM station_log WHERE order_id = %s AND exited_at IS NULL", (order_id,))
    active_log = cur.fetchone()
    
    if active_log:
        exited_at = datetime.now().isoformat()
        if db.engine == 'postgresql':
            cur.execute("UPDATE station_log SET exited_at = %s WHERE id = %s", (exited_at, active_log['id']))
        else:
            cur.execute("UPDATE station_log SET exited_at = ? WHERE id = ?", (exited_at, active_log['id']))
        conn.commit()
    
    # Обновить станцию заказа на 6.1
    if db.engine == 'postgresql':
        cur.execute(
            "UPDATE orders SET current_station = %s WHERE id = %s",
            (sub_station_id, order_id)
        )
    else:
        cur.execute(
            "UPDATE orders SET current_station = ? WHERE id = ?",
            (sub_station_id, order_id)
        )
    
    conn.commit()
    
    # Добавить запись в station_log для подстанции 6.1
    entered_at = datetime.now().isoformat()
    if db.engine == 'postgresql':
        cur.execute(
            "INSERT INTO station_log (order_id, station_id, entered_at) VALUES (%s, %s, %s)",
            (order_id, sub_station_id, entered_at)
        )
    else:
        cur.execute(
            "INSERT INTO station_log (order_id, station_id, entered_at) VALUES (?, ?, ?)",
            (order_id, sub_station_id, entered_at)
        )
    
    conn.commit()
    
    # Подтверждение
    if db.engine == 'postgresql':
        cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    else:
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    updated_order = cur.fetchone()
    
    print(f"\n✓ Заказ {order_dict['order_number']} перемещён на подстанцию {sub_station_id} (QR-scanner)")
    print(f"  Новый статус: {dict(updated_order)}")
    
    conn.close()

if __name__ == '__main__':
    print("Перемещение заказа на подстанцию 6.1 (QR-scanner)...")
    move_order_to_sub_station_6_1(5, 6.1)