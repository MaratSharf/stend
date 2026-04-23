"""
MES Production System - User model for Flask-Login.
"""
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Role hierarchy — higher number = more permissions
# Note: Custom roles (like 'oper', 'viewer_only') are checked dynamically via role_permissions table
ROLES = {
    'viewer': 1,
    'operator': 2,
    'admin': 3,
}

ROLE_LABELS = {
    'viewer': 'Наблюдатель',
    'operator': 'Оператор',
    'admin': 'Администратор',
    'oper': 'Оператор (alt)',  # Alternative operator account
    'viewer_only': 'Только просмотр',  # Read-only role
}


class User(UserMixin):
    """Simple user model backed by database rows (dicts)."""

    def __init__(self, id: int, username: str, password_hash: str,
                 role: str = 'viewer', is_active: bool = True,
                 password_changed: bool = True):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self._is_active = is_active
        self._password_changed = password_changed

    @staticmethod
    def from_dict(d: dict) -> 'User':
        return User(
            id=d['id'],
            username=d['username'],
            password_hash=d['password_hash'],
            role=d.get('role', 'viewer'),
            is_active=bool(d.get('is_active', 1)),
            password_changed=bool(d.get('password_changed', 1)),
        )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_role(self, role: str) -> bool:
        """Check if user has at least the given role level."""
        return ROLES.get(self.role, 0) >= ROLES.get(role, 0)

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        from web.auth_user import user_has_permission
        return user_has_permission(self.id, permission)

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def needs_password_change(self) -> bool:
        """True if user has never changed their password."""
        return not self._password_changed

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
