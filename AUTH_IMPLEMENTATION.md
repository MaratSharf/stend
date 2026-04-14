# Аутентификация и авторизация пользователей с ролями

## Вариант 1 — Простая форма логин/пароль с сессиями ✅ Рекомендую

**Технологии:** Flask-Login + Werkzeug `generate_password_hash` + SQLite (таблица `users`)

```bash
pip install Flask-Login
```

### Как работает

| Компонент | Что делает |
|-----------|-----------|
| **Flask-Login** | Управление сессиями, `@login_required`, `current_user` |
| **Werkzeug** | Хеширование паролей (pbkdf2, уже в зависимостях Flask) |
| **SQLite** | Таблица `users` — логин, хеш пароля, роль |

### Роли

```python
class Role:
    ADMIN = 'admin'        # управление пользователями + всё остальное
    OPERATOR = 'operator'  # создание заказов, запуск, перемещение
    VIEWER = 'viewer'      # только чтение (GET)
```

### Структура БД

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    password_hash TEXT,
    role TEXT DEFAULT 'viewer',
    is_active INTEGER DEFAULT 1,
    created_at TEXT
);
```

### Что нужно сделать

1. Добавить модель `User` (наследуется от `UserMixin`)
2. Страницы `/login`, `/logout`, `/register` (только admin)
3. Декоратор `@require_role('admin')` поверх `@login_required`
4. API-ключ оставить для машинных запросов (curl, скрипты), а пользователей — через сессии

### Плюсы

- ✅ Минимум зависимостей — только Flask-Login
- ✅ Сессии хранятся в signed cookie — не нужна дополнительная БД
- ✅ `@login_required` — встроенный декоратор
- ✅ Работает без HTTPS в локальной сети (но для продакшена нужен HTTPS)

### Минусы

- ❌ Нет JWT — только cookie-based (не подходит для мобильных приложений)
- ❌ Нет OAuth2/SSO — только логин/пароль

### Оценка

~200 строк кода, 1 новая зависимость. Идеально для вашего масштаба.

---

## Вариант 2 — Flask-Security-Too (полноценное решение)

**Технологии:** `flask-security-too` (форк Flask-Security)

```bash
pip install Flask-Security-Too
```

### Что даёт из коробки

- ✅ Регистрация, логин, logout, восстановление пароля
- ✅ Роли и permissions (`@roles_required('admin')`)
- ✅ Подтверждение email (опционально)
- ✅ CSRF защита
- ✅ Сессии + remember-me

### Минусы

- ❌ Тяжёлая зависимость — тянет Flask-Mail, Flask-Principal, passlib
- ❌ Много «магии» — сложнее кастомизировать
- ❌ Для внутренней системы (MES на заводе) половина фич избыточна

### Оценка

Не рекомендую для вашего проекта — overkill.

---

## Вариант 3 — JWT токены (для API-first)

**Технологии:** `PyJWT` или `Flask-JWT-Extended`

```bash
pip install Flask-JWT-Extended
```

### Как работает

```
POST /api/auth/login  →  { username, password }  →  { access_token }
Все запросы           →  Header: Authorization: Bearer <token>
```

### Роли в токене

```json
{
  "sub": "user_id",
  "role": "operator",
  "exp": 1713456789
}
```

### Плюсы

- ✅ Stateless — работает с load balancer
- ✅ Подходит для мобильных приложений и SPA
- ✅ Токен можно передать в заголовке

### Минусы

- ❌ Нет встроенной работы с сессиями (нужен свой механизм инвалидации)
- ❌ Сложнее для фронтенда (хранить токен, обрабатывать refresh)
- ❌ Избыточно для одной машины/локальной сети

### Оценка

Имеет смысл только если будете делать SPA (React/Vue) или мобильное приложение.

---

## Вариант 4 — OAuth2 / OIDC (Keycloak, Google, etc.)

**Технологии:** `Authlib` + внешний провайдер

### Плюсы

- ✅ Единый вход (SSO) для всей компании
- ✅ Не нужно хранить пароли
- ✅ 2FA из коробки (если провайдер поддерживает)

### Минусы

- ❌ Нужен внешний сервер (Keycloak, Okta, Google)
- ❌ Сложная настройка
- ❌ Зависимость от внешнего сервиса

### Оценка

Имеет смысл только если в компании уже есть Keycloak/AD/SSO.

---

## Сравнение вариантов

| Критерий | Flask-Login | Flask-Security-Too | JWT | OAuth2 |
|----------|-------------|-------------------|-----|--------|
| Сложность | ⭐ 1/5 | ⭐ 3/5 | ⭐ 3/5 | ⭐ 5/5 |
| Зависимости | 1 | 5+ | 1-2 | 1+ |
| Подходит для MES | ⭐ 5/5 | ⭐ 4/5 | ⭐ 3/5 | ⭐ 4/5 |
| Мобильные приложения | ❌ | ❌ | ✅ | ✅ |
| SSO | ❌ | ❌ | ❌ | ✅ |
| Гибкость | Высокая | Низкая | Средняя | Высокая |

---

## Рекомендация: Вариант 1 — Flask-Login

### Почему

| Критерий | Оценка |
|----------|--------|
| Сложность внедрения | ⭐ 1/5 |
| Подходит для MES | ⭐ 5/5 |
| Покрывает потребности | ⭐ 5/5 |
| Лишние зависимости | 0 |

### План реализации

1. **Миграция БД** — таблица `users` + `roles`
2. **Модель User** — Flask-Login `UserMixin`
3. **Страницы** — `/login` (шаблон + JS), `/logout`
4. **Декоратор ролей** — `@require_role('admin')`
5. **Разделение маршрутов:**
   - `/login`, `/logout` — для людей (сессии)
   - `/api/*` — оставить API-ключ для машин
6. **Первый пользователь** — создаётся при инициализации (admin/admin, сменить при первом входе)

### Схема авторизации

```
Человек → браузер → сессия (cookie) → @login_required → страница
Скрипт  → curl     → X-API-Key     → @require_api_key → /api/orders
```

### Пример структуры файлов

```
mes_production/
├── web/
│   ├── app.py
│   ├── auth.py          # API key middleware (уже есть)
│   ├── auth_user.py     # Flask-Login + user auth
│   ├── models.py        # User model (UserMixin)
│   ├── templates/
│   │   ├── login.html   # Страница входа
│   │   └── users.html   # Управление пользователями (admin only)
│   └── static/
│       └── login.js     # Логика страницы входа
└── utils/
    └── database.py      # Добавить init_users_table()
```

### Пример кода — User модель

```python
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin):
    def __init__(self, id, username, password_hash, role='viewer'):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_operator(self):
        return self.role in ('admin', 'operator')
```

### Пример кода — декоратор ролей

```python
from functools import wraps
from flask import abort
from flask_login import current_user

def require_role(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role != role and role != 'viewer':
                # admin > operator > viewer
                roles_hierarchy = {'admin': 3, 'operator': 2, 'viewer': 1}
                if roles_hierarchy.get(current_user.role, 0) < roles_hierarchy.get(role, 0):
                    abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

### Пример использования

```python
@app.route('/api/orders', methods=['POST'])
@login_required
@require_role('operator')
def api_create_order():
    # Только оператор и админ могут создавать заказы
    ...

@app.route('/api/orders', methods=['GET'])
@login_required
def api_get_orders():
    # Все авторизованные пользователи могут читать
    ...
```
