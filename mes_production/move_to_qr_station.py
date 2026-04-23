#!/usr/bin/env python
"""
Перемещение заказа на подстанцию 6.1 (QR-scanner) - PostgreSQL версия
"""
from utils.db_connection import DBConnection
from config import load_config
from datetime import datetime

def move_order_to_sub_station_6_1(order_id, sub_station_id=6.1):
    """Переместить заказ на подстанцию 6.1."""
    try:
        config = load_config()
        db = DBConnection(config['database'])
    except Exception:
        print("Ошибка загрузки конфигурации. Используйте PostgreSQL конфигурацию в config.yaml")
        exit(1)
    
    conn = db.get_connection()
    cur = db.cursor(conn)
    
    # Получить текущий статус заказа
    cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    order = cur.fetchone()
    
    if not order:
        print(f"Заказ {order_id} не найден")
        conn.close()
        return
    
    order_dict = dict(order)
    print(f"Текущий заказ: {order_dict}")
    
    # Освободить текущую станцию (обновить station_log)
    cur.execute("SELECT * FROM station_log WHERE order_id = %s AND exited_at IS NULL", (order_id,))
    active_log = cur.fetchone()
    
    if active_log:
        exited_at = datetime.now().isoformat()
        cur.execute("UPDATE station_log SET exited_at = %s WHERE id = %s", (exited_at, active_log['id']))
        conn.commit()
    
    # Обновить станцию заказа на 6.1
    cur.execute(
        "UPDATE orders SET current_station = %s WHERE id = %s",
        (sub_station_id, order_id)
    )
    
    conn.commit()
    
    # Добавить запись в station_log для подстанции 6.1
    entered_at = datetime.now().isoformat()
    cur.execute(
        "INSERT INTO station_log (order_id, station_id, entered_at) VALUES (%s, %s, %s)",
        (order_id, sub_station_id, entered_at)
    )
    
    conn.commit()
    
    # Подтверждение
    cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    updated_order = cur.fetchone()
    
    print(f"\n✓ Заказ {order_dict['order_number']} перемещён на подстанцию {sub_station_id} (QR-scanner)")
    print(f"  Новый статус: {dict(updated_order)}")
    
    conn.close()

if __name__ == '__main__':
    print("Перемещение заказа на подстанцию 6.1 (QR-scanner)...")
    move_order_to_sub_station_6_1(5, 6.1)