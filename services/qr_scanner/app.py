from flask import Flask, render_template, jsonify, request
import logging
from waitress import serve
import requests
import os
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация MES API
MES_API_URL = os.environ.get('MES_API_URL', 'http://localhost:5000')
MES_API_KEY = os.environ.get('MES_API_KEY', 'change-me-to-a-secure-key')

def create_app():
    """Фабрика Flask приложения"""
    app = Flask(__name__)
    
    # Хранение последних результатов сканирования
    scan_results = []
    active_scans = {}  # order_id -> latest_scan_data
    
    @app.route('/')
    def index():
        """Главная страница с QR-сканером"""
        return render_template('index.html', mes_api_url=MES_API_URL, api_key=MES_API_KEY)

    @app.route('/api/current-order')
    def get_current_order():
        """Получить текущий заказ со станции 6.1 из MES"""
        try:
            # Получаем все станции
            response = requests.get(
                f'{MES_API_URL}/api/stations',
                headers={'X-API-Key': MES_API_KEY},
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Ошибка получения станций: {response.status_code}")
                return jsonify({'error': 'Cannot fetch stations', 'details': response.text}), 500
            
            stations = response.json()
            
            # Ищем станцию 6.1 (QR-scanner)
            for station in stations:
                if station.get('id') == 6.1:
                    # Теперь API возвращает 'orders' массив вместо 'order_id'
                    orders = station.get('orders', [])
                    if orders and len(orders) > 0:
                        # Возвращаем все заказы на станции для выбора
                        logger.info(f"На станции 6.1 найдено заказов: {len(orders)}")
                        return jsonify({
                            'success': True,
                            'orders': orders,
                            'count': len(orders),
                            'message': 'Multiple orders available' if len(orders) > 1 else 'Single order available'
                        })
                    
                    # Станция 6.1 пуста
                    return jsonify({
                        'success': True,
                        'orders': [],
                        'count': 0,
                        'message': 'Station 6.1 is idle'
                    })
            
            # Станция 6.1 не найдена
            return jsonify({
                'success': False,
                'message': 'Station 6.1 not found'
            }), 404
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка соединения с MES API: {e}")
            return jsonify({
                'success': False,
                'message': f'Cannot connect to MES: {str(e)}'
            }), 500
    
    @app.route('/api/health')
    def health():
        """Проверка работоспособности API"""
        return jsonify({
            'status': 'ok', 
            'service': 'QR Scanner',
            'mes_api_url': MES_API_URL
        })
    
    @app.route('/api/scan', methods=['POST'])
    def receive_scan():
        """Получение результата сканирования от фронтенда"""
        data = request.get_json()
        
        if not data or 'qr_data' not in data:
            return jsonify({'error': 'qr_data required'}), 400
        
        qr_data = data['qr_data']
        order_id = data.get('order_id')
        timestamp = datetime.now().isoformat()
        
        result = {
            'qr_data': qr_data,
            'timestamp': timestamp,
            'order_id': order_id
        }
        
        # Сохраняем результат
        scan_results.append(result)
        if len(scan_results) > 100:
            scan_results.pop(0)
        
        if order_id:
            active_scans[order_id] = result
        
        logger.info(f"QR код сканирован: {qr_data} (order_id: {order_id})")
        
        return jsonify({
            'success': True,
            'result': result
        })
    
    @app.route('/api/scan/<int:order_id>', methods=['POST'])
    def scan_for_order(order_id):
        """Сканирование QR-кода для конкретного заказа с сохранением в MES"""
        data = request.get_json()
        
        if not data or 'qr_data' not in data:
            return jsonify({'error': 'qr_data required'}), 400
        
        qr_data = data['qr_data']
        timestamp = datetime.now().isoformat()
        result_text = data.get('result', 'OK')
        
        # Сохраняем результат в MES database через API
        try:
            response = requests.post(
                f'{MES_API_URL}/api/orders/{order_id}/scan-result',
                json={
                    'qr_data': qr_data,
                    'result': result_text,
                    'timestamp': timestamp
                },
                headers={
                    'X-API-Key': MES_API_KEY,
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Результат сканирования сохранён в MES для заказа {order_id}")
                return jsonify({
                    'success': True,
                    'message': 'Result saved to MES',
                    'response': response.json()
                })
            else:
                logger.error(f"Ошибка сохранения в MES: {response.status_code} - {response.text}")
                return jsonify({
                    'success': False,
                    'message': f'MES API error: {response.status_code}',
                    'response': response.text
                }), 500
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Не удалось соединиться с MES API: {e}")
            return jsonify({
                'success': False,
                'message': f'Cannot connect to MES: {str(e)}'
            }), 500
    
    @app.route('/api/scans', methods=['GET'])
    def get_scans():
        """Получение истории сканирований"""
        order_id = request.args.get('order_id', type=int)
        
        if order_id:
            filtered = [s for s in scan_results if s.get('order_id') == order_id]
            return jsonify({'scans': filtered, 'count': len(filtered)})
        
        return jsonify({
            'scans': scan_results[-50:],  # Последние 50
            'count': len(scan_results)
        })
    
    @app.route('/api/scans/<int:order_id>/latest', methods=['GET'])
    def get_latest_scan(order_id):
        """Получение последнего сканирования для заказа"""
        if order_id in active_scans:
            return jsonify({'scan': active_scans[order_id]})
        return jsonify({'scan': None}), 404
    
    @app.route('/api/complete-station', methods=['POST'])
    def complete_station():
        """Завершение подстанции 6.1 для заказа"""
        data = request.get_json()
        
        if not data or 'order_id' not in data:
            return jsonify({'error': 'order_id required'}), 400
        
        order_id = data['order_id']
        
        try:
            # Вызываем API для завершения подстанции
            response = requests.post(
                f'{MES_API_URL}/api/orders/{order_id}/complete-sub',
                json={'sub_station_id': 6.1},
                headers={
                    'X-API-Key': MES_API_KEY,
                    'Content-Type': 'application/json'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Подстанция 6.1 завершена для заказа {order_id}")
                return jsonify({
                    'success': True,
                    'response': response.json()
                })
            else:
                logger.error(f"Ошибка завершения станции: {response.status_code}")
                return jsonify({
                    'success': False,
                    'message': response.json().get('error', 'Unknown error')
                }), 400
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Не удалось соединиться с MES API: {e}")
            return jsonify({
                'success': False,
                'message': f'Cannot connect to MES: {str(e)}'
            }), 500
    
    @app.errorhandler(404)
    def not_found(error):
        """Обработчик 404"""
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def server_error(error):
        """Обработчик 500"""
        return jsonify({'error': 'Internal server error'}), 500
    
    return app

def main():
    """Точка входа"""
    app = create_app()
    logger.info('Запуск QR Scanner сервиса...')
    logger.info(f'MES API URL: {MES_API_URL}')
    logger.info('Открыть в браузере: http://localhost:5001')
    serve(app, host='0.0.0.0', port=5001, threads=4)

if __name__ == '__main__':
    main()