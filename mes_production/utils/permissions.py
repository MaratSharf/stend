"""
MES Production System - Permissions utility
Defines available permissions and provides helpers for checking user access.
"""
from typing import List, Dict, Any, Set

# Define all available permissions in the system
# Each permission is linked to a screen (parent_permission)
PERMISSIONS = {
    # Screen access permissions (parent permissions)
    'order_view': {
        'label': 'Экран: Заказы',
        'description': 'Доступ к странице заказов',
        'category': 'screens',
        'parent': None,
        'screen_id': 'orders'
    },
    'production_view': {
        'label': 'Экран: Производство',
        'description': 'Доступ к странице производства (статус заказов на станциях)',
        'category': 'screens',
        'parent': None,
        'screen_id': 'production'
    },
    'map_view': {
        'label': 'Экран: Карта станций',
        'description': 'Доступ к SVG-карте производственного конвейера',
        'category': 'screens',
        'parent': None,
        'screen_id': 'map'
    },
    'station_view': {
        'label': 'Экран: Станции',
        'description': 'Доступ к странице трекинга станций',
        'category': 'screens',
        'parent': None,
        'screen_id': 'tracking'
    },
    'user_view': {
        'label': 'Экран: Пользователи',
        'description': 'Доступ к странице управления пользователями',
        'category': 'screens',
        'parent': None,
        'screen_id': 'users'
    },
    'role_view': {
        'label': 'Экран: Роли',
        'description': 'Доступ к странице управления ролями',
        'category': 'screens',
        'parent': None,
        'screen_id': 'roles'
    },
    # Order operations (children of order_view)
    'create_order': {
        'label': 'Создание заказов',
        'description': 'Создание новых производственных заказов',
        'category': 'orders',
        'parent': 'order_view',
        'screen_id': 'orders'
    },
    'launch_order': {
        'label': 'Запуск в производство',
        'description': 'Запуск заказа в производственный процесс',
        'category': 'orders',
        'parent': 'order_view',
        'screen_id': 'orders'
    },
    'move_order': {
        'label': 'Перемещение заказов',
        'description': 'Перемещение заказа между станциями',
        'category': 'orders',
        'parent': 'order_view',
        'screen_id': 'orders'
    },
    'complete_order': {
        'label': 'Завершение заказа',
        'description': 'Ручное завершение заказа',
        'category': 'orders',
        'parent': 'order_view',
        'screen_id': 'orders'
    },
    'cancel_order': {
        'label': 'Отмена заказа',
        'description': 'Отмена заказа в любом статусе',
        'category': 'orders',
        'parent': 'order_view',
        'screen_id': 'orders'
    },
    # Station operations (children of station_view)
    'manage_stations': {
        'label': 'Управление станциями',
        'description': 'Настройка конфигурации станций',
        'category': 'stations',
        'parent': 'station_view',
        'screen_id': 'stations'
    },
    # Statistics and data (standalone or children)
    'view_statistics': {
        'label': 'Просмотр статистики',
        'description': 'Просмотр производственной статистики',
        'category': 'statistics',
        'parent': None,
        'screen_id': 'statistics'
    },
    'export_data': {
        'label': 'Экспорт данных',
        'description': 'Экспорт данных в CSV/Excel',
        'category': 'data',
        'parent': None,
        'screen_id': 'data'
    },
    # Admin operations (children of user_view/role_view)
    'manage_users': {
        'label': 'Управление пользователями',
        'description': 'Создание, редактирование и удаление пользователей',
        'category': 'admin',
        'parent': 'user_view',
        'screen_id': 'users'
    },
    'manage_roles': {
        'label': 'Управление ролями',
        'description': 'Настройка прав для ролей пользователей',
        'category': 'admin',
        'parent': 'role_view',
        'screen_id': 'roles'
    },
    'view_logs': {
        'label': 'Просмотр логов',
        'description': 'Просмотр системных логов',
        'category': 'admin',
        'parent': None,
        'screen_id': 'logs'
    },
}

# Permission categories for UI grouping
CATEGORIES = {
    'screens': 'Экраны',
    'orders': 'Заказы',
    'stations': 'Станции',
    'statistics': 'Статистика',
    'data': 'Данные',
    'admin': 'Администрирование',
}

# Screen structure for UI (ordered list of screens with their operations)
SCREENS = {
    'orders': {
        'label': 'Заказы',
        'main_permission': 'order_view',
        'operations': ['create_order', 'launch_order', 'move_order', 'complete_order', 'cancel_order']
    },
    'production': {
        'label': 'Производство',
        'main_permission': 'production_view',
        'operations': []
    },
    'map': {
        'label': 'Карта станций',
        'main_permission': 'map_view',
        'operations': []
    },
    'tracking': {
        'label': 'Трекинг станций',
        'main_permission': 'station_view',
        'operations': ['manage_stations']
    },
    'users': {
        'label': 'Пользователи',
        'main_permission': 'user_view',
        'operations': ['manage_users']
    },
    'roles': {
        'label': 'Роли',
        'main_permission': 'role_view',
        'operations': ['manage_roles']
    },
    'statistics': {
        'label': 'Статистика',
        'main_permission': 'view_statistics',
        'operations': []
    },
    'data': {
        'label': 'Данные',
        'main_permission': 'export_data',
        'operations': []
    },
    'logs': {
        'label': 'Логи',
        'main_permission': 'view_logs',
        'operations': []
    },
}

# Default role permission assignments
DEFAULT_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    'viewer': [
        'order_view',
        'production_view',
        'map_view',
        'station_view',
        'view_statistics',
    ],
    'operator': [
        'order_view',
        'production_view',
        'map_view',
        'station_view',
        'create_order',
        'launch_order',
        'move_order',
        'complete_order',
        'cancel_order',
        'view_statistics',
    ],
    'admin': list(PERMISSIONS.keys()),  # All permissions
    'oper': [  # Alternative operator account - same as operator
        'order_view',
        'production_view',
        'map_view',
        'station_view',
        'create_order',
        'launch_order',
        'move_order',
        'complete_order',
        'cancel_order',
        'view_statistics',
    ],
    'viewer_only': [  # Read-only role - can view all screens but not modify orders
        'order_view',
        'production_view',
        'map_view',
        'station_view',
        'view_statistics',
    ],
    # Default permissions for any new custom role - ensures basic access
    'default': [
        'production_view',
        'map_view',
        'station_view',
        'view_statistics',
    ],
}


def get_role_default_permissions(role: str) -> List[str]:
    """Get default permissions for a role, ensuring consistency."""
    defaults = DEFAULT_ROLE_PERMISSIONS.get(role, []).copy()
    
    # If role is not in the predefined list, use 'default' permissions
    if not defaults and role != 'admin':
        defaults = DEFAULT_ROLE_PERMISSIONS.get('default', []).copy()
    
    # Ensure viewer can only view, not create/modify orders
    if role == 'viewer':
        # Remove any write permissions if accidentally added
        write_perms = ['create_order', 'launch_order', 'move_order', 'complete_order', 
                       'cancel_order', 'manage_users', 'manage_roles', 'manage_stations']
        defaults = [p for p in defaults if p not in write_perms]
    
    # Ensure operator has all necessary order operation permissions
    if role == 'operator':
        required_order_perms = ['create_order', 'launch_order', 'move_order', 
                                'complete_order', 'cancel_order']
        for perm in required_order_perms:
            if perm not in defaults:
                defaults.append(perm)
    
    return defaults


def get_permission_categories() -> List[str]:
    """Return list of permission category keys."""
    return list(CATEGORIES.keys())


def get_permissions_by_category(category: str) -> List[Dict[str, str]]:
    """Return permissions grouped by category."""
    return [
        {'key': k, **v}
        for k, v in PERMISSIONS.items()
        if v.get('category') == category
    ]


def get_all_permissions() -> List[Dict[str, str]]:
    """Return all permissions with metadata."""
    return [{'key': k, **v} for k, v in PERMISSIONS.items()]


def get_default_permissions_for_role(role: str) -> List[str]:
    """Return default permission keys for a role."""
    defaults = DEFAULT_ROLE_PERMISSIONS.get(role, []).copy()
    # If role is not in the predefined list, use 'default' permissions
    if not defaults and role != 'admin':
        defaults = DEFAULT_ROLE_PERMISSIONS.get('default', []).copy()
    return defaults
