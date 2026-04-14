"""
MES Production System — User authentication (Flask-Login).

Provides:
  - login_manager instance
  - load_user callback
  - authenticate(username, password) helper
  - require_role decorator
  - init_default_admin() — creates admin if no users exist
"""
import sqlite3
import functools
from typing import Optional

from flask import abort, redirect, request, url_for
from flask_login import LoginManager, current_user

from web.models import User


# ── Flask-Login setup ─────────────────────────────────────────

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Войдите в систему для доступа к этой странице'


@login_manager.user_loader
def load_user(user_id: int) -> Optional[User]:
    """Load user from database by ID."""
    # app_config is set during create_app() — avoids circular imports
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


# ── Dual auth: session OR API key ────────────────────────────

def require_auth_or_api_key(func):
    """
    Decorator: requires EITHER a logged-in user session OR a valid API key.
    This allows both browser users and API clients (curl) to write data.
    """
    @functools.wraps(func)
    def decorated(*args, **kwargs):
        # Check session auth first
        if current_user.is_authenticated:
            return func(*args, **kwargs)

        # Fall back to API key auth
        from flask import current_app
        auth_service = current_app.config.get('auth_service')
        if auth_service is not None:
            api_key = request.headers.get('X-API-Key')
            if api_key and auth_service.is_valid(api_key):
                return func(*args, **kwargs)

        # Neither auth method succeeded — always return 401 for API endpoints
        return {'error': 'Unauthorized: login or provide API key'}, 401
    return decorated

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
                    return {'error': 'Unauthorized'}, 401
                return redirect(url_for('login'))
            if not current_user.has_role(role):
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return {'error': 'Forbidden: insufficient role'}, 403
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        ''')

        # Check if any users exist
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            # Create default admin
            from werkzeug.security import generate_password_hash
            from datetime import datetime
            admin_hash = generate_password_hash('admin')
            cursor.execute('''
                INSERT INTO users (username, password_hash, role, created_at)
                VALUES (?, ?, 'admin', ?)
            ''', ('admin', admin_hash, datetime.now().isoformat()))
            conn.commit()
    finally:
        conn.close()
