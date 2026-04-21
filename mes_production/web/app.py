"""
MES Production System - Flask Application
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from core.controller import Controller
from utils.database import Database
from utils.logger import setup_logger
from web.auth import AuthService
from web.auth_user import (
    login_manager, authenticate, require_role, init_default_users,
    require_auth_or_api_key, require_operator_or_api_key, generate_csrf_token,
    require_permission, get_user_permissions, user_has_permission
)
from utils.permissions import get_all_permissions, get_permission_categories, get_permissions_by_category, CATEGORIES, DEFAULT_ROLE_PERMISSIONS
from web.models import User, ROLES, ROLE_LABELS
from utils.role_service import RoleService
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

    # Initialize auth service (API key) — for machine scripts only
    api_keys = config.get('auth', {}).get('api_keys', [])
    auth_service = AuthService(api_keys if api_keys else None)
    app.config['auth_service'] = auth_service
    
    # Initialize role service
    role_service = RoleService(user_db_path)
    app.config['role_service'] = role_service

    # Store in app context
    app.config['controller'] = controller
    app.config['logger'] = logger
    app.config['role_service'] = role_service

    # Expose CSRF token to all templates
    @app.context_processor
    def inject_csrf():
        return {'csrf_token': generate_csrf_token()}

    # ── Auth pages (login/logout/change-password) ──────────────

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
                # Fix #3: Force password change on first login
                if user.needs_password_change:
                    return redirect(url_for('change_password'))
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                # Redirect users with station_view permission to station page
                # Use user_has_permission after login_user so current_user is set
                if user.has_role('admin'):
                    return redirect(url_for('index'))
                elif user_has_permission(user.id, 'production_view'):
                    return redirect(url_for('station'))
                return redirect(url_for('index'))
            flash('Неверный логин или пароль', 'error')

        return render_template('login.html')

    @app.route('/change-password', methods=['GET', 'POST'])
    @login_required
    def change_password():
        if request.method == 'POST':
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')

            if not new_pw or len(new_pw) < 6:
                flash('Пароль должен быть не менее 6 символов', 'error')
            elif new_pw != confirm_pw:
                flash('Пароли не совпадают', 'error')
            else:
                db_path = app.config.get('user_db_path')
                import sqlite3
                conn = sqlite3.connect(db_path)
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE users SET password_hash = ?, password_changed = 1
                        WHERE id = ?
                    ''', (generate_password_hash(new_pw), current_user.id))
                    conn.commit()
                    logger.info(f"User '{current_user.username}' changed password")
                    flash('Пароль успешно изменён', 'success')
                    return redirect(url_for('index'))
                finally:
                    conn.close()

        return render_template('change_password.html')

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
        
        # Validate role exists in database (built-in or custom)
        db_path = app.config.get('user_db_path')
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            # Check in role_permissions table
            cursor.execute('SELECT 1 FROM role_permissions WHERE role = ? LIMIT 1', (role,))
            role_in_perms = cursor.fetchone() is not None
            # Check in users table (role assigned to existing users)
            cursor.execute('SELECT 1 FROM users WHERE role = ? LIMIT 1', (role,))
            role_in_users = cursor.fetchone() is not None
            role_exists = role_in_perms or role_in_users
        finally:
            conn.close()
        
        if not role_exists and role not in ROLES:
            return jsonify({'error': f'Invalid role. Role "{role}" does not exist'}), 400

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

            # Fix #5: Whitelisted column updates (no f-string SQL)
            if 'role' in data and data['role'] in ROLES:
                cursor.execute('UPDATE users SET role = ? WHERE id = ?', (data['role'], user_id))
            if 'password' in data and data['password']:
                cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                               (generate_password_hash(data['password']), user_id))
            if 'is_active' in data:
                cursor.execute('UPDATE users SET is_active = ? WHERE id = ?',
                               (1 if data['is_active'] else 0, user_id))

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
    @require_permission('order_view')
    def index():
        """Main page - orders list."""
        return render_template('index.html', user=current_user)

    @app.route('/tracking')
    @login_required
    @require_permission('station_view')
    def tracking():
        """Station tracking page."""
        return render_template('tracking.html', user=current_user)

    @app.route('/station')
    @login_required
    @require_permission('production_view')
    def station():
        """Station detail page — pick a station and see its orders."""
        return render_template('station.html', user=current_user)

    @app.route('/map')
    @login_required
    @require_permission('map_view')
    def map_page():
        """SVG pipeline tracking page."""
        return render_template('map.html', user=current_user)

    @app.route('/roles')
    @login_required
    @require_permission('role_view')
    def roles_page():
        """Roles management page - configure permissions for each role."""
        from utils.permissions import (
            get_permission_categories, get_permissions_by_category, 
            CATEGORIES, PERMISSIONS, SCREENS
        )
        import sqlite3
        
        db_path = app.config.get('user_db_path')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            
            # Get ALL roles from database (including custom roles)
            cursor.execute('SELECT DISTINCT role FROM role_permissions ORDER BY role')
            all_roles_db = [r['role'] for r in cursor.fetchall()]
            
            # Get all permissions for each role
            role_permissions = {}
            for role in all_roles_db:
                cursor.execute('''
                    SELECT permission FROM role_permissions WHERE role = ? AND permission != ''
                ''', (role,))
                role_permissions[role] = [r['permission'] for r in cursor.fetchall()]
            
            # Build roles dict: include built-in roles with labels + custom roles
            roles_dict = dict(ROLE_LABELS)  # Copy built-in roles
            for role in all_roles_db:
                if role not in roles_dict:
                    roles_dict[role] = role.capitalize()  # Custom role label
        finally:
            conn.close()
        
        categories = get_permission_categories()
        permissions_by_category = {cat: get_permissions_by_category(cat) for cat in categories}
        
        return render_template(
            'roles.html', 
            user=current_user, 
            roles=roles_dict,
            categories=categories,
            category_labels=CATEGORIES,
            permissions_by_category=permissions_by_category,
            role_permissions=role_permissions,
            screens=SCREENS,
            all_permissions=PERMISSIONS
        )

    # ── API Routes - Role Permissions Management ───────────────

    @app.route('/api/roles/<role>/permissions', methods=['POST'])
    @login_required
    @require_role('admin')
    def api_set_role_permissions(role: str):
        """Set permissions for a specific role."""
        # Validate role exists in database (either in role_permissions table OR in users table as role)
        db_path = app.config.get('user_db_path')
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            # Check if role exists in role_permissions table OR is a built-in role
            cursor.execute('SELECT 1 FROM role_permissions WHERE role = ? LIMIT 1', (role,))
            role_in_perms = cursor.fetchone() is not None
            
            # Also check if role is assigned to any user
            cursor.execute('SELECT 1 FROM users WHERE role = ? LIMIT 1', (role,))
            role_in_users = cursor.fetchone() is not None
            
            role_exists = role_in_perms or role_in_users
        finally:
            conn.close()
        
        if not role_exists and role not in ROLES:
            return jsonify({'error': f'Invalid role. Role "{role}" does not exist'}), 400
        
        data = request.get_json()
        if not data or 'permissions' not in data:
            return jsonify({'error': 'permissions array required'}), 400
        
        permissions = data['permissions']
        if not isinstance(permissions, list):
            return jsonify({'error': 'permissions must be an array'}), 400
        
        # Validate all permissions exist
        from utils.permissions import PERMISSIONS
        invalid = [p for p in permissions if p not in PERMISSIONS]
        if invalid:
            return jsonify({'error': f'Invalid permissions: {", ".join(invalid)}'}), 400
        
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            
            # Delete existing permissions for this role (including empty marker)
            cursor.execute('DELETE FROM role_permissions WHERE role = ?', (role,))
            
            # Remove duplicates by using set
            unique_permissions = list(set(permissions))
            
            # Insert new permissions using executemany
            cursor.executemany(
                'INSERT INTO role_permissions (role, permission) VALUES (?, ?)',
                [(role, perm) for perm in unique_permissions]
            )
            
            conn.commit()
            logger.info(f"Permissions for role '{role}' updated by '{current_user.username}'")
            return jsonify({'success': True, 'permissions': unique_permissions})
        finally:
            conn.close()

    @app.route('/api/roles/<role>/permissions/reset', methods=['POST'])
    @login_required
    @require_role('admin')
    def api_reset_role_permissions(role: str):
        """Reset permissions for a role to defaults."""
        if role not in ROLES:
            return jsonify({'error': f'Invalid role. Choose: {", ".join(ROLES.keys())}'}), 400
        
        from utils.permissions import DEFAULT_ROLE_PERMISSIONS
        default_perms = DEFAULT_ROLE_PERMISSIONS.get(role, [])
        
        db_path = app.config.get('user_db_path')
        import sqlite3
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            
            # Delete existing permissions
            cursor.execute('DELETE FROM role_permissions WHERE role = ?', (role,))
            
            # Insert default permissions
            for perm in default_perms:
                cursor.execute(
                    'INSERT INTO role_permissions (role, permission) VALUES (?, ?)',
                    (role, perm)
                )
            
            conn.commit()
            logger.info(f"Permissions for role '{role}' reset to defaults by '{current_user.username}'")
            return jsonify({'success': True, 'permissions': default_perms})
        finally:
            conn.close()

    @app.route('/api/roles', methods=['GET'])
    @login_required
    def api_get_roles():
        """Get all roles (built-in + custom)."""
        import sqlite3
        db_path = app.config.get('user_db_path')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            # Get all roles from role_permissions table
            cursor.execute('SELECT DISTINCT role FROM role_permissions ORDER BY role')
            roles_db = [r['role'] for r in cursor.fetchall()]
            
            # Get built-in roles
            roles_list = []
            for role in ROLES.keys():
                roles_list.append({
                    'role': role,
                    'label': ROLE_LABELS.get(role, role.capitalize()),
                    'builtin': True
                })
            
            # Add custom roles
            for role in roles_db:
                if role not in ROLES:
                    roles_list.append({
                        'role': role,
                        'label': role.capitalize(),
                        'builtin': False
                    })
            
            return jsonify({'success': True, 'roles': roles_list})
        finally:
            conn.close()

    @app.route('/api/roles', methods=['POST'])
    @login_required
    @require_role('admin')
    def api_create_role():
        """Create a new role with default permissions."""
        data = request.get_json()
        if not data or not data.get('role'):
            return jsonify({'error': 'role name required'}), 400
        
        role = data['role'].strip().lower()
        if not role or not role.isidentifier():
            return jsonify({'error': 'Invalid role name. Use letters and underscores only'}), 400
        
        # Get permissions to assign (default to viewer permissions if not specified)
        permissions = data.get('permissions', ['order_view', 'station_view'])
        
        db_path = app.config.get('user_db_path')
        import sqlite3
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            
            # Check if role already exists (in role_permissions or users table)
            cursor.execute('SELECT 1 FROM role_permissions WHERE role = ? LIMIT 1', (role,))
            role_in_perms = cursor.fetchone() is not None
            cursor.execute('SELECT 1 FROM users WHERE role = ? LIMIT 1', (role,))
            role_in_users = cursor.fetchone() is not None
            
            if role_in_perms or role_in_users:
                return jsonify({'error': f'Role "{role}" already exists'}), 400
            
            # Remove duplicates
            unique_permissions = list(set(permissions))
            
            # Insert role with permissions using executemany
            cursor.executemany(
                'INSERT INTO role_permissions (role, permission) VALUES (?, ?)',
                [(role, perm) for perm in unique_permissions]
            )
            
            conn.commit()
            logger.info(f"New role '{role}' created by '{current_user.username}' with {len(unique_permissions)} permission(s)")
            return jsonify({'success': True, 'role': role, 'permissions': unique_permissions})
        except sqlite3.IntegrityError:
            return jsonify({'error': f'Role "{role}" already exists'}), 400
        finally:
            conn.close()

    @app.route('/api/roles/<role>', methods=['DELETE'])
    @login_required
    @require_role('admin')
    def api_delete_role(role: str):
        """Delete a role."""
        if role in ('admin', 'operator', 'viewer'):
            return jsonify({'error': 'Cannot delete built-in roles'}), 403
        
        db_path = app.config.get('user_db_path')
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            
            # Check if role exists in role_permissions OR users table
            cursor.execute('SELECT 1 FROM role_permissions WHERE role = ? LIMIT 1', (role,))
            role_in_perms = cursor.fetchone() is not None
            cursor.execute('SELECT 1 FROM users WHERE role = ? LIMIT 1', (role,))
            role_in_users = cursor.fetchone() is not None
            
            if not role_in_perms and not role_in_users:
                return jsonify({'error': f'Role "{role}" not found'}), 404
            
            # Delete role permissions
            cursor.execute('DELETE FROM role_permissions WHERE role = ?', (role,))
            
            conn.commit()
            logger.info(f"Role '{role}' deleted by '{current_user.username}'")
            return jsonify({'success': True})
        finally:
            conn.close()

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
    # Fix #4: All write endpoints require operator+ role (not viewer)
    # Fix #2: Session users must have valid CSRF token; API key users bypass CSRF

    @app.route('/api/orders', methods=['POST'])
    @require_operator_or_api_key
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
    @require_operator_or_api_key
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
    @require_operator_or_api_key
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
    @require_operator_or_api_key
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
    @require_operator_or_api_key
    def api_cancel_order(order_id: int):
        """Cancel an order."""
        result = controller.cancel_order(order_id)
        if result['success']:
            logger.info("POST /api/orders/%d/cancel — OK", order_id)
            return jsonify(result)
        else:
            logger.warning("POST /api/orders/%d/cancel — FAILED", order_id)
            return jsonify(result), 400

    @app.route('/api/orders/<int:order_id>/complete-sub', methods=['POST'])
    @require_operator_or_api_key
    def api_complete_sub(order_id: int):
        """Complete a sub-station for an order. Body: {sub_station_id: 1.1}."""
        data = request.get_json()
        if not data or 'sub_station_id' not in data:
            return jsonify({'error': 'sub_station_id required'}), 400

        sub_id = float(data['sub_station_id'])
        result = db.complete_sub_station(order_id, sub_id)
        if result['success']:
            logger.info("POST /api/orders/%d/complete-sub %.1f — OK", order_id, sub_id)
            order = controller.get_order(order_id)
            result['order'] = order
            return jsonify(result)
        else:
            logger.warning("POST /api/orders/%d/complete-sub %.1f — FAILED", order_id, sub_id)
            return jsonify(result), 400

    @app.route('/api/sub-stations', methods=['GET'])
    @login_required
    def api_get_sub_stations():
        """Get all sub-stations grouped by parent. For UI rendering."""
        all_stations = db.get_stations()
        groups = {}
        for s in all_stations:
            main_id = float(int(s['id']))
            if s['id'] != main_id:
                if main_id not in groups:
                    groups[main_id] = {'main_id': main_id, 'subs': []}
                groups[main_id]['subs'].append(s)
        return jsonify(list(groups.values()))

    return app
