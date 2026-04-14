"""
MES Production System - Flask Application
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from core.controller import Controller
from utils.database import Database
from utils.logger import setup_logger
from web.auth import AuthService
from web.auth_user import login_manager, authenticate, require_role, init_default_users, require_auth_or_api_key
from web.models import User, ROLES
import yaml
import os


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        # Default to config.yaml in the project root (parent of web/)
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def create_app(config: dict = None) -> Flask:
    """Create and configure the Flask application."""
    if config is None:
        config = load_config()

    app = Flask(__name__)
    app.secret_key = os.urandom(24)  # For flash sessions

    # ── Initialize database ────────────────────────────────────
    db_path = config.get('database', {}).get('path', 'data/mes.db')

    # Setup logger (needed by both Database and web layer)
    log_config = config.get('logging', {})
    logger = setup_logger('mes_web', log_config.get('path', 'data/logs'), log_config.get('level', 'INFO'))

    db = Database(db_path, logger)

    # Initialize stations
    station_names = config.get('stations', [])
    if station_names:
        db.init_stations(station_names)

    # Initialize controller
    controller = Controller(db)

    # ── Initialize user authentication ─────────────────────────
    user_db_path = os.path.join(os.path.dirname(db_path), 'users.db')
    app.config['user_db_path'] = user_db_path
    init_default_users(user_db_path)

    # Init Flask-Login
    login_manager.init_app(app)

    # Initialize auth service (API key)
    api_keys = config.get('auth', {}).get('api_keys', [])
    auth_service = AuthService(api_keys if api_keys else None)
    app.config['auth_service'] = auth_service
    # Store first API key for frontend (if available)
    app.config['frontend_api_key'] = api_keys[0] if api_keys else None

    # Store in app context
    app.config['controller'] = controller
    app.config['logger'] = logger

    # ── Auth pages (login/logout) ──────────────────────────────

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')

            user = authenticate(username, password)
            if user and user.is_active:
                login_user(user, remember=request.form.get('remember'))
                logger.info(f"User '{username}' logged in")
                next_page = request.args.get('next')
                return redirect(next_page if next_page else url_for('index'))
            flash('Неверный логин или пароль', 'error')

        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logger.info(f"User '{current_user.username}' logged out")
        logout_user()
        return redirect(url_for('login'))

    # ── User management (admin only) ───────────────────────────

    @app.route('/users')
    @login_required
    @require_role('admin')
    def users_page():
        """Admin page: list/create/edit users."""
        db_path = app.config.get('user_db_path')
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY id')
            users = [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

        return render_template('users.html', users=users, roles=ROLES, user=current_user)

    @app.route('/api/users', methods=['POST'])
    @login_required
    @require_role('admin')
    def api_create_user():
        data = request.get_json()
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'error': 'username and password required'}), 400

        role = data.get('role', 'viewer')
        if role not in ROLES:
            return jsonify({'error': f'Invalid role. Choose: {", ".join(ROLES.keys())}'}), 400

        db_path = app.config.get('user_db_path')
        import sqlite3
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            password_hash = generate_password_hash(data['password'])
            from datetime import datetime
            cursor.execute('''
                INSERT INTO users (username, password_hash, role, created_at)
                VALUES (?, ?, ?, ?)
            ''', (data['username'].strip(), password_hash, role, datetime.now().isoformat()))
            conn.commit()
            logger.info(f"User '{data['username']}' created by '{current_user.username}'")
            return jsonify({'success': True, 'id': cursor.lastrowid})
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Username already exists'}), 400
        finally:
            conn.close()

    @app.route('/api/users/<int:user_id>', methods=['POST'])
    @login_required
    @require_role('admin')
    def api_update_user(user_id: int):
        data = request.get_json()
        db_path = app.config.get('user_db_path')
        import sqlite3
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            updates = []
            params = []

            if 'role' in data and data['role'] in ROLES:
                updates.append('role = ?')
                params.append(data['role'])
            if 'password' in data and data['password']:
                updates.append('password_hash = ?')
                params.append(generate_password_hash(data['password']))
            if 'is_active' in data:
                updates.append('is_active = ?')
                params.append(1 if data['is_active'] else 0)

            if updates:
                params.append(user_id)
                cursor.execute(f'UPDATE users SET {", ".join(updates)} WHERE id = ?', params)
                conn.commit()
            logger.info(f"User {user_id} updated by '{current_user.username}'")
            return jsonify({'success': True})
        finally:
            conn.close()

    @app.route('/api/users/<int:user_id>', methods=['DELETE'])
    @login_required
    @require_role('admin')
    def api_delete_user(user_id: int):
        if user_id == current_user.id:
            return jsonify({'error': 'Cannot delete yourself'}), 400

        db_path = app.config.get('user_db_path')
        import sqlite3
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            logger.info(f"User {user_id} deleted by '{current_user.username}'")
            return jsonify({'success': True})
        finally:
            conn.close()

    # ── Page routes ────────────────────────────────────────────

    @app.route('/')
    @login_required
    def index():
        """Main page - orders list."""
        return render_template('index.html',
                               api_key=app.config.get('frontend_api_key'),
                               user=current_user)

    @app.route('/tracking')
    @login_required
    def tracking():
        """Station tracking page."""
        return render_template('tracking.html',
                               api_key=app.config.get('frontend_api_key'),
                               user=current_user)

    @app.route('/station')
    @login_required
    def station():
        """Station detail page — pick a station and see its orders."""
        return render_template('station.html',
                               api_key=app.config.get('frontend_api_key'),
                               user=current_user)

    @app.route('/map')
    @login_required
    def map_page():
        """SVG pipeline tracking page."""
        return render_template('map.html',
                               api_key=app.config.get('frontend_api_key'),
                               user=current_user)

    # ── API Routes - Protected by login (read-only) ────────────

    @app.route('/api/orders', methods=['GET'])
    @login_required
    def api_get_orders():
        """Get all orders with optional status filter."""
        status = request.args.get('status')
        orders = controller.get_orders(status)
        return jsonify(orders)

    @app.route('/api/stations', methods=['GET'])
    @login_required
    def api_get_stations():
        """Get all stations status."""
        stations = controller.get_stations()
        return jsonify(stations)

    @app.route('/api/statistics', methods=['GET'])
    @login_required
    def api_get_statistics():
        """Get production statistics."""
        stats = controller.get_statistics()
        return jsonify(stats)

    # ── API Routes - Protected (write operations) ──────────────

    @app.route('/api/orders', methods=['POST'])
    @require_auth_or_api_key
    def api_create_order():
        """Create one or multiple orders."""
        data = request.get_json()

        if not data:
            logger.warning("POST /api/orders — no data provided")
            return jsonify({'error': 'No data provided'}), 400

        batch = data.get('batch')
        product_code = data.get('product_code')
        color = data.get('color', '')
        count = data.get('quantity')

        if not all([batch, product_code, count]):
            logger.warning("POST /api/orders — missing fields: batch=%s, product_code=%s, count=%s", batch, product_code, count)
            return jsonify({'error': 'Missing required fields'}), 400

        try:
            count = int(count)
        except (ValueError, TypeError):
            logger.warning("POST /api/orders — bad quantity: %s", data.get('quantity'))
            return jsonify({'error': 'Quantity must be a number'}), 400

        if count < 1:
            logger.warning("POST /api/orders — quantity < 1: %s", count)
            return jsonify({'error': 'Quantity must be at least 1'}), 400

        result = controller.create_order(batch, product_code, color, count)
        logger.info("POST /api/orders — created %d order(s), batch=%s", result['count'], batch)
        return jsonify(result), 201

    @app.route('/api/orders/<int:order_id>/launch', methods=['POST'])
    @require_auth_or_api_key
    def api_launch_order(order_id: int):
        """Launch an order to production."""
        result = controller.launch_order(order_id)
        if result['success']:
            logger.info("POST /api/orders/%d/launch — OK", order_id)
            return jsonify(result)
        else:
            logger.warning("POST /api/orders/%d/launch — FAILED", order_id)
            return jsonify(result), 400

    @app.route('/api/orders/<int:order_id>/move', methods=['POST'])
    @require_auth_or_api_key
    def api_move_order(order_id: int):
        """Move order to next station."""
        result = controller.move_order(order_id)
        if result['success']:
            logger.info("POST /api/orders/%d/move — OK", order_id)
            return jsonify(result)
        else:
            logger.warning("POST /api/orders/%d/move — FAILED", order_id)
            return jsonify(result), 400

    @app.route('/api/orders/<int:order_id>/complete', methods=['POST'])
    @require_auth_or_api_key
    def api_complete_order(order_id: int):
        """Complete an order manually."""
        result = controller.complete_order(order_id)
        if result['success']:
            logger.info("POST /api/orders/%d/complete — OK", order_id)
            return jsonify(result)
        else:
            logger.warning("POST /api/orders/%d/complete — FAILED", order_id)
            return jsonify(result), 400

    @app.route('/api/orders/<int:order_id>/cancel', methods=['POST'])
    @require_auth_or_api_key
    def api_cancel_order(order_id: int):
        """Cancel an order."""
        result = controller.cancel_order(order_id)
        if result['success']:
            logger.info("POST /api/orders/%d/cancel — OK", order_id)
            return jsonify(result)
        else:
            logger.warning("POST /api/orders/%d/cancel — FAILED", order_id)
            return jsonify(result), 400

    return app
