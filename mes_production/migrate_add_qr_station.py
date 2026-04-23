#!/usr/bin/env python
"""
Миграция для добавления подстанции 6.1 (QR-scanner) к станции 6 (Контроль)
"""
from utils.db_connection import DBConnection

def add_sub_station_6_1():
    """Добавить подстанцию 6.1 если её нет."""
    db = DBConnection('data/mes.db')
    conn = db.get_connection()
    cur = db.cursor(conn)
    
    # Проверить, существует ли уже подстанция 6.1
    if db.engine == 'postgresql':
        cur.execute(
            "SELECT id FROM stations WHERE id = %s",
            (6.1,)
        )
    else:
        cur.execute(
            "SELECT id FROM stations WHERE id = ?",
            (6.1,)
        )
    
    existing = cur.fetchone()
    
    if existing:
        print(f"Подстанция 6.1 уже существует: {dict(existing)}")
        conn.close()
        return
    
    # Добавить подстанцию 6.1
    if db.engine == 'postgresql':
        cur.execute(
            "INSERT INTO stations (id, name, order_id) VALUES (%s, %s, %s)",
            (6.1, 'QR-scanner 6.1', None)
        )
    else:
        cur.execute(
            "INSERT INTO stations (id, name, order_id) VALUES (?, ?, ?)",
            (6.1, 'QR-scanner 6.1', None)
        )
    
    conn.commit()
    print("Подстанция 6.1 (QR-scanner) успешно создана!")
    
    # Подтверждение
    if db.engine == 'postgresql':
        cur.execute("SELECT * FROM stations WHERE id = %s", (6.1,))
    else:
        cur.execute("SELECT * FROM stations WHERE id = ?", (6.1,))
    
    new_station = cur.fetchone()
    print(f"Создано: {dict(new_station)}")
    
    conn.close()

if __name__ == '__main__':
    add_sub_station_6_1()
