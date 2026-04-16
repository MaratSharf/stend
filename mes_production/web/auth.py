"""
MES Production System - Authentication middleware
Simple API key-based authentication for protected endpoints.
"""
from functools import wraps
from flask import request, jsonify, current_app


class AuthService:
    """Manages API keys for authentication."""
    
    def __init__(self, api_keys: list[str] | None = None):
        self._api_keys: set[str] = set(api_keys or [])
    
    def add_key(self, key: str) -> None:
        self._api_keys.add(key)
    
    def remove_key(self, key: str) -> None:
        self._api_keys.discard(key)
    
    def is_valid(self, key: str) -> bool:
        return key in self._api_keys


def require_api_key(func):
    """Decorator that requires a valid API key in the X-API-Key header."""
    @wraps(func)
    def decorated(*args, **kwargs):
        auth_service = current_app.config.get('auth_service')
        if auth_service is None:
            # Auth not configured, allow access
            return func(*args, **kwargs)
        
        api_key = request.headers.get('X-API-Key')
        if not api_key or not auth_service.is_valid(api_key):
            return jsonify({'error': 'Unauthorized: valid API key required'}), 401
        
        return func(*args, **kwargs)
    return decorated
