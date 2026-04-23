# Руководство по системе ролей и пользователей MES

## Обзор изменений

Система управления ролями и пользователями была полностью переработана для предотвращения проблем с доступом при создании новых ролей.

## Основные изменения

### 1. Умная система перенаправления после входа

Теперь перенаправление пользователя после входа определяется **на основе фактических разрешений**, а не только названия роли:

**Приоритет перенаправления:**
1. `order_view` → страница заказов (`/`)
2. `map_view` + `production_view` (без `order_view`) → карта станций (`/map`)
3. `production_view` → производство (`/station`)
4. `map_view` → карта станций (`/map`)
5. `station_view` → трекинг станций (`/tracking`)
6. `view_statistics` → статистика
7. `user_view` → пользователи
8. `role_view` → роли

### 2. Автоматические разрешения по умолчанию для новых ролей

При создании новой роли без указания разрешений, система автоматически назначает базовые права просмотра:

```python
default_permissions = [
    'production_view',  # Просмотр производства
    'map_view',         # Карта станций
    'station_view',     # Трекинг станций
    'view_statistics',  # Статистика
]
```

Это гарантирует, что новая роль не будет заблокирована и сможет accessing至少 одну страницу.

### 3. Логика перенаправления для специальных ролей

- **Роли с доступом к заказам** (`order_view`): перенаправляются на главную страницу со списком заказов
- **Роли только для производства** (с `map_view` + `production_view`, но без `order_view`): перенаправляются на карту станций
- **Роли только для просмотра карты**: перенаправляются на карту станций
- **Роли только для производства**: перенаправляются на страницу производства

## Примеры использования

### Создание роли только для просмотра производства (как роль 'w')

```bash
# Через API
curl -X POST http://localhost:5000/api/roles \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "role": "production_viewer",
    "permissions": ["production_view", "map_view"]
  }'
```

Пользователь с этой ролью будет автоматически перенаправлен на `/map` после входа.

### Создание оператора с полными правами

```bash
curl -X POST http://localhost:5000/api/roles \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "role": "senior_operator",
    "permissions": [
      "order_view",
      "production_view",
      "map_view",
      "station_view",
      "create_order",
      "launch_order",
      "move_order",
      "complete_order",
      "cancel_order",
      "view_statistics"
    ]
  }'
```

Пользователь с этой ролью будет перенаправлен на `/` (заказы) после входа.

### Создание роли только для карты станций

```bash
curl -X POST http://localhost:5000/api/roles \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "role": "map_viewer",
    "permissions": ["map_view"]
  }'
```

Пользователь будет перенаправлен на `/map`.

## Встроенные роли

| Роль | Разрешения | Перенаправление |
|------|-----------|-----------------|
| `admin` | Все разрешения | `/` (заказы) |
| `operator` | Заказы + операции | `/` (заказы) |
| `viewer` | Просмотр всех экранов | `/` (заказы) |
| `oper` | Альтернативный оператор | `/` (заказы) |
| `viewer_only` | Только просмотр | `/` (заказы) |

## Проверка прав доступа

Для проверки прав пользователя:

```python
from web.auth_user import get_user_permissions

perms = get_user_permissions(user_id)
print(f"Разрешения пользователя: {perms}")

# Определение страницы для перенаправления
if 'order_view' in perms:
    redirect_page = '/'
elif 'map_view' in perms and 'production_view' in perms:
    redirect_page = '/map'
elif 'production_view' in perms:
    redirect_page = '/station'
# и т.д.
```

## API эндпоинты

### Управление ролями

- `GET /api/roles` - Получить все роли
- `POST /api/roles` - Создать новую роль
- `PUT /api/roles/<role>` - Обновить разрешения роли
- `DELETE /api/roles/<role>` - Удалить роль
- `POST /api/roles/<role>/permissions` - Установить разрешения для роли
- `POST /api/roles/<role>/permissions/reset` - Сбросить разрешения к значениям по умолчанию

### Управление пользователями

- `GET /api/users` - Получить всех пользователей
- `POST /api/users` - Создать пользователя
- `POST /api/users/<id>` - Обновить пользователя
- `DELETE /api/users/<id>` - Удалить пользователя

## Предотвращение проблем

Система теперь автоматически:

1. ✅ Назначает базовые разрешения новым ролям
2. ✅ Проверяет существование роли перед назначением пользователю
3. ✅ Определяет правильную страницу для перенаправления на основе разрешений
4. ✅ Предлагает создать роль с разрешениями по умолчанию при создании пользователя с несуществующей ролью
5. ✅ Валидирует все разрешения перед сохранением

## Тестирование

Для тестирования системы:

```bash
cd mes_production
python -c "
import sqlite3
conn = sqlite3.connect('data/users.db')
cursor = conn.cursor()

# Проверка ролей
cursor.execute('SELECT DISTINCT role FROM role_permissions ORDER BY role')
roles = [r[0] for r in cursor.fetchall()]
print('Роли в системе:', roles)

# Проверка пользователя
cursor.execute('SELECT username, role FROM users')
users = cursor.fetchall()
for user in users:
    cursor.execute('SELECT permission FROM role_permissions WHERE role = ?', (user[1],))
    perms = [r[0] for r in cursor.fetchall()]
    print(f'{user[0]} (роль {user[1]}): {len(perms)} разрешений')

conn.close()
"
```
