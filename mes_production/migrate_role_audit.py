"""
MES Production System - Migration for Role Audit Log
Добавляет таблицу для аудита изменений ролей.
Запуск: python migrate_role_audit.py
"""
import sqlite3
import os
import sys

# Добавить родительскую директорию в path для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def migrate(db_path: str):
    """Создать таблицу role_audit_log если она не существует."""
    
    print(f"Подключение к базе данных: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"❌ Файл БД не найден: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Проверка существования таблицы
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='role_audit_log'"
        )
        if cursor.fetchone():
            print("ℹ️  Таблица role_audit_log уже существует")
            return True
        
        # Создание таблицы аудита
        print("📝 Создание таблицы role_audit_log...")
        cursor.execute('''
            CREATE TABLE role_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id TEXT NOT NULL,           -- Имя роли (используем TEXT для совместимости)
                action TEXT NOT NULL,            -- 'created', 'updated', 'deleted', 
                                                  -- 'permission_added', 'permission_removed'
                old_value TEXT,                  -- JSON со старыми значениями
                new_value TEXT,                  -- JSON с новыми значениями
                changed_by INTEGER,              -- ID пользователя
                changed_at TEXT NOT NULL,        -- ISO timestamp
                ip_address TEXT,                 -- IP адрес
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
    from flask import Flask
    
    # Попытка загрузить конфиг из приложения
    try:
        # Импортировать функцию создания приложения если доступна
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "app_module", 
            os.path.join(os.path.dirname(__file__), 'web', 'app.py')
        )
        # Для простоты используем стандартный путь
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
