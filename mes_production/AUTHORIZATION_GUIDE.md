# 🔐 Руководство по аутентификации и авторизации

## 📋 Содержание

1. [Обзор системы](#обзор-системы)
2. [Типы аутентификации](#типы-аутентификации)
3. [Роли и права доступа](#роли-и-права-доступа)
4. [Управление ролями](#управление-ролями)
5. [Управление пользователями](#управление-пользователями)
6. [API для аутентификации](#api-для-аутентификации)
7. [Примеры использования](#примеры-использования)

---

## 🎯 Обзор системы

MES Production System использует гибридную систему аутентификации:

| Тип | Для кого | Метод |
|-----|----------|-------|
| **Сессийная** | Люди (браузер) | Flask-Login + сессии |
| **API-ключи** | Скрипты/интеграции | Заголовок `X-API-Key` |

### Основные компоненты

```
mes_production/
├── web/
│   ├── auth.py           # API-ключи (машинная аутентификация)
│   ├── auth_user.py      # Flask-Login (пользовательская аутентификация)
│   ├── models.py         # Модели User, ROLES
│   └── app.py            # Flask приложение + API endpoints
├── utils/
│   └── permissions.py    # Права доступа (permissions)
└── data/
    └── users.db          # База данных пользователей и ролей
```

---

## 🔑 Типы аутентификации

### 1. Сессийная аутентификация (для людей)

**Как работает:**
1. Пользователь вводит логин/пароль на `/login`
2. Сервер проверяет credentials в `users.db`
3. При успехе создаётся сессия Flask-Login
4. CSRF-токен генерируется для защиты POST-запросов
5. Сессия сохраняется в cookie

**Поток аутентификации:**
```
┌─────────────┐     POST /login     ┌──────────────┐
│   Браузер   │ ──────────────────> │   Сервер     │
│             │                     │              │
│  username   │                     │  Проверка    │
│  password   │                     │  в users.db  │
│             │ <────────────────── │              │
└─────────────┘    Set-Cookie       └──────────────┘
                        session
```

**Входные данные:**
```html
POST /login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123&remember=on
```

**Ответ:**
- Успех: редирект на `/` (главная)
- Ошибка: редирект на `/login` с сообщением об ошибке

**Принудительная смена пароля:**
- При первом входе `admin` должен сменить пароль
- Перенаправление на `/change-password`
- Пароль должен быть минимум 6 символов

### 2. API-ключи (для скриптов)

**Настройка:**
```yaml
# config.yaml
auth:
  api_keys:
    - my-secret-key-123
    - another-key-456
```

**Использование:**
```bash
# Заголовок X-API-Key
curl -H "X-API-Key: my-secret-key-123" \
     http://localhost:5000/api/orders
```

**Преимущества:**
- Не требует сессий/cookies
- Не требует CSRF-токена
- Подходит для автоматизации

**Ограничения:**
- API-ключи bypass CSRF (для безопасности)
- Ключи хранятся в `config.yaml` (нужно защищать файл)

---

## 👥 Роли и права доступа

### Встроенные роли

| Роль | Уровень | Описание |
|------|---------|----------|
| `viewer` | 1 | Просмотр заказов и статистики |
| `operator` | 2 | Операционные действия (запуск, перемещение, завершение) |
| `admin` | 3 | Управление пользователями и ролями |

### Права доступа (permissions)

Права — это атомарные возможности, которые можно назначать ролям:

| Категория | Права | Описание |
|-----------|-------|----------|
| **orders** | `order_create`, `order_launch`, `order_move`, `order_complete`, `order_cancel` | Управление заказами |
| **stations** | `station_view`, `station_control` | Управление станциями |
| **users** | `user_view`, `user_create`, `user_edit`, `user_delete` | Управление пользователями |
| **roles** | `role_view`, `role_edit` | Управление ролями |

**Файл `utils/permissions.py`:**
```python
PERMISSIONS = {
    'order_create': 'Создать заказ',
    'order_launch': 'Запустить заказ',
    'order_move': 'Переместить заказ',
    'order_complete': 'Завершить заказ',
    'order_cancel': 'Отменить заказ',
    'station_view': 'Просмотр станции',
    'station_control': 'Управление станцией',
    'user_view': 'Просмотр пользователей',
    'user_create': 'Создать пользователя',
    'user_edit': 'Редактировать пользователя',
    'user_delete': 'Удалить пользователя',
    'role_view': 'Просмотр ролей',
    'role_edit': 'Редактировать роли',
}

CATEGORIES = ['orders', 'stations', 'users', 'roles']

DEFAULT_ROLE_PERMISSIONS = {
    'admin': ['order_create', 'order_launch', 'order_move', 'order_complete', 'order_cancel',
              'station_view', 'station_control',
              'user_view', 'user_create', 'user_edit', 'user_delete',
              'role_view', 'role_edit'],
    'operator': ['order_launch', 'order_move', 'order_complete', 'order_cancel',
                 'station_view', 'station_control'],
    'viewer': ['order_view', 'station_view'],
}
```

### Таблица БД: `role_permissions`

```sql
CREATE TABLE role_permissions (
    role TEXT NOT NULL,
    permission TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (role, permission)
);
```

**Особенности:**
- Кастомные роли имеют запись с `permission=''` (пустой маркер)
- Встроенные роли имеют записи с реальными правами
- Удаление роли: `DELETE FROM role_permissions WHERE role = ?`

---

## 🛠️ Управление ролями

### Создание кастомной роли

**Через UI:**
1. Войти как `admin`
2. Перейти на `/roles`
3. Ввести имя роли в поле "Новая роль"
4. Нажать "Создать роль"

**Через API:**
```bash
POST /api/roles
Content-Type: application/json
X-API-Key: my-secret-key-123

{
    "role": "supervisor"
}
```

**Ответ:**
```json
{
    "success": true,
    "role": "supervisor",
    "permissions": []
}
```

**Валидация:**
- Имя роли: только буквы и underscores (`isidentifier()`)
- Уникальность: нельзя создать дубликат
- Преобразование: имя приводится к нижнему регистру

### Редактирование прав роли

**Через UI:**
1. На странице `/roles` выбрать роль из таблицы
2. Отметить нужные права чекбоксами
3. Нажать "Сохранить"

**Через API:**
```bash
POST /api/roles/supervisor/permissions
Content-Type: application/json
X-API-Key: my-secret-key-123

{
    "permissions": [
        "order_create",
        "order_launch",
        "order_move",
        "station_view"
    ]
}
```

**Ответ:**
```json
{
    "success": true,
    "permissions": ["order_create", "order_launch", "order_move", "station_view"]
}
```

### Сброс прав роли

**Только для встроенных ролей:**
```bash
POST /api/roles/admin/permissions/reset
Content-Type: application/json
X-API-Key: my-secret-key-123
```

**Важно:**
- Сброс работает только для `admin`, `operator`, `viewer`
- Кастомные роли не имеют "дефолтных" прав
- После сброса права восстанавливаются из `DEFAULT_ROLE_PERMISSIONS`

### Удаление роли

**Через UI:**
1. На странице `/roles` нажать кнопку удаления
2. Подтвердить удаление

**Через API:**
```bash
DELETE /api/roles/supervisor
X-API-Key: my-secret-key-123
```

**Ограничения:**
- Нельзя удалить встроенные роли (`admin`, `operator`, `viewer`)
- Ответ 403 при попытке удалить built-in роль

**Важно:**
- Удаление роли НЕ удаляет пользователей с этой ролью
- Пользователи остаются с несуществующей ролью (нужно обновить)

---

## 👤 Управление пользователями

### Создание пользователя

**Через UI:**
1. Перейти на `/users` (доступно только `admin`)
2. Заполнить форму:
   - Логин (уникальный)
   - Пароль (минимум 6 символов)
   - Роль (из выпадающего списка)
3. Нажать "Создать"

**Через API:**
```bash
POST /api/users
Content-Type: application/json
X-API-Key: my-secret-key-123

{
    "username": "ivan_operator",
    "password": "securepass123",
    "role": "operator"
}
```

**Валидация:**
- `username`: требуется, уникально
- `password`: требуется, минимум 6 символов
- `role`: должен существовать в `role_permissions` (built-in или custom)

**Ответ:**
```json
{
    "success": true,
    "id": 5
}
```

### Редактирование пользователя

**Что можно изменить:**
- Роль (выбрать из доступных)
- Пароль (если нужно)
- Статус активен/неактивен

**Через API:**
```bash
POST /api/users/5
Content-Type: application/json
X-API-Key: my-secret-key-123

{
    "role": "supervisor",
    "is_active": true
}
```

**Ограничения:**
- Нельзя изменить `username` (только через БД)
- Пароль хешируется через `werkzeug.security.generate_password_hash()`

### Удаление пользователя

**Через UI:**
1. На странице `/users` нажать кнопку удаления
2. Подтвердить

**Через API:**
```bash
DELETE /api/users/5
X-API-Key: my-secret-key-123
```

**Ограничения:**
- Нельзя удалить себя (`user_id == current_user.id`)
- Ответ 400 при попытке удалить себя

---

## 📡 API для аутентификации

### Эндпоинты ролей

| Метод | Endpoint | Доступ | Описание |
|-------|----------|--------|----------|
| GET | `/api/roles` | Login | Получить все роли |
| POST | `/api/roles` | Admin | Создать роль |
| DELETE | `/api/roles/<role>` | Admin | Удалить роль |
| POST | `/api/roles/<role>/permissions` | Admin | Установить права |
| POST | `/api/roles/<role>/permissions/reset` | Admin | Сбросить права (built-in) |

**GET /api/roles:**
```json
{
    "success": true,
    "roles": [
        {"role": "admin", "label": "Администратор", "builtin": true},
        {"role": "operator", "label": "Оператор", "builtin": true},
        {"role": "viewer", "label": "Наблюдатель", "builtin": true},
        {"role": "supervisor", "label": "Supervisor", "builtin": false}
    ]
}
```

### Эндпоинты пользователей

| Метод | Endpoint | Доступ | Описание |
|-------|----------|--------|----------|
| POST | `/api/users` | Admin | Создать пользователя |
| POST | `/api/users/<id>` | Admin | Обновить пользователя |
| DELETE | `/api/users/<id>` | Admin | Удалить пользователя |

### Эндпоинты аутентификации

| Метод | Endpoint | Доступ | Описание |
|-------|----------|--------|----------|
| GET | `/login` | Public | Форма входа |
| POST | `/login` | Public | Вход с credentials |
| GET | `/logout` | Login | Выход |
| GET | `/change-password` | Login | Смена пароля |
| POST | `/change-password` | Login | Подтвердить новый пароль |

---

## 🔄 Жизненный цикл аутентификации

### Вход пользователя

```
1. Пользователь переходит на /login
2. Вводит username и password
3. Сервер проверяет в users.db:
   - SELECT * FROM users WHERE username = ?
   - check_password_hash(password_hash, password)
4. При успехе:
   - login_user(user) — Flask-Login
   - session['user_id'] = user.id
   - redirect to /
5. При ошибке:
   - flash('Неверный логин или пароль')
   - redirect to /login
```

### Проверка прав (декораторы)

**require_role('admin'):**
```python
@app.route('/users')
@login_required
@require_role('admin')
def users_page():
    # Только администраторы
    pass
```

**require_operator_or_api_key:**
```python
@app.route('/api/orders', methods=['POST'])
@require_operator_or_api_key
def api_create_order():
    # Operator или API-ключ
    pass
```

**require_permission('order_create'):**
```python
@app.route('/api/orders', methods=['POST'])
@login_required
@require_permission('order_create')
def api_create_order():
    # Нужен конкретный permission
    pass
```

### Выход пользователя

```
1. GET /logout
2. logout_user() — Flask-Login
3. session.clear()
4. redirect to /login
```

---

## 💻 Примеры использования

### Пример 1: Создание пользователя через API

```python
import requests

API_KEY = "my-secret-key-123"
BASE_URL = "http://localhost:5000"

# Создать роль
response = requests.post(
    f"{BASE_URL}/api/roles",
    json={"role": "qa_engineiner"},
    headers={"X-API-Key": API_KEY}
)
print(response.json())  # {"success": true, "role": "qa_engineiner", "permissions": []}

# Настроить права
response = requests.post(
    f"{BASE_URL}/api/roles/qa_engineiner/permissions",
    json={"permissions": ["order_view", "station_view", "order_complete"]},
    headers={"X-API-Key": API_KEY}
)
print(response.json())

# Создать пользователя
response = requests.post(
    f"{BASE_URL}/api/users",
    json={
        "username": "anna_qa",
        "password": "qa123456",
        "role": "qa_engineiner"
    },
    headers={"X-API-Key": API_KEY}
)
print(response.json())  # {"success": true, "id": 12}
```

### Пример 2: Работа с сессией (браузер)

```python
import requests

BASE_URL = "http://localhost:5000"
session = requests.Session()

# Войти
response = session.post(
    f"{BASE_URL}/login",
    data={"username": "admin", "password": "admin123"}
)
print(response.url)  # http://localhost:5000/

# Получить роли
response = session.get(f"{BASE_URL}/api/roles")
print(response.json())

# Создать пользователя
response = session.post(
    f"{BASE_URL}/api/users",
    json={"username": "test_user", "password": "test123", "role": "viewer"}
)
print(response.json())

# Выйти
response = session.get(f"{BASE_URL}/logout")
print(response.url)  # http://localhost:5000/login
```

### Пример 3: Получение списка ролей для селектора

```javascript
// users.html
async function populateRoleSelectors() {
    const response = await fetch('/api/roles');
    const data = await response.json();
    
    if (data.success) {
        const createRole = document.getElementById('createRole');
        const editRole = document.getElementById('editRole');
        
        data.roles.forEach(r => {
            const option = document.createElement('option');
            option.value = r.role;
            option.textContent = r.label + (r.builtin ? ' (встроенная)' : ' (кастомная)');
            createRole.appendChild(option.cloneNode(true));
            editRole.appendChild(option.cloneNode(true));
        });
    }
}
```

---

## 🔒 Безопасность

### Хранение паролей

- Пароли хешируются через `werkzeug.security.generate_password_hash()`
- Используется PBKDF2 с SHA-256
- Соль генерируется автоматически

### CSRF-защита

- Все POST-запросы от сессионных пользователей требуют CSRF-токен
- API-ключи bypass CSRF (для скриптов)
- Токен генерируется через `secrets.token_hex(16)`

### Защита от перебора

- Не реализована (можно добавить позже)
- Рекомендация: использовать fail2ban или аналогичные решения

### API-ключи

- Хранятся в `config.yaml` (не в БД)
- Не логируются
- Рекомендуется использовать уникальные ключи для каждого клиента

---

## 🐛 Решение проблем

### Ошибка: "Invalid role. Role 'xxx' does not exist"

**Причина:**
- Роль не существует в `role_permissions`
- Опечатка в имени роли

**Решение:**
```sql
-- Проверить существующие роли
SELECT DISTINCT role FROM role_permissions;

-- Создать роль, если её нет
INSERT INTO role_permissions (role, permission) VALUES ('xxx', '');
```

### Ошибка: "CSRF token missing"

**Причина:**
- POST без CSRF-токена от сессионного пользователя

**Решение:**
```html
<!-- В форме -->
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
```

### Ошибка: "Cannot delete built-in roles"

**Причина:**
- Попытка удалить `admin`, `operator` или `viewer`

**Решение:**
- Создайте кастомную роль вместо этого
- Используйте кастомную роль для назначения пользователям

---

## 📚 Дополнительные ресурсы

- `AUTH_IMPLEMENTATION.md` — техническая документация по реализации
- `KODA.md` — общий контекст проекта
- `utils/permissions.py` — список всех прав доступа
- `web/auth_user.py` — код Flask-Login интеграции
- `web/auth.py` — код API-ключей

---

*Документация создана для MES Production System*
*Версия: 1.0*
*Дата: 2026-04-17*
