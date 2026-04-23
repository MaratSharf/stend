"""
Shared pytest fixtures for MES tests.
"""
import os
import sys
import pytest
import tempfile
import logging
import yaml
from datetime import datetime
from werkzeug.security import generate_password_hash

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.database import Database
from core.controller import Controller
from web.app import create_app
from utils.db_connection import DBConnection


TEST_API_KEY = "test-secret-key-12345"

# Shared logger for tests (quiet — WARNING level)
_test_logger = logging.getLogger('mes_test')
_test_logger.setLevel(logging.WARNING)
if not _test_logger.handlers:
    _test_logger.addHandler(logging.NullHandler())


@pytest.fixture
def db_path(tmp_path):
    """Return a temporary database path."""
    return str(tmp_path / "test_mes.db")


@pytest.fixture
def user_db_path(tmp_path):
    """Return a temporary users database path."""
    return str(tmp_path / "test_users.db")


def _init_test_users(config):
    """Create test users in the user DB. All have password_changed=1."""
    db = DBConnection(config)
    conn = db.get_connection()
    try:
        cursor = db.cursor(conn)
        # PostgreSQL-only table creation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                is_active INTEGER NOT NULL DEFAULT 1,
                password_changed INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        ''')
        now = datetime.now().isoformat()
        ph = db.placeholder()
        # Admin user (password_changed=1 so no redirect in tests)
        admin_hash = generate_password_hash('admin')
        cursor.execute(f'''
            INSERT INTO users (username, password_hash, role, password_changed, created_at)
            VALUES ({ph}, {ph}, 'admin', 1, {ph})
            ON CONFLICT (username) DO NOTHING
        ''', ('admin', admin_hash, now))
        # Viewer user
        viewer_hash = generate_password_hash('viewer')
        cursor.execute(f'''
            INSERT INTO users (username, password_hash, role, password_changed, created_at)
            VALUES ({ph}, {ph}, 'viewer', 1, {ph})
            ON CONFLICT (username) DO NOTHING
        ''', ('viewer', viewer_hash, now))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def db(db_path):
    """Provide a Database instance with test stations (including sub-stations)."""
    database = Database(db_path, logger=_test_logger)
    database.init_stations([
        {"name": "Station 1", "subs": ["Station 1.1", "Station 1.2"]},
        {"name": "Station 2"},
        {"name": "Station 3", "subs": ["Station 3.1"]},
        {"name": "Station 4"},
        {"name": "Station 5"},
        {"name": "Station 6"},
        {"name": "Station 7"},
        {"name": "Station 8"},
        {"name": "Station 9"},
        {"name": "Station 10"},
    ])
    return database


@pytest.fixture
def controller(db):
    """Provide a Controller instance."""
    return Controller(db)


@pytest.fixture
def app_config(db_path, user_db_path):
    """Provide a minimal test configuration."""
    return {
        'database': {'path': db_path},
        'server': {'host': '127.0.0.1', 'port': 5000},
        'stations': [
            {"name": "Station 1", "subs": ["Station 1.1", "Station 1.2"]},
            {"name": "Station 2"},
            {"name": "Station 3", "subs": ["Station 3.1"]},
            {"name": "Station 4"},
            {"name": "Station 5"},
            {"name": "Station 6"},
            {"name": "Station 7"},
            {"name": "Station 8"},
            {"name": "Station 9"},
            {"name": "Station 10"},
        ],
        'logging': {'level': 'WARNING', 'path': str(os.path.dirname(db_path))},
        'auth': {'api_keys': [TEST_API_KEY]}
    }


@pytest.fixture
def app(app_config, user_db_path):
    """Provide a Flask app instance with test users."""
    # Patch init_default_users to use our user_db_path
    from web.auth_user import init_default_users
    init_default_users(user_db_path)

    flask_app = create_app(app_config)
    # Override user_db_path to our test DB
    flask_app.config['user_db_path'] = user_db_path
    flask_app.config['user_db_conn'] = None
    return flask_app


@pytest.fixture
def client(app):
    """Provide a test client."""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """Provide a test client logged in as admin (via API key)."""
    c = app.test_client()
    c.environ_base['HTTP_X_API_KEY'] = TEST_API_KEY
    return c


@pytest.fixture
def unauth_client(app):
    """Provide a test client without any auth."""
    return app.test_client()


@pytest.fixture
def logged_client(app):
    """Provide a test client logged in as admin via session, with CSRF token."""
    c = app.test_client()
    # Login via the session-based login route
    resp = c.post('/login', data={
        'username': 'admin',
        'password': 'admin',
        'remember': 'yes'
    }, follow_redirects=True)
    # Extract CSRF token from the response meta tag
    import re
    m = re.search(r'meta name="csrf-token" content="([^"]+)"', resp.data.decode())
    csrf_token = m.group(1) if m else None

    # Store CSRF token for use in POST requests
    c.csrf_token = csrf_token

    def _post_with_csrf(url, **kwargs):
        headers = kwargs.pop('headers', {}) or {}
        if csrf_token:
            headers['X-CSRF-Token'] = csrf_token
        return c.post(url, headers=headers, **kwargs)

    c.post_csrf = _post_with_csrf
    return c