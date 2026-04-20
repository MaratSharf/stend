"""
MES Production System — User authentication (Flask-Login).

Provides:
  - login_manager instance
  - load_user callback
  - authenticate(username, password) helper
  - require_role decorator
  - require_operator_role — write endpoints require operator+
1  - require_permission decorator — permission-based access control
  - CSRF token generation/validation
  - init_default_users() — creates admin if no users exist
"""
import sqlite3
import functools
import hashlib
import os
import time
from typing import Optional, List

from flask import abort, redirect, request, url_for, session, jsonify as flask_jsonify
from flask_login import LoginManager, current_user

from web.models import User
from utils.permissions import PERMISSIONS


def get_user_permissions(user_id: int) -> List[str]:
    """
    Get all permission keys for a user based on their role.
    Returns list of permission strings from role_permissions table.
    """
    from flask import current_app
    db_path = current_app.config.get('user_db_path')
    if not db_path:
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        # Get user's role
        cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        if not row:
            return []
        
        role = row['role']
        
        # Get permissions for this role from role_permissions table
        cursor.execute('''
            SELECT permission FROM role_permissions WHERE role = ?
        ''', (role,))
        return [r['permission'] for r in cursor.fetchall()]
    finally:
        conn.close()


def user_has_permission(user_id: int, permission: str) -> bool:
    """
    Check if a user has a specific permission.
    Admin users always have all permissions.
    """
    # First check if user is admin by looking up their role in DB
    from flask import current_app
    db_path = current_app.config.get('user_db_path')
    if db_path:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            if row and row['role'] == 'admin':
                return True
        finally:
            conn.close()
    
    if permission in PERMISSIONS:
        permissions = get_user_permissions(user_id)
        return permission in permissions
    return False


def require_permission(permission: str):
    """
    Decorator: requires the user to have a specific permission.
    
    Usage:
        @app.route('/api/orders', methods=['POST'])
        @login_required
        @require_permission('create_order')
        def api_create_order(): ...
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify_error('Unauthorized', 401)
                return redirect(url_for('login'))
            
            if not user_has_permission(current_user.id, permission):
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify_error(f'Forbidden: {permission} permission required', 403)
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ── Flask-Login setup ─────────────────────────────────────────

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Войдите в систему для доступа к этой странице'


@login_manager.user_loader
def load_user(user_id: int) -> Optional[User]:
    """Load user from database by ID."""
    from flask import current_app
    db_path = current_app.config.get('user_db_path')
    if not db_path:
        return None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        return User.from_dict(dict(row)) if row else None
    finally:
        conn.close()


# ── Authentication helper ────────────────────────────────────

def authenticate(username: str, password: str) -> Optional[User]:
    """Verify username/password. Returns User or None."""
    from flask import current_app
    db_path = current_app.config.get('user_db_path')
    if not db_path:
        return None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        if row and User.from_dict(dict(row)).check_password(password):
            return User.from_dict(dict(row))
        return None
    finally:
        conn.close()


# ── CSRF token helpers ───────────────────────────────────────

def generate_csrf_token() -> str:
    """Generate or return existing CSRF token in session."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = hashlib.sha256(os.urandom(32)).hexdigest()
    return session['_csrf_token']


def validate_csrf_token() -> bool:
    """Validate CSRF token from form data or header."""
    token = session.get('_csrf_token')
    if not token:
        return False
    form_token = (
        request.form.get('_csrf_token') or
        request.headers.get('X-CSRF-Token') or
        request.headers.get('X-Csrf-Token')
    )
    return form_token is not None and form_token == token


def require_csrf(func):
    """Decorator: validates CSRF token for session-authenticated POST requests."""
    @functools.wraps(func)
    def decorated(*args, **kwargs):
        # Only check CSRF for session-authenticated users (not API key users)
        if current_user.is_authenticated:
            if not validate_csrf_token():
                return {'error': 'CSRF token missing or invalid'}, 403
        return func(*args, **kwargs)
    return decorated


# ── Dual auth: session OR API key ────────────────────────────

def require_auth_or_api_key(func):
    """
    Decorator: requires EITHER a logged-in user session (with CSRF) OR a valid API key.
    API key users bypass CSRF (they are scripts, not browsers).
    """
    @functools.wraps(func)
    def decorated(*args, **kwargs):
        # Check session auth first
        if current_user.is_authenticated:
            # Session user → must have valid CSRF token
            if not validate_csrf_token():
                return jsonify_csrf_error()
            return func(*args, **kwargs)

        # Fall back to API key auth (no CSRF required for API key)
        from flask import current_app
        auth_service = current_app.config.get('auth_service')
        if auth_service is not None:
            api_key = request.headers.get('X-API-Key')
            if api_key and auth_service.is_valid(api_key):
                return func(*args, **kwargs)

        # Neither auth method succeeded
        return jsonify_error('Unauthorized: login or provide API key', 401)
    return decorated


def require_operator_or_api_key(func):
    """
    Decorator: requires EITHER (logged-in user with operator+ role AND valid CSRF)
    OR a valid API key. This prevents viewers from performing write operations.
    """
    @functools.wraps(func)
    def decorated(*args, **kwargs):
        # Check session auth first
        if current_user.is_authenticated:
            # Check role: must be operator or admin
            if not current_user.has_role('operator'):
                return jsonify_error('Forbidden: operator role required', 403)
            # Session user → must have valid CSRF token
            if not validate_csrf_token():
                return jsonify_csrf_error()
            return func(*args, **kwargs)

        # Fall back to API key auth (no CSRF required for API key)
        from flask import current_app
        auth_service = current_app.config.get('auth_service')
        if auth_service is not None:
            api_key = request.headers.get('X-API-Key')
            if api_key and auth_service.is_valid(api_key):
                return func(*args, **kwargs)

        # Neither auth method succeeded
        return jsonify_error('Unauthorized: login or provide API key', 401)
    return decorated


# ── Helper: JSON error responses ─────────────────────────────

def jsonify_error(message: str, status: int):
    """Return a JSON error response (avoids importing jsonify in decorator)."""
    from flask import jsonify
    return jsonify({'error': message}), status


def jsonify_csrf_error():
    """Return CSRF validation error."""
    return jsonify_error('CSRF token missing or invalid', 403)


# ── Role-based decorator ─────────────────────────────────────

def require_role(role: str):
    """
    Decorator: requires the user to have at least the given role level.

    Usage:
        @app.route('/admin')
        @login_required
        @require_role('admin')
        def admin_page(): ...
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify_error('Unauthorized', 401)
                return redirect(url_for('login'))
            if not current_user.has_role(role):
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify_error('Forbidden: insufficient role', 403)
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ── Default admin ────────────────────────────────────────────

def init_default_users(db_path: str):
    """Create the users table and a default admin if no users exist."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # ── Create role_permissions table ───────────────────────
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='role_permissions'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE role_permissions (
                    role TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    PRIMARY KEY (role, permission)
                )
            ''')
            # Insert default permissions
            from utils.permissions import DEFAULT_ROLE_PERMISSIONS
            for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
                for perm in perms:
                    cursor.execute(
                        'INSERT INTO role_permissions (role, permission) VALUES (?, ?)',
                        (role, perm)
                    )

        # ── Create users table ──────────────────────────────────
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                is_active INTEGER NOT NULL DEFAULT 1,
                password_changed INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        ''')

        # ── Migration: add password_changed column ──────────────
        cursor.execute("PRAGMA table_info(users)")
        col_names = [col[1] for col in cursor.fetchall()]
        if 'password_changed' not in col_names:
            cursor.execute("ALTER TABLE users ADD COLUMN password_changed INTEGER NOT NULL DEFAULT 1")
            cursor.execute("UPDATE users SET password_changed = 1 WHERE password_changed IS NULL")

        # Check if any users exist
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            # Create default admin — must change password on first login
            from werkzeug.security import generate_password_hash
            from datetime import datetime
            admin_hash = generate_password_hash('admin')
            cursor.execute('''
                INSERT INTO users (username, password_hash, role, password_changed, created_at)
                VALUES (?, ?, 'admin', 0, ?)
            ''', ('admin', admin_hash, datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
