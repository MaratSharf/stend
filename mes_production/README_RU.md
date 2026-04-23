# 🏭 MES Production System

**Manufacturing Execution System (MES)** — веб-приложение для управления производственными заказами и отслеживания прохождения заказов через рабочие станции.

## 📋 Описание

Система позволяет:

- ✅ **Создавать пакеты заказов** с автогенерацией уникальных номеров
- ✅ **Запускать заказы в производство** на первую станцию
- ✅ **Отслеживать перемещение заказов** между рабочими станциями
- ✅ **Автоматически завершать заказы** после прохождения всех станций
- ✅ **Просматривать статистику производства** в реальном времени
- ✅ **Управлять статусом заказов** (буфер, производство, завершено, отменено)
- ✅ **Интегрировать QR-сканирование** на этапе контроля (станция 6.1)

### 🔄 Производственные станции

Система включает 10 рабочих станций:

| № | Станция | Подстанции |
|---|---------|------------|
| 1 | Приёмка | 1.1, 1.2 |
| 2 | Сортировка | — |
| 3 | Подготовка | 3.1 |
| 4 | Сборка | — |
| 5 | Пайка | — |
| 6 | Контроль | 6.1 (QR-scanner) |
| 7 | Тестирование | — |
| 8 | Упаковка | — |
| 9 | Маркировка | — |
| 10 | Отгрузка | — |

## 🛠️ Технологии

| Категория | Технология |
|-----------|------------|
| Язык | Python 3.10+ |
| Веб-фреймворк | Flask >= 3.0.0 |
| Аутентификация | Flask-Login >= 0.6.3 |
| Сервер | Waitress >= 3.0.0 |
| База данных | PostgreSQL 12+ (psycopg2-binary >= 2.9.0) |
| Конфигурация | YAML (PyYAML >= 6.0) |
| Фронтенд | HTML5/CSS3/JavaScript (тёмная/светлая тема) |
| Тесты | pytest >= 8.0, pytest-cov >= 5.0 |

## 📁 Структура проекта

```
mes_production/
├── run.py                # Точка входа (Waitress сервер)
├── config.yaml           # Конфигурация системы
├── requirements.txt      # Python зависимости
├── pytest.ini            # Конфигурация pytest
│
├── core/
│   └── controller.py     # Контроллер бизнес-логики
│
├── utils/
│   ├── database.py       # Операции с базой данных
│   ├── db_connection.py  # Подключение к PostgreSQL
│   ├── logger.py         # Настройка логирования
│   ├── permissions.py    # Права доступа (permissions)
│   └── role_service.py   # Сервис управления ролями
│
├── web/
│   ├── app.py            # Flask приложение (фабрика)
│   ├── auth.py           # Мидлвара аутентификации по API-ключу
│   ├── auth_user.py      # Аутентификация пользователей (Flask-Login)
│   ├── models.py         # Модели данных (User, ROLES)
│   ├── static/           # Статические файлы (CSS, JS)
│   └── templates/        # HTML-шаблоны
│
├── tests/
│   ├── conftest.py       # Общие фикстуры
│   ├── test_api.py       # Интеграционные тесты (API + авторизация)
│   └── test_database.py  # Модульные тесты (БД + Контроллер)
│
└── data/
    ├── mes.db            # SQLite (резервная копия)
    ├── users.db          # SQLite (резервная копия)
    └── logs/             # Логи приложения
```

## 🚀 Установка и запуск

### Предварительные требования

- Python 3.10 или выше
- PostgreSQL 12 или выше
- pip (менеджер пакетов Python)

### Шаг 1: Создание и активация виртуальной среды

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Шаг 2: Установка зависимостей

```bash
pip install -r requirements.txt
```

### Шаг 3: Настройка PostgreSQL

```sql
-- Создание базы данных
CREATE DATABASE mes_production;

-- Создание пользователя
CREATE USER mes_user WITH PASSWORD 'mes_password';

-- Предоставление прав
GRANT ALL PRIVILEGES ON DATABASE mes_production TO mes_user;
```

### Шаг 4: Настройка конфигурации

Откройте `config.yaml` и настройте параметры:

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
    subs:
      - QR-scanner 6.1
  - name: Тестирование
  - name: Упаковка
  - name: Маркировка
  - name: Отгрузка
auth:
  api_keys:
    - ваш-секретный-ключ
logging:
  level: INFO
  path: data/logs
```

### Шаг 5: Запуск приложения

```bash
python run.py
```

Приложение запустится и будет доступно по адресу:
- **http://localhost:5000**

### Шаг 6: Первый вход

- **Логин:** `admin`
- **Пароль:** `admin`

> ⚠️ **Смените пароль** при первом входе через страницу `/change-password`.

### Остановка

Нажмите **Ctrl+C** в терминале.

## 🌐 Веб-интерфейс

### Основные страницы

| Страница | Route | Описание |
|----------|-------|----------|
| Вход | `/login` | Форма аутентификации |
| Заказы | `/` | Список всех заказов с фильтрацией |
| Трекинг | `/tracking` | Карта станций — визуализация прохождения |
| Станция | `/station` | Детали станции с заказами |
| Карта | `/map` | SVG-визуализация конвейера |
| Пользователи | `/users` | Админ-панель управления пользователями |
| Роли | `/roles` | Управление правами ролей |
| Смена пароля | `/change-password` | Принудительная смена пароля |

### Статические файлы

- `static/style.css` — основные стили
- `static/theme.js` — переключение тёмной/светлой темы
- `static/script.js` — общая логика фронтенда
- `static/orders.js` — логика заказов
- `static/station.js` — логика станций
- `static/map.js` — логика карты

## 📡 API Endpoints

### Заказы

| Метод | Endpoint | Доступ | Описание |
|-------|----------|--------|----------|
| GET | `/api/orders` | Login | Все заказы (`?status=buffer/production/completed/cancelled`) |
| POST | `/api/orders` | Login/API | Создать заказы |
| POST | `/api/orders/<id>/launch` | Login/API | Запустить в производство |
| POST | `/api/orders/<id>/move` | Login/API | Переместить на след. станцию |
| POST | `/api/orders/<id>/complete` | Login/API | Завершить вручную |
| POST | `/api/orders/<id>/cancel` | Login/API | Отменить заказ |
| POST | `/api/orders/<id>/complete-sub` | Login/API | Завершить подстанцию |
| POST | `/api/orders/<id>/scan-result` | Login/API | Сохранить результат QR-сканирования |

### Станции и статистика

| Метод | Endpoint | Доступ | Описание |
|-------|----------|--------|----------|
| GET | `/api/stations` | Login/API | Статус всех станций |
| GET | `/api/statistics` | Login/API | Статистика производства |
| GET | `/api/sub-stations` | Login | Подстанции группой |

### Управление пользователями

| Метод | Endpoint | Доступ | Описание |
|-------|----------|--------|----------|
| GET | `/api/users` | Admin | Список пользователей |
| POST | `/api/users` | Admin | Создать пользователя |
| POST | `/api/users/<id>` | Admin | Обновить пользователя |
| DELETE | `/api/users/<id>` | Admin | Удалить пользователя |

### Управление ролями

| Метод | Endpoint | Доступ | Описание |
|-------|----------|--------|----------|
| GET | `/api/roles` | Login | Список ролей |
| POST | `/api/roles` | Admin | Создать роль |
| POST | `/api/roles/<role>/permissions` | Admin | Установить права |
| DELETE | `/api/roles/<role>` | Admin | Удалить роль |

### Создание заказов (пакетная генерация)

**Формат запроса:**
```json
{
  "batch": "BATCH-A",
  "product_code": "MOLD-220",
  "color": "Красный",
  "quantity": 3
}
```

**Формат ответа:**
```json
{
  "success": true,
  "orders": [
    {
      "id": 1,
      "batch": "BATCH-A",
      "order_number": "ORD-0001",
      "product_code": "MOLD-220",
      "color": "Красный",
      "quantity": 1,
      "status": "buffer"
    }
  ],
  "count": 3,
  "message": "Created 3 order(s)"
}
```

### Формат номеров заказов

Формат: `ORD-<последние-4-цифры-id>`

Примеры: `ORD-0001`, `ORD-0042`, `ORD-0123`

Каждый созданный заказ имеет `quantity: 1`. Поле `quantity` в запросе означает **количество заказов для генерации**.

### Примеры curl

**Создание заказов:**
```bash
curl -X POST http://localhost:5000/api/orders \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ваш-ключ" \
  -d '{"batch":"B1","product_code":"P1","color":"Red","quantity":3}'
```

**Получение заказов:**
```bash
curl http://localhost:5000/api/orders
```

**Запуск заказа:**
```bash
curl -X POST http://localhost:5000/api/orders/1/launch \
  -H "X-API-Key: ваш-ключ"
```

## 🔐 Аутентификация и авторизация

### Типы аутентификации

1. **Сессийная (браузер)** — через Flask-Login с CSRF-токенами
2. **API-ключи** — для машинных скриптов (заголовок `X-API-Key`)

### Роли пользователей

| Роль | Уровень | Описание |
|------|---------|----------|
| `viewer` | 1 | Просмотр заказов и статистики |
| `operator` | 2 | Операционные действия (запуск, перемещение, завершение) |
| `admin` | 3 | Управление пользователями и ролями |

### Права доступа (permissions)

| Категория | Права |
|-----------|-------|
| **Заказы** | `order_view`, `order_create`, `order_launch`, `order_move`, `order_complete`, `order_cancel` |
| **Станции** | `station_view`, `station_control` |
| **Производство** | `production_view`, `map_view` |
| **Пользователи** | `user_view`, `manage_users` |
| **Роли** | `role_view`, `manage_roles` |

### Правила защиты эндпоинтов

| Тип операции | Требуемая аутентификация | CSRF | Роль |
|--------------|--------------------------|------|------|
| GET (чтение) | Login или API-ключ | Нет | Любая |
| POST (запись) | Login (operator+) **ИЛИ** API-ключ | Да (для login) | Operator+ |

### Кастомные роли

Система поддерживает создание пользовательских ролей с произвольными правами:

```bash
# Создание роли через API
POST /api/roles
{
  "role": "supervisor",
  "permissions": ["order_view", "order_create", "station_view"]
}
```

## 📊 Статусы заказов

| Статус | Описание |
|--------|----------|
| `buffer` | Заказ создан, ожидает запуска |
| `production` | Заказ в производстве |
| `completed` | Заказ завершён |
| `cancelled` | Заказ отменён |

## 🗄️ База данных

При первом запуске автоматически создаются таблицы в PostgreSQL.

### Таблицы

| Таблица | Описание |
|---------|----------|
| `orders` | Заказы с отслеживанием статуса |
| `stations` | 10 рабочих станций с текущими заказами |
| `station_log` | Журнал прохождения станций |
| `users` | Пользователи системы |
| `role_permissions` | Права доступа для ролей |
| `qr_scans` | Результаты QR-сканирования |

### Особенности

- **Внешние ключи** включены
- **Транзакции** с rollback для многошаговых операций
- **REAL-типы** для station_id (поддержка подстанций 1.1, 1.2 и т.д.)
- **completed_subs** — поле для отслеживания завершённых подстанций

### Схемы

**orders:**
```sql
id SERIAL PRIMARY KEY
batch TEXT NOT NULL
order_number TEXT UNIQUE NOT NULL
product_code TEXT NOT NULL
color TEXT NOT NULL
quantity INTEGER NOT NULL
status TEXT DEFAULT 'buffer'
current_station REAL
completed_subs TEXT DEFAULT ''
created_at TEXT NOT NULL
started_at TEXT
completed_at TEXT
```

**stations:**
```sql
id REAL PRIMARY KEY
name TEXT NOT NULL
order_id INTEGER (FK → orders.id)
```

**station_log:**
```sql
id SERIAL PRIMARY KEY
order_id INTEGER NOT NULL (FK → orders.id)
station_id REAL NOT NULL (FK → stations.id)
entered_at TEXT NOT NULL
exited_at TEXT
result TEXT DEFAULT 'OK'
```

## 🧪 Тестирование

```bash
# Все тесты с покрытием
pytest --cov=utils --cov=core --cov=web -v

# Конкретный файл
pytest tests/test_api.py -v

# По ключевому слову
pytest -k "launch" -v
```

**Текущее покрытие: 92%** (47+ тестов)

| Файл | Покрытие |
|------|----------|
| `core/controller.py` | 100% |
| `utils/database.py` | 90% |
| `utils/logger.py` | 100% |
| `web/app.py` | 92% |
| `web/auth.py` | 86% |

## 🐛 Режим разработки

Для разработки можно запускать с отладкой:

```bash
python -m web.app
```

Запускается Flask development server с автоматической перезагрузкой.

## 🔄 Жизненный цикл заказа

```
[Создание] → buffer → [Запуск] → production → [Перемещение через станции] → 
→ [Достижение последней станции] → [Автозавершение] → completed
                                   ↓
                              [Отмена в любой момент] → cancelled
```

### Логика подстанций

1. Заказ попадает на основную станцию (например, 1.0)
2. Подстанции (1.1, 1.2) должны быть завершены по отдельности
3. После завершения всех подстанций заказ может перейти на следующую основную станцию
4. `completed_subs` хранит список завершённых подстанций (например, `"1.1,1.2"`)

## 📝 Правила разработки

### Стиль кодирования

- **Python:** PEP 8, типизация через `typing`
- **Импорты:** группировка (стандартная библиотека → сторонние → локальные)
- **Имена:** snake_case для функций/переменных, PascalCase для классов

### Логирование

Используйте встроенный logger из `utils.logger`:
```python
from utils.logger import setup_logger
logger = setup_logger('my_module', 'data/logs', 'INFO')
logger.info('Сообщение')
```

### Обработка ошибок

- Все БД-операции оборачиваются в `try...except` с `rollback()`
- Логирование ошибок через `logger.error(..., exc_info=True)`
- API возвращает JSON с `{error: ...}` и HTTP-статусом

### Тестирование

- **Модульные тесты:** `tests/test_database.py` — БД и контроллер
- **Интеграционные тесты:** `tests/test_api.py` — API с авторизацией
- **Фикстуры:** `conftest.py` — общие setUp/tearDown
- **Покрытие:** используйте `pytest --cov` для проверки

### CSRF-защита

- Все POST-запросы от сессионных пользователей требуют CSRF-токен
- API-ключи bypass CSRF (для скриптов)
- Токен генерируется через `generate_csrf_token()` и проверяется через `validate_csrf_token()`

## 📚 Дополнительные файлы документации

| Файл | Описание |
|------|----------|
| `README.md` | Основная документация (английский) |
| `AUTHORIZATION_GUIDE.md` | Документация по аутентификации |
| `ORDER_LIFECYCLE.md` | Жизненный цикл заказа |
| `QR_SCANNER_INTEGRATION.md` | Интеграция QR-сканера |
| `MIGRATION_TO_POSTGRESQL.md` | Миграция на PostgreSQL |
| `ROLE_MANAGEMENT_IMPROVEMENTS.md` | План улучшений ролевой модели |

## 🛠️ Команды для разработчиков

```bash
# Запуск сервера
python run.py

# Запуск в режиме отладки
python -m web.app

# Тесты с покрытием
pytest --cov=utils --cov=core --cov=web -v

# Проверка конкретного теста
pytest tests/test_database.py::test_launch_order -v

# Форматирование (если используется black)
black .

# Линтинг (если используется flake8/pylint)
flake8 .
```

## 🔒 Безопасность

- **Хеширование паролей:** PBKDF2 через `werkzeug.security`
- **CSRF-защита:** для всех POST-запросов сессийных пользователей
- **API-ключи:** для машинных интеграций
- **Ролевая модель:** granular permissions для каждого действия

## 📝 Лицензия

MIT

## 👤 Автор

**Marat Sharf**

---

*Версия: 0.6.3*
*Дата обновления: 2026-04-23*