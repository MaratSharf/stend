from flask import Flask, render_template, jsonify, request
import logging
from waitress import serve
import sys
import os

# Получаем корневую директорию проекта
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MES_DIR = os.path.join(ROOT_DIR, 'mes_production')

# Добавляем mes_production в путь для импорта модулей
sys.path.insert(0, MES_DIR)

from utils.db_connection import DBConnection
from utils.logger import setup_logger

# Настройка логирования
logger = setup_logger('qr_scanner_db', os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'logs'), 'INFO')

# Путь к базе данных MES
MES_DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'mes.db')

def create_app():
    """Фабрика приложения Flask"""
    app = Flask(__name__)
    
    # Инициализация БД
    db = DBConnection(MES_DB_PATH)
    
    def init_qr_table():
        """Создание таблицы для хранения QR-кодов"""
        conn = db.get_connection()
        cur = db.cursor(conn)
        
        # Проверка существования таблицы
        if db.engine == 'postgresql':
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                ('qr_scans',)
            )
            table_exists = cur.fetchone() is not None
        else:
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                ('qr_scans',)
            )
            table_exists = cur.fetchone() is not None
        
        if not table_exists:
            if db.engine == 'postgresql':
                cur.execute("""
                    CREATE TABLE qr_scans (
                        id SERIAL PRIMARY KEY,
                        qr_data TEXT NOT NULL,
                        scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        order_id INTEGER REFERENCES orders(id),
                        station_id REAL,
                        notes TEXT
                    )
                """)
            else:
                cur.execute("""
                    CREATE TABLE qr_scans (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        qr_data TEXT NOT NULL,
                        scan_time TEXT DEFAULT CURRENT_TIMESTAMP,
                        order_id INTEGER REFERENCES orders(id),
                        station_id REAL,
                        notes TEXT
                    )
                """)
            conn.commit()
            logger.info("Таблица qr_scans создана")
        
        conn.close()
    
    # Инициализация таблицы при старте
    init_qr_table()
    
    @app.route('/')
    def index():
        """Главная страница с QR-сканером"""
        return render_template('index.html')
    
    @app.route('/api/health')
    def health():
        """Проверка работоспособности API"""
        return jsonify({'status': 'ok', 'service': 'QR Scanner with DB'})
    
    @app.route('/api/scan', methods=['POST'])
    def save_scan():
        """Сохранение QR-кода в базу данных"""
        data = request.get_json()
        
        if not data or 'qr_data' not in data:
            return jsonify({'error': 'qr_data required'}), 400
        
        qr_data = data['qr_data']
        order_id = data.get('order_id')
        station_id = data.get('station_id')
        notes = data.get('notes', '')
        
        try:
            conn = db.get_connection()
            cur = db.cursor(conn)
            
            placeholder = db.placeholder()
            
            sql = f"""
                INSERT INTO qr_scans (qr_data, order_id, station_id, notes)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
            """
            
            params = (qr_data, order_id, station_id, notes)
            cur.execute(sql, params)
            
            scan_id = db.lastrowid(cur)
            conn.commit()
            conn.close()
            
            logger.info(f"QR-код сохранён: ID={scan_id}, data={qr_data[:50]}...")
            
            return jsonify({
                'success': True,
                'scan_id': scan_id,
                'qr_data': qr_data,
                'message': 'QR-код успешно сохранён'
            })
            
        except Exception as e:
            logger.error(f"Ошибка сохранения QR-кода: {e}", exc_info=True)
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/scans', methods=['GET'])
    def get_scans():
        """Получение истории сканирований"""
        limit = request.args.get('limit', 50, type=int)
        order_id = request.args.get('order_id', type=int)
        station_id = request.args.get('station_id', type=float)
        
        try:
            conn = db.get_connection()
            cur = db.cursor(conn)
            
            sql = "SELECT * FROM qr_scans WHERE 1=1"
            params = []
            
            if order_id:
                sql += f" AND order_id {db.placeholder()}"
                params.append(order_id)
            
            if station_id:
                sql += f" AND station_id {db.placeholder()}"
                params.append(station_id)
            
            sql += f" ORDER BY scan_time DESC LIMIT {limit}"
            
            cur.execute(sql, params)
            rows = cur.fetchall()
            conn.close()
            
            scans = []
            for row in rows:
                scans.append({
                    'id': row['id'],
                    'qr_data': row['qr_data'],
                    'scan_time': row['scan_time'],
                    'order_id': row['order_id'],
                    'station_id': row['station_id'],
                    'notes': row['notes']
                })
            
            return jsonify({'scans': scans, 'count': len(scans)})
            
        except Exception as e:
            logger.error(f"Ошибка получения сканирований: {e}", exc_info=True)
            if 'conn' in locals():
                conn.close()
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/scans/<int:scan_id>', methods=['DELETE'])
    def delete_scan(scan_id):
        """Удаление записи сканирования"""
        try:
            conn = db.get_connection()
            cur = db.cursor(conn)
            
            placeholder = db.placeholder()
            cur.execute(f"DELETE FROM qr_scans WHERE id={placeholder}", (scan_id,))
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Запись удалена'})
            
        except Exception as e:
            logger.error(f"Ошибка удаления сканирования: {e}", exc_info=True)
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return jsonify({'error': str(e)}), 500
    
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
    logger.info('Запуск QR Scanner с поддержкой БД...')
    logger.info('Открыть в браузере: http://localhost:5001')
    serve(app, host='0.0.0.0', port=5001, threads=4)

if __name__ == '__main__':
    main()
