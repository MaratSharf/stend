"""
MES Production System - Flask Application
"""
from flask import Flask, render_template, request, jsonify
from core.controller import Controller
from utils.database import Database
from utils.logger import setup_logger
import yaml
import os


def load_config(config_path: str = 'config.yaml') -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def create_app(config: dict = None) -> Flask:
    """Create and configure the Flask application."""
    if config is None:
        config = load_config()
    
    app = Flask(__name__)
    
    # Initialize database
    db_path = config.get('database', {}).get('path', 'data/mes.db')
    db = Database(db_path)
    
    # Initialize stations
    station_names = config.get('stations', [])
    if station_names:
        db.init_stations(station_names)
    
    # Initialize controller
    controller = Controller(db)
    
    # Setup logger
    log_config = config.get('logging', {})
    logger = setup_logger('mes_web', log_config.get('path', 'data/logs'), log_config.get('level', 'INFO'))
    
    # Store in app context
    app.config['controller'] = controller
    app.config['logger'] = logger
    
    @app.route('/')
    def index():
        """Main page - orders list."""
        return render_template('index.html')
    
    @app.route('/tracking')
    def tracking():
        """Station tracking page."""
        return render_template('tracking.html')
    
    # API Routes
    @app.route('/api/orders', methods=['GET'])
    def api_get_orders():
        """Get all orders with optional status filter."""
        status = request.args.get('status')
        orders = controller.get_orders(status)
        return jsonify(orders)
    
    @app.route('/api/orders', methods=['POST'])
    def api_create_order():
        """Create a new order."""
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        batch = data.get('batch')
        product_code = data.get('product_code')
        color = data.get('color')
        quantity = data.get('quantity')
        
        if not all([batch, product_code, color, quantity]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            return jsonify({'error': 'Quantity must be a number'}), 400
        
        order = controller.create_order(batch, product_code, color, quantity)
        return jsonify(order), 201
    
    @app.route('/api/orders/<int:order_id>/launch', methods=['POST'])
    def api_launch_order(order_id: int):
        """Launch an order to production."""
        result = controller.launch_order(order_id)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    @app.route('/api/orders/<int:order_id>/move', methods=['POST'])
    def api_move_order(order_id: int):
        """Move order to next station."""
        result = controller.move_order(order_id)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    @app.route('/api/orders/<int:order_id>/complete', methods=['POST'])
    def api_complete_order(order_id: int):
        """Complete an order manually."""
        result = controller.complete_order(order_id)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    @app.route('/api/orders/<int:order_id>/cancel', methods=['POST'])
    def api_cancel_order(order_id: int):
        """Cancel an order."""
        result = controller.cancel_order(order_id)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    @app.route('/api/stations', methods=['GET'])
    def api_get_stations():
        """Get all stations status."""
        stations = controller.get_stations()
        return jsonify(stations)
    
    @app.route('/api/statistics', methods=['GET'])
    def api_get_statistics():
        """Get production statistics."""
        stats = controller.get_statistics()
        return jsonify(stats)
    
    return app


if __name__ == '__main__':
    config = load_config()
    app = create_app(config)
    
    host = config.get('server', {}).get('host', '0.0.0.0')
    port = config.get('server', {}).get('port', 5000)
    
    app.run(host=host, port=port, debug=True)
