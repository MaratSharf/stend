"""
MES Production System - Permissions utility
Defines available permissions and provides helpers for checking user access.
"""
from typing import List, Dict, Any, Set

# Define all available permissions in the system
PERMISSIONS = {
    'view_orders': {
        'label': 'Просмотр заказов',
        'description': 'Просмотр списка и деталей заказов',
        'category': 'orders'
    },
    'create_order': {
        'label': 'Создание заказов',
        'description': 'Создание новых производственных заказов',
        'category': 'orders'
    },
    'launch_order': {
        'label': 'Запуск в производство',
        'description': 'Запуск заказа в производственный процесс',
        'category': 'orders'
    },
    'move_order': {
        'label': 'Перемещение заказов',
        'description': 'Перемещение заказа между станциями',
        'category': 'orders'
    },
    'complete_order': {
        'label': 'Завершение заказа',
        'description': 'Ручное завершение заказа',
        'category': 'orders'
    },
    'cancel_order': {
        'label': 'Отмена заказа',
        'description': 'Отмена заказа в любом статусе',
        'category': 'orders'
    },
    'view_stations': {
        'label': 'Просмотр станций',
        'description': 'Просмотр статуса рабочих станций',
        'category': 'stations'
    },
    'manage_stations': {
        'label': 'Управление станциями',
        'description': 'Настройка конфигурации станций',
        'category': 'stations'
    },
    'view_statistics': {
        'label': 'Просмотр статистики',
        'description': 'Просмотр производственной статистики',
        'category': 'statistics'
    },
    'export_data': {
        'label': 'Экспорт данных',
        'description': 'Экспорт данных в CSV/Excel',
        'category': 'data'
    },
    'manage_users': {
        'label': 'Управление пользователями',
        'description': 'Создание, редактирование и удаление пользователей',
        'category': 'admin'
    },
    'manage_roles': {
        'label': 'Управление ролями',
        'description': 'Настройка прав для ролей пользователей',
        'category': 'admin'
    },
    'view_logs': {
        'label': 'Просмотр логов',
        'description': 'Просмотр системных логов',
        'category': 'admin'
    },
}

# Permission categories for UI grouping
CATEGORIES = {
    'orders': 'Заказы',
    'stations': 'Станции',
    'statistics': 'Статистика',
    'data': 'Данные',
    'admin': 'Администрирование',
}

# Default role permission assignments
DEFAULT_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    'viewer': [
        'view_orders',
        'view_stations',
        'view_statistics',
    ],
    'operator': [
        'view_orders',
        'create_order',
        'launch_order',
        'move_order',
        'complete_order',
        'cancel_order',
        'view_stations',
        'view_statistics',
    ],
    'admin': list(PERMISSIONS.keys()),  # All permissions
}


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
    return DEFAULT_ROLE_PERMISSIONS.get(role, []).copy()
