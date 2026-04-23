# 🔄 Миграция на PostgreSQL

Инструкция по переходу MES Production System с SQLite на PostgreSQL.

---

## 📋 Содержание

1. [Требования](#требования)
2. [Установка PostgreSQL](#установка-postgresql)
3. [Настройка базы данных](#настройка-базы-данных)
4. [Конфигурация приложения](#конфигурация-приложения)
5. [Миграция данных из SQLite](#миграция-данных-из-sqlite)
6. [Запуск приложения](#запуск-приложения)
7. [Проверка работы](#проверка-работы)
8. [Возврат к SQLite (откат)](#возврат-к-sqlite-откат)

---

## 🔧 Требования

- **PostgreSQL 12+** (рекомендуется 14+)
- **Python 3.10+**
- **psycopg2-binary** (уже установлен в `requirements.txt`)

---

## 📥 Установка PostgreSQL

### Windows

1. Скачайте установщик с [официального сайта](https://www.postgresql.org/download/windows/)
2. Запустите установщик, выберите версию 14 или новее
3. При установке запомните:
   - Порт (по умолчанию `5432`)
   - Пароль суперпользователя `postgres`

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

### macOS (Homebrew)

```bash
brew install postgresql@14
brew services start postgresql@14
```

---

## 🗄️ Настройка базы данных

### 1. Вход в PostgreSQL

```bash
# Windows (через cmd)
psql -U postgres

# Linux/macOS
sudo -u postgres psql
```

### 2. Создание базы данных и пользователя

```sql
-- Создать базу данных
CREATE DATABASE mes_production;

-- Создать пользователя
CREATE USER mes_user WITH PASSWORD 'mes_password';

-- Предоставить права
GRANT ALL PRIVILEGES ON DATABASE mes_production TO mes_user;

-- Для PostgreSQL 15+ также нужно предоставить права на схему
\c mes_production
GRANT ALL ON SCHEMA public TO mes_user;
```

### 3. Выход из psql

```sql
\q
```

---

## ⚙️ Конфигурация приложения

### 1. Обновите `config.yaml`

Файл: `mes_production/config.yaml`

```yaml
database:
  engine: postgresql
  host: localhost
  port: 5432
  name: mes_production
  user: mes_user
  password: mes_password

server:
  host: 0.0.0.0
  port: 5000

stations:
  - name: Приёмка
    subs:
      - Приёмка 1.1
      - Приёмка 1.2
  - name: Сортировка
  - name: Подготовка
    subs:
      - Подготовка 3.1
  - name: Сборка
  - name: Пайка
  - name: Контроль
  - name: Тестирование
  - name: Упаковка
  - name: Маркировка
  - name: Отгрузка

auth:
  api_keys:
    - change-me-to-a-secure-key

logging:
  level: INFO
  path: data/logs
```

### 2. Настройка пользователей (users.db)

Если вы используете отдельную БД для пользователей, обновите `user_db_conn` в `web/app.py`:

```python
# Для PostgreSQL
app.config['user_db_conn'] = {
    'engine': 'postgresql',
    'host': 'localhost',
    'port': 5432,
    'name': 'mes_users',
    'user': 'mes_user',
    'password': 'mes_password'
}
```

Или оставьте SQLite для пользователей:

```python
# Для SQLite (по умолчанию)
app.config['user_db_path'] = 'data/users.db'
```

---

## 📊 Миграция данных из SQLite

### Вариант 1: Автоматическая миграция скриптом

Создайте файл `mes_production/migrate_to_pg.py`:

```python
#!/usr/bin/env python
"""
Скрипт миграции данных из SQLite в PostgreSQL
"""
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import yaml

def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_sqlite_tables(db_path):
    """Получить все данные из SQLite"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    tables = {
        'orders': [],
        'stations': [],
        'station_log': [],
        'users': [],
        'role_permissions': []
    }
    
    for table in tables.keys():
        try:
            cursor.execute(f'SELECT * FROM {table}')
            rows = cursor.fetchall()
            tables[table] = [dict(row) for row in rows]
            print(f"✓ {table}: {len(tables[table])} записей")
        except sqlite3.OperationalError:
            print(f"✗ {table}: таблица не найдена")
    
    conn.close()
    return tables

def migrate_to_postgresql(data, pg_config):
    """Загрузить данные в PostgreSQL"""
    conn = psycopg2.connect(
        host=pg_config['host'],
        port=pg_config['port'],
        dbname=pg_config['name'],
        user=pg_config['user'],
        password=pg_config['password']
    )
    cursor = conn.cursor()
    
    # Миграция orders
    if data['orders']:
        print("\nМиграция orders...")
        for order in data['orders']:
            cursor.execute('''
                INSERT INTO orders 
                (id, batch, order_number, product_code, color, quantity, 
                 status, current_station, completed_subs, created_at, 
                 started_at, completed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            ''', (
                order['id'], order['batch'], order['order_number'],
                order['product_code'], order['color'], order['quantity'],
                order['status'], order['current_station'], order['completed_subs'],
                order['created_at'], order['started_at'], order['completed_at']
            ))
    
    # Миграция stations
    if data['stations']:
        print("\nМиграция stations...")
        for station in data['stations']:
            cursor.execute('''
                INSERT INTO stations (id, name, order_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            ''', (station['id'], station['name'], station.get('order_id')))
    
    # Миграция station_log
    if data['station_log']:
        print("\nМиграция station_log...")
        for log in data['station_log']:
            cursor.execute('''
                INSERT INTO station_log 
                (id, order_id, station_id, entered_at, exited_at, result)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            ''', (
                log['id'], log['order_id'], log['station_id'],
                log['entered_at'], log.get('exited_at'), log.get('result', 'OK')
            ))
    
    # Миграция users
    if data['users']:
        print("\nМиграция users...")
        for user in data['users']:
            cursor.execute('''
                INSERT INTO users 
                (id, username, password_hash, role, is_active, 
                 password_changed, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            ''', (
                user['id'], user['username'], user['password_hash'],
                user['role'], user['is_active'], user['password_changed'],
                user['created_at']
            ))
    
    # Миграция role_permissions
    if data['role_permissions']:
        print("\nМиграция role_permissions...")
        for perm in data['role_permissions']:
            cursor.execute('''
                INSERT INTO role_permissions (role, permission)
                VALUES (%s, %s)
                ON CONFLICT (role, permission) DO NOTHING
            ''', (perm['role'], perm['permission']))
    
    # Сброс последовательностей (для SERIAL-полей)
    print("\nСброс последовательностей...")
    cursor.execute("SELECT setval('orders_id_seq', (SELECT MAX(id) FROM orders))")
    cursor.execute("SELECT setval('station_log_id_seq', (SELECT MAX(id) FROM station_log))")
    cursor.execute("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users))")
    
    conn.commit()
    conn.close()
    print("\n✓ Миграция завершена успешно!")

def main():
    print("=" * 50)
    print("Миграция данных из SQLite в PostgreSQL")
    print("=" * 50)
    
    config = load_config()
    db_config = config.get('database', {})
    
    if db_config.get('engine') != 'postgresql':
        print("❌ Ошибка: в config.yaml должен быть указан engine: postgresql")
        return
    
    # Путь к SQLite БД
    sqlite_path = input("\nПуть к SQLite базе (data/mes.db): ").strip()
    if not sqlite_path:
        sqlite_path = 'data/mes.db'
    
    print(f"\nЧтение данных из {sqlite_path}...")
    data = get_sqlite_tables(sqlite_path)
    
    confirm = input(f"\nПродолжить миграцию в PostgreSQL? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Миграция отменена")
        return
    
    print("\nЗагрузка данных в PostgreSQL...")
    migrate_to_postgresql(data, db_config)

if __name__ == '__main__':
    main()
```

### 2. Запуск миграции

```bash
cd mes_production
python migrate_to_pg.py
```

### Вариант 2: Ручная миграция через pgAdmin

1. Откройте **pgAdmin** и подключитесь к PostgreSQL
2. Используйте **Import/Export** для каждой таблицы
3. Или выполните SQL-дампы через `pg_dump` и `psql`

---

## 🚀 Запуск приложения

### 1. Проверка зависимостей

```bash
cd mes_production
pip install -r requirements.txt
```

### 2. Запуск через Waitress (продакшен)

```bash
python run.py
```

### 3. Запуск в режиме разработки

```bash
python -m web.app
```

Приложение будет доступно по адресу: **http://localhost:5000**

---

## ✅ Проверка работы

### 1. Проверка подключения к БД

```bash
python -c "from utils.database import Database; import yaml; c=yaml.safe_load(open('config.yaml')); db=Database(c['database']); print('✓ Подключение успешно')"
```

### 2. Запуск тестов

```bash
pytest tests/ -v
```

Все 56 тестов должны пройти успешно.

### 3. Проверка веб-интерфейса

1. Откройте http://localhost:5000
2. Войдите как `admin` / `admin`
3. Создайте тестовый заказ
4. Проверьте переходы между станциями

---

## ↩️ Возврат к SQLite (откат)

### 1. Восстановите `config.yaml`

```yaml
database:
  path: data/mes.db
```

### 2. Восстановите базу из резервной копии

```bash
# Сделайте резервную копию перед миграцией!
copy data\mes.db data\mes.db.backup
```

---

## 📝 Примечания

### Преимущества PostgreSQL

- ✅ Надёжность и целостность данных
- ✅ Поддержка транзакций ACID
- ✅ Масштабируемость
- ✅ Параллельные запросы
- ✅ Резервное копирование

### Особенности

- **SERIAL-поля** в PostgreSQL автоматически создают последовательности
- **ON CONFLICT** вместо `INSERT OR IGNORE` в SQLite
- **%s** вместо `?` для параметризованных запросов
- **RealDictCursor** для доступа к полям по имени

---

## 🆘 Решение проблем

### Ошибка подключения

```
psycopg2.OperationalError: connection refused
```

**Решение:** Убедитесь, что служба PostgreSQL запущена:

```bash
# Windows
net start postgresql-x64-14

# Linux
sudo systemctl start postgresql
```

### Ошибка аутентификации

```
psycopg2.OperationalError: password authentication failed
```

**Решение:** Проверьте пароль в `config.yaml` и создайте пользователя заново:

```sql
ALTER USER mes_user WITH PASSWORD 'mes_password';
```

### Ошибка прав доступа

```
permission denied for schema public
```

**Решение:** Предоставьте права на схему:

```sql
\c mes_production
GRANT ALL ON SCHEMA public TO mes_user;
```

---

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи в `data/logs/`
2. Убедитесь, что PostgreSQL запущен
3. Проверьте права пользователя
4. Убедитесь, что `psycopg2-binary` установлен

---

*Документация актуальна для версии 0.6.3*