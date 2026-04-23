"""
MES Production System - Migration for Role Audit Log (PostgreSQL version)
Добавляет таблицу для аудита изменений ролей.
Запуск: python migrate_role_audit.py
"""
import os
import sys
from utils.db_connection import DBConnection
from config import load_config


def migrate(db_path: str):
    """Создать таблицу role_audit_log если она не существует."""
    
    print(f"Подключение к базе данных: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"❌ Файл БД не найден: {db_path}")
        return False
    
    # Use config if available, otherwise direct path
    try:
        config = load_config()
        db = DBConnection(config['database'])
    except:
        db = DBConnection(db_path)
    
    conn = db.get_connection()
    try:
        cursor = db.cursor(conn)
        ph = db.placeholder()
        
        # Проверка существования таблицы (PostgreSQL)
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'role_audit_log'
            )
        """)
        if cursor.fetchone()['exists']:
            print("ℹ️  Таблица role_audit_log уже существует")
            return True
        
        # Создание таблицы аудита
        print("📝 Создание таблицы role_audit_log...")
        cursor.execute('''
            CREATE TABLE role_audit_log (
                id SERIAL PRIMARY KEY,
                role_id TEXT NOT NULL,
                action TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                changed_by INTEGER,
                changed_at TEXT NOT NULL,
                ip_address TEXT,
                FOREIGN KEY (changed_by) REFERENCES users(id)
            )
        ''')
        
        # Создание индекса для быстрого поиска по роли
        print("📝 Создание индекса...")
        cursor.execute('''
            CREATE INDEX idx_role_audit_role_id ON role_audit_log(role_id)
        ''')
        
        # Создание индекса для сортировки по времени
        cursor.execute('''
            CREATE INDEX idx_role_audit_changed_at ON role_audit_log(changed_at DESC)
        ''')
        
        conn.commit()
        print("✅ Миграция успешно выполнена!")
        print("   Создана таблица: role_audit_log")
        print("   Созданы индексы: idx_role_audit_role_id, idx_role_audit_changed_at")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка миграции: {e}")
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    # Определить путь к БД пользователей
    try:
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data',
            'users.db'
        )
    except Exception:
        db_path = 'data/users.db'
    
    # Проверка аргументов командной строки
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print("=" * 60)
    print("Миграция: Добавление таблицы аудита ролей")
    print("=" * 60)
    
    success = migrate(db_path)
    sys.exit(0 if success else 1)