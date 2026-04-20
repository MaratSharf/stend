# План улучшения системы управления ролями

## Текущее состояние (анализ)

### Модель данных
- **Таблица `users`**: содержит базовые поля (id, username, password_hash, role, is_active, password_changed, created_at)
- **Таблица `role_permissions`**: связывает роли с разрешениями (role, permission)
- **Роли хранятся как строки** в поле `role` таблицы users и role_permissions
- **Нет отдельной таблицы ролей** — роли существуют только через записи в role_permissions
- **Разрешения определены в коде** (utils/permissions.py), не в БД

### Проблемы текущей архитектуры

1. **Отсутствие таблицы ролей**:
   - Нельзя хранить метаданные о роли (описание, дату создания, создателя)
   - Нет возможности отслеживать историю изменений ролей
   - Сложно реализовать наследование прав между ролями
   - Невозможно мягкое удаление ролей (архивирование)

2. **Отсутствие аудита**:
   - Логируются только факты изменений, но не детали (что было → что стало)
   - Нет истории кто и когда изменял права роли
   - Нет возможности откатить изменения

3. **Ограниченный функционал управления**:
   - Нет клонирования ролей
   - Нет проверки зависимостей перед удалением (сколько пользователей имеют эту роль?)
   - Нет массового назначения прав
   - Нет группировки разрешений по сущностям (Заказы, Станции, Пользователи, Роли)

4. **Дублирование кода подключения к БД**:
   - В каждом методе создаётся новое соединение sqlite3.connect()
   - Нет централизованного сервиса для работы с ролями

---

## Улучшение модели данных

### 1. Новая схема базы данных

```sql
-- Таблица ролей (новая)
CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,           -- 'admin', 'operator', 'viewer', 'manager'
    label TEXT NOT NULL,                 -- 'Администратор', 'Оператор', ...
    description TEXT,                    -- Описание роли
    is_builtin INTEGER DEFAULT 0,        -- 1 для системных ролей (нельзя удалить)
    is_active INTEGER DEFAULT 1,         -- Для архивирования без удаления
    parent_role_id INTEGER,              -- Для наследования прав (nullable)
    created_at TEXT NOT NULL,
    created_by INTEGER,                  -- ID пользователя-создателя
    updated_at TEXT,
    updated_by INTEGER,
    FOREIGN KEY (parent_role_id) REFERENCES roles(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    FOREIGN KEY (updated_by) REFERENCES users(id)
);

-- Модифицированная таблица role_permissions
CREATE TABLE role_permissions_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL,            -- Ссылка на roles.id вместо строки
    permission TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    granted_by INTEGER,                  -- Кто выдал право
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES users(id),
    UNIQUE(role_id, permission)
);

-- Таблица аудита изменений ролей (новая)
CREATE TABLE role_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL,
    action TEXT NOT NULL,                -- 'created', 'updated', 'deleted', 'permission_added', 'permission_removed'
    old_value TEXT,                      -- JSON со старыми значениями
    new_value TEXT,                      -- JSON с новыми значениями
    changed_by INTEGER NOT NULL,
    changed_at TEXT NOT NULL,
    ip_address TEXT,
    FOREIGN KEY (role_id) REFERENCES roles(id),
    FOREIGN KEY (changed_by) REFERENCES users(id)
);

-- Индекс для быстрого поиска пользователей по роли
CREATE INDEX idx_users_role ON users(role);

-- Миграция данных:
-- 1. Создать таблицу roles
-- 2. Заполнить из существующих записей role_permissions
-- 3. Обновить role_permissions для использования role_id
-- 4. Сохранить обратную совместимость на период миграции
```

### 2. Обновление модели User

Добавить в `models.py`:
- Кэширование прав пользователя (избегать запроса к БД при каждой проверке)
- Метод для получения наследованных прав (если реализовано наследование)
- Валидацию роли при создании/изменении

---

## Улучшение функционала управления ролями

### 1. Сервисный слой (новый файл `utils/role_service.py`)

```python
class RoleService:
    """Централизованный сервис для управления ролями"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_connection(self):
        """Получить соединение с БД (единая точка)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_role(self, name: str, label: str, description: str = None, 
                    parent_role: str = None, created_by: int = None) -> dict:
        """Создание новой роли с аудитом"""
        
    def clone_role(self, source_role: str, new_name: str, new_label: str, 
                   created_by: int = None) -> dict:
        """Клонирование существующей роли"""
        
    def delete_role(self, role_name: str, force: bool = False) -> dict:
        """Удаление роли с проверкой зависимостей"""
        # Проверить, есть ли пользователи с этой ролью
        # Если есть — вернуть ошибку или предложить переназначить
        
    def update_permissions(self, role_name: str, permissions: List[str], 
                          changed_by: int = None) -> dict:
        """Обновление прав роли с аудитом"""
        
    def get_role_dependencies(self, role_name: str) -> dict:
        """Получить информацию о зависимостях роли"""
        return {
            'users_count': ...,      # Сколько пользователей имеют эту роль
            'child_roles': [...],    # Дочерние роли (если есть наследование)
            'permissions_count': ... # Количество прав
        }
    
    def get_audit_log(self, role_name: str = None, limit: int = 50) -> List[dict]:
        """Получить журнал аудита"""
```

### 2. Расширение API (добавить в `app.py`)

```python
# Клонирование роли
@app.route('/api/roles/<role>/clone', methods=['POST'])
@login_required
@require_role('admin')
def api_clone_role(role: str):
    data = request.get_json()
    new_name = data.get('new_name')
    new_label = data.get('new_label')
    # Использовать RoleService.clone_role()

# Проверка зависимостей перед удалением
@app.route('/api/roles/<role>/dependencies', methods=['GET'])
@login_required
@require_permission('role_view')
def api_get_role_dependencies(role: str):
    # Вернуть информацию о пользователях с этой ролью

# Журнал аудита
@app.route('/api/roles/audit', methods=['GET'])
@login_required
@require_role('admin')
def api_get_role_audit():
    role_filter = request.args.get('role')
    # Вернуть последние изменения

# Массовое обновление прав (несколько ролей сразу)
@app.route('/api/roles/permissions/bulk', methods=['POST'])
@login_required
@require_role('admin')
def api_bulk_update_permissions():
    data = request.get_json()
    # data = {'roles': ['role1', 'role2'], 'add_permissions': [...], 'remove_permissions': [...]}
```

### 3. Улучшение интерфейса (`roles.html`)

#### Добавить функции:
1. **Кнопка "Клонировать роль"**:
   - Открывает модальное окно с предложением ввести новое имя
   - Автоматически копирует все права

2. **Индикатор зависимостей**:
   - При выборе роли показывать: "Эту роль имеют N пользователей"
   - При попытке удаления — предупреждение со списком пользователей

3. **Вкладка "История изменений"**:
   - Таблица с последними изменениями (кто, когда, что изменил)
   - Возможность отфильтровать по роли

4. **Группировка разрешений по экранам**:
   - Заказы (order_view + операции)
   - Станции (station_view + manage_stations)
   - Пользователи (user_view + manage_users)
   - Роли (role_view + manage_roles)
   - Производство (новые права для производственных операций)
   - Карта станций (права для просмотра карты)

5. **Чекбокс "Выбрать все для экрана"**:
   - При активации order_view автоматически выбирать все операции с заказами

6. **Визуальные индикаторы**:
   - Подсветка обязательных прав (без которых экран не работает)
   - Предупреждения о конфликтующих правах

### 4. Валидация и бизнес-правила

```python
# Правила для ролей
ROLE_CONSTRAINTS = {
    'builtin_roles': ['admin', 'operator', 'viewer'],  # Нельзя удалить
    'min_admin_count': 1,  # Всегда должен быть хотя бы 1 админ
    'protected_permissions': ['manage_roles', 'manage_users'],  # Требуют осторожности
}

def validate_role_changes(role: str, changes: dict) -> Tuple[bool, str]:
    """Проверка допустимости изменений"""
    # Нельзя удалить последнее право manage_roles у всех ролей
    # Нельзя создать роль без имени
    # Нельзя назначить несуществующее право
```

---

## План реализации (поэтапно)

### Этап 1: Подготовка (без нарушения работы)
1. ✅ Анализ текущего кода (выполнено)
2. Создать файл миграции БД (`migrate_roles_schema.py`)
3. Добавить таблицу `roles` без удаления старой логики
4. Реализовать двойную запись (в старую и новую схему)

### Этап 2: Сервисный слой
1. Создать `utils/role_service.py`
2. Создать `utils/audit_service.py` для журнала изменений
3. Написать тесты для сервиса

### Этап 3: Обновление backend API
1. Добавить endpoints для клонирования, аудита, проверки зависимостей
2. Обновить существующие endpoints для использования RoleService
3. Добавить валидацию и обработку ошибок

### Этап 4: Обновление frontend
1. Добавить кнопку "Клонировать" в интерфейс ролей
2. Добавить отображение зависимостей роли
3. Создать страницу/модальное окно "История изменений"
4. Улучшить группировку прав по экранам (Заказы, Станции, Производство, Пользователи, Роли)
5. Добавить чекбоксы "Выбрать все для экрана"

### Этап 5: Миграция и очистка
1. Перенести все данные в новую схему
2. Обновить модель User для работы с role_id
3. Удалить поддержку старой схемы
4. Обновить документацию

---

## Ожидаемые преимущества

1. **Безопасность**: Полный аудит всех изменений прав доступа
2. **Гибкость**: Наследование ролей, клонирование, массовые операции
3. **Надёжность**: Проверка зависимостей предотвращает случайное удаление активных ролей
4. **Удобство**: Группировка прав по сущностям (Заказы, Станции, Производство, Пользователи, Роли)
5. **Поддерживаемость**: Централизованный сервис вместо дублирования кода БД
6. **Масштабируемость**: Легко добавлять новые права и роли

---

## Примечания по модулям системы

Для модулей **Заказы**, **Карта станций**, **Станция**, **Производство**, **Пользователи**, **Роли** рекомендуется:

1. **Заказы**:
   - screen: `order_view`
   - operations: `create_order`, `launch_order`, `move_order`, `complete_order`, `cancel_order`
   - Добавить: `edit_order`, `delete_order`, `view_order_history`

2. **Карта станций / Станция / Производство**:
   - Разделить права на просмотр карты и управление станциями
   - Добавить: `view_station_map`, `configure_station`, `start_production`, `stop_production`

3. **Пользователи**:
   - screen: `user_view`
   - operations: `manage_users`, `activate_user`, `deactivate_user`, `reset_user_password`

4. **Роли**:
   - screen: `role_view`
   - operations: `manage_roles`, `clone_role`, `view_role_audit`
