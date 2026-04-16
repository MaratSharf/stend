# Возможные улучшения проекта MES Production System

---

## 🔴 Критические (безопасность)

### 1. Вынести `secret_key` в конфигурацию

**Проблема:** `app.secret_key = os.urandom(24)` генерируется при каждом запуске сервера. Все пользовательские сессии сбрасываются.

**Файл:** `mes_production/web/app.py`, строка ~36

**Решение:**
```yaml
# config.yaml
security:
  secret_key: "your-secret-key-here-change-in-production"
```
```python
# app.py
app.secret_key = config.get('security', {}).get('secret_key', os.urandom(24).hex())
```

**Приоритет:** Высокий. В продакшене при каждом деплое пользователи будут разлогиниваться.

---

### 2. Rate limiting на login endpoint

**Проблема:** Нет защиты от brute-force атак на `/login`. Злоумышленник может перебирать пароли бесконечно.

**Файл:** `mes_production/web/app.py`, маршрут `/login`

**Решение:**
```bash
pip install Flask-Limiter
```
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(app, key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    ...
```

**Приоритет:** Высокий. Стандартная защита для любого endpoint с аутентификацией.

---

### 3. Валидация длины входных строк

**Проблема:** Поля `batch`, `product_code`, `color` принимаются без ограничения длины. Можно отправить строку в 10MB.

**Файл:** `mes_production/web/app.py`, `api_create_order()`

**Решение:**
```python
batch = data.get('batch', '')[:100]      # max 100 символов
product_code = data.get('product_code', '')[:100]
color = data.get('color', '')[:50]

if not batch or not product_code:
    return jsonify({'error': 'Batch and product_code required'}), 400
```

**Приоритет:** Средний. Защита от DoS через большие payload.

---

### 4. Пароль: минимальная длина и сложность

**Проблема:** Пароль может быть 1 символ. Нет проверки сложности.

**Файл:** `mes_production/web/app.py`, `change_password()`, `api_create_user()`

**Решение:**
```python
def validate_password(password: str) -> Optional[str]:
    """Validate password. Returns error message or None."""
    if len(password) < 8:
        return 'Минимальная длина пароля — 8 символов'
    if not any(c.isupper() for c in password):
        return 'Пароль должен содержать заглавную букву'
    if not any(c.isdigit() for c in password):
        return 'Пароль должен содержать цифру'
    return None
```

**Приоритет:** Средний. Стандартное требование для корпоративных систем.

---

## 🟡 Важные (качество кода и архитектура)

### 5. DRY: Общий шаблон для всех страниц

**Проблема:** `<header>` с навигацией, темой и информацией о пользователе дублируется в 5 HTML файлах.

**Файлы:** `index.html`, `tracking.html`, `station.html`, `map.html`, `users.html`

**Решение:** Создать `base.html`:
```html
<!-- web/templates/base.html -->
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token }}">
    <title>{% block title %}MES{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <header>
            <h1>🏭 MES Production System</h1>
            <div class="header-actions">
                <nav>
                    <a href="/" class="{% if request.path == '/' %}active{% endif %}">Заказы</a>
                    <a href="/tracking" class="{% if request.path == '/tracking' %}active{% endif %}">Карта станций</a>
                    <a href="/station" class="{% if request.path == '/station' %}active{% endif %}">Станция</a>
                    <a href="/map" class="{% if request.path == '/map' %}active{% endif %}">Производство</a>
                    {% if user and user.role == 'admin' %}
                    <a href="/users" class="{% if request.path == '/users' %}active{% endif %}">Пользователи</a>
                    {% endif %}
                </nav>
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="font-size:0.85rem;color:var(--text-secondary);">
                        {{ user.username }} ({{ user.role_label }})
                    </span>
                    <a href="/logout" class="btn btn-sm btn-secondary">Выйти</a>
                    <button id="themeToggle" class="theme-toggle" aria-label="Toggle theme">🌙</button>
                </div>
            </div>
        </header>

        {% block content %}{% endblock %}
    </div>

    <div class="toast-container" id="toastContainer"></div>
    <script src="{{ url_for('static', filename='theme.js') }}"></script>
    <script src="{{ url_for('static', filename='script.js') }}"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

Каждая страница:
```html
{% extends "base.html" %}
{% block title %}MES - Заказы{% endblock %}
{% block content %}
<!-- уникальный контент страницы -->
{% endblock %}
{% block scripts %}
<script src="{{ url_for('static', filename='orders.js') }}"></script>
{% endblock %}
```

**Приоритет:** Средний. Изменение навигации сейчас требует правки 5 файлов.

---

### 6. Connection pooling для SQLite

**Проблема:** Каждый метод БД открывает/закрывает соединение. При 4 потоках Waitress и авто-обновлении каждые 3 сек — высокая нагрузка.

**Файл:** `mes_production/utils/database.py`, `get_connection()`

**Решение:** Использовать `queue.Queue` для пула соединений:
```python
import queue

class Database:
    def __init__(self, db_path, logger, pool_size=4):
        self._pool = queue.Queue(maxsize=pool_size)
        for _ in range(pool_size):
            self._pool.put(self._new_connection())

    def _new_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def get_connection(self):
        return self._pool.get()

    def return_connection(self, conn):
        self._pool.put(conn)
```

Или проще — использовать один connection на поток через `threading.local()`.

**Приоритет:** Средний. Заметно при высокой нагрузке.

---

### 7. Оптимизация `get_stations()` — убрать N+1

**Проблема:** `get_stations()` делает 1 запрос для станций + N запросов для заказов (по одному на станцию).

**Файл:** `mes_production/utils/database.py`, `get_stations()`

**Текущий код:**
```python
cursor.execute('SELECT s.id, s.name FROM stations s ORDER BY s.id')
stations = [...]
for station in stations:
    cursor.execute('SELECT ... FROM orders WHERE current_station = ?', (station['id'],))
```

**Решение:** Один запрос с JOIN:
```python
cursor.execute('''
    SELECT s.id, s.name,
           o.id as order_id, o.order_number, o.product_code, o.color, o.quantity, o.batch
    FROM stations s
    LEFT JOIN orders o ON o.current_station = s.id AND o.status = 'production'
    ORDER BY s.id, o.id
''')
# Группировка в Python
```

**Приоритет:** Средний. С 13 станциями это 14 запросов каждые 3 секунды.

---

### 8. Пагинация заказов

**Проблема:** `GET /api/orders` возвращает ВСЕ заказы без лимита.

**Файл:** `mes_production/utils/database.py`, `get_orders()`

**Решение:**
```python
def get_orders(self, status=None, page=1, per_page=50):
    offset = (page - 1) * per_page
    if status:
        cursor.execute('SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ? OFFSET ?',
                       (status, per_page, offset))
    else:
        cursor.execute('SELECT * FROM orders ORDER BY id DESC LIMIT ? OFFSET ?',
                       (per_page, offset))
```

API: `GET /api/orders?page=1&per_page=50`

**Приоритет:** Средний. Станет критическим при 1000+ заказах.

---

### 9. Поиск и фильтрация заказов

**Проблема:** Только фильтр по статусу. Нет поиска по номеру, партии, товару.

**Файл:** `mes_production/utils/database.py`, `get_orders()`

**Решение:**
```python
def get_orders(self, status=None, search=None, page=1, per_page=50):
    query = 'SELECT * FROM orders WHERE 1=1'
    params = []
    if status:
        query += ' AND status = ?'
        params.append(status)
    if search:
        query += ' AND (order_number LIKE ? OR batch LIKE ? OR product_code LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    query += ' ORDER BY id DESC LIMIT ? OFFSET ?'
    params.extend([per_page, (page-1)*per_page])
    cursor.execute(query, params)
```

API: `GET /api/orders?search=ORD-0001&page=1`

**Приоритет:** Средний. Удобство для операторов.

---

## 🟢 Полезные (фичи и UX)

### 10. История заказов (Station Log)

**Проблема:** Таблица `station_log` существует но не доступна через API или UI. Нет audit trail.

**Решение:**
- API: `GET /api/orders/<id>/log` — журнал перемещений заказа
- UI: Модальное окно «История» на странице заказов
- Показывать: станция, время входа, время выхода, результат

**Приоритет:** Средний. Важно для расследования проблем.

---

### 11. Экспорт в CSV

**Проблема:** Нет возможности выгрузить заказы для отчётов.

**Решение:**
```python
@app.route('/api/orders/export', methods=['GET'])
@login_required
def export_orders():
    orders = controller.get_orders()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['№', 'Партия', 'Товар', 'Цвет', 'Статус', 'Станция', 'Создан', 'Завершён'])
    for o in orders:
        writer.writerow([o['order_number'], o['batch'], o['product_code'], ...])
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=orders.csv'})
```

**Приоритет:** Низкий. Удобно для менеджеров.

---

### 12. Completion Rate в UI

**Проблема:** `completion_rate` считается в БД но не отображается ни на одной странице.

**Решение:** Добавить 5-ю карточку статистики:
```html
<div class="stat-card">
    <div class="stat-value" id="statRate">0%</div>
    <div class="stat-label">Завершено</div>
</div>
```

**Приоритет:** Низкий. Already computed, just needs display.

---

### 13. Горячие клавиши

**Проблема:** Операторы работают мышью. Для массовых операций медленно.

**Решение:**
- `Enter` — подтвердить модалку
- `Escape` — закрыть модалку
- `L` — запустить заказ (на странице заказов)
- `M` — переместить
- `C` — завершить
- `X` — отменить

```javascript
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeModal();
    if (e.key === 'Enter' && modalActive) submitForm();
});
```

**Приоритет:** Низкий. UX-улучшение для power users.

---

### 14. Детальная страница заказа

**Проблема:** Нет страницы с полной информацией об одном заказе.

**Решение:**
- `GET /orders/<id>` — страница заказа
- Все поля, статус, текущая станция
- История перемещений
- Кнопки действий (запустить, переместить, завершить, отменить)

**Приоритет:** Низкий. Удобно для отслеживания конкретного заказа.

---

### 15. Уведомления о завершении

**Проблема:** Нет оповещения когда заказ завершается.

**Решение:**
- Toast-уведомление при автозавершении
- (Опционально) Email/webhook при завершении заказа
- Цветовая индикация в таблице заказов

**Приоритет:** Низкий. Удобно для контроля.

---

### 16. Dashboard с графиками

**Проблема:** Статистика только в виде чисел.

**Решение:** Добавить страницу `/dashboard` с:
- График заказов по дням (bar chart)
- Время прохождения каждой станции (line chart)
- Распределение по статусам (pie chart)
- Top products by volume

Использовать Chart.js или ApexCharts (CDN, без npm).

**Приоритет:** Низкий. Красиво для менеджмента.

---

### 17. Бэкап базы данных

**Проблема:** Нет механизма резервного копирования.

**Решение:**
```python
# В run.py или отдельный скрипт
import shutil
from datetime import datetime

def backup_database():
    backup_dir = 'data/backups'
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2('data/mes.db', f'{backup_dir}/mes_{timestamp}.db')
    # Удалить бэкапы старше 30 дней
```

Запускать по cron или через APScheduler.

**Приоритет:** Средний. Критично для продакшена.

---

### 18. Alembic для миграций БД

**Проблема:** Миграции в коде (`ALTER TABLE ...`) — сложно отслеживать и откатывать.

**Решение:**
```bash
pip install alembic
alembic init migrations
alembic revision --autogenerate -m "add completed_subs column"
alembic upgrade head
```

**Приоритет:** Низкий. Важно при росте команды разработчиков.

---

### 19. Docker-контейнеризация

**Проблема:** Развёртывание требует ручной настройки.

**Решение:**
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY mes_production/requirements.txt .
RUN pip install -r requirements.txt
COPY mes_production/ .
EXPOSE 5000
CMD ["python", "run.py"]
```

```yaml
# docker-compose.yml
version: '3'
services:
  mes:
    build: .
    ports: ["5000:5000"]
    volumes:
      - ./data:/app/data
    environment:
      - FLASK_ENV=production
```

**Приоритет:** Низкий. Удобно для CI/CD.

---

### 20. WebSocket / SSE для real-time обновлений

**Проблема:** Auto-refresh каждые 3 секунды — polling.

**Решение:** Server-Sent Events (SSE) — проще чем WebSocket:
```python
from flask import Response, stream_with_context

@app.route('/api/stream')
@login_required
def stream():
    def event_stream():
        while True:
            stations = controller.get_stations()
            yield f"data: {json.dumps(stations)}\n\n"
            time.sleep(2)
    return Response(stream_with_context(event_stream()),
                    mimetype='text/event-stream')
```

**Приоритет:** Низкий. Polling работает нормально для текущей нагрузки.

---

## Сводная таблица

| # | Улучшение | Категория | Приоритет | Сложность |
|---|-----------|-----------|-----------|-----------|
| 1 | Secret key в config.yaml | Безопасность | 🔴 Высокий | ⭐ |
| 2 | Rate limiting на login | Безопасность | 🔴 Высокий | ⭐⭐ |
| 3 | Валидация длины строк | Безопасность | 🟡 Средний | ⭐ |
| 4 | Валидация сложности пароля | Безопасность | 🟡 Средний | ⭐ |
| 5 | Базовый шаблон (DRY HTML) | Архитектура | 🟡 Средний | ⭐⭐ |
| 6 | Connection pooling | Производительность | 🟡 Средний | ⭐⭐⭐ |
| 7 | Оптимизация get_stations() | Производительность | 🟡 Средний | ⭐⭐ |
| 8 | Пагинация заказов | Производительность | 🟡 Средний | ⭐⭐ |
| 9 | Поиск заказов | UX | 🟡 Средний | ⭐⭐ |
| 10 | История заказов (log API) | Фича | 🟡 Средний | ⭐⭐ |
| 11 | Экспорт в CSV | Фича | 🟢 Низкий | ⭐ |
| 12 | Completion Rate в UI | UX | 🟢 Низкий | ⭐ |
| 13 | Горячие клавиши | UX | 🟢 Низкий | ⭐⭐ |
| 14 | Страница заказа | Фича | 🟢 Низкий | ⭐⭐ |
| 15 | Уведомления о завершении | Фича | 🟢 Низкий | ⭐⭐ |
| 16 | Dashboard с графиками | Фича | 🟢 Низкий | ⭐⭐⭐ |
| 17 | Бэкап БД | Инфраструктура | 🟡 Средний | ⭐ |
| 18 | Alembic миграции | Архитектура | 🟢 Низкий | ⭐⭐ |
| 19 | Docker-контейнеризация | Инфраструктура | 🟢 Низкий | ⭐⭐ |
| 20 | SSE вместо polling | Производительность | 🟢 Низкий | ⭐⭐ |
