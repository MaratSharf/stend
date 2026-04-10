"""
Shared pytest fixtures for MES tests.
"""
import os
import sys
import pytest
import tempfile
import yaml

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.database import Database
from core.controller import Controller
from web.app import create_app


TEST_API_KEY = "test-secret-key-12345"


@pytest.fixture
def db_path(tmp_path):
    """Return a temporary database path."""
    return str(tmp_path / "test_mes.db")


@pytest.fixture
def db(db_path):
    """Provide a Database instance with test stations."""
    database = Database(db_path)
    database.init_stations([
        "Station 1", "Station 2", "Station 3",
        "Station 4", "Station 5", "Station 6",
        "Station 7", "Station 8", "Station 9",
        "Station 10"
    ])
    return database


@pytest.fixture
def controller(db):
    """Provide a Controller instance."""
    return Controller(db)


@pytest.fixture
def app_config(db_path):
    """Provide a minimal test configuration."""
    return {
        'database': {'path': db_path},
        'server': {'host': '127.0.0.1', 'port': 5000},
        'stations': [
            "Station 1", "Station 2", "Station 3",
            "Station 4", "Station 5", "Station 6",
            "Station 7", "Station 8", "Station 9",
            "Station 10"
        ],
        'logging': {'level': 'WARNING', 'path': str(os.path.dirname(db_path))},
        'auth': {'api_keys': [TEST_API_KEY]}
    }


@pytest.fixture
def app(app_config):
    """Provide a Flask app instance."""
    return create_app(app_config)


@pytest.fixture
def client(app):
    """Provide a test client."""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """Provide a test client with valid API key."""
    c = app.test_client()
    c.environ_base['HTTP_X_API_KEY'] = TEST_API_KEY
    return c


@pytest.fixture
def unauth_client(app):
    """Provide a test client without API key."""
    return app.test_client()
