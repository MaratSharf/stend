"""
MES Production System - Database utility
Handles SQLite database operations for orders, stations, and station logs.
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()
    
    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database tables."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch TEXT NOT NULL,
                order_number TEXT UNIQUE NOT NULL,
                product_code TEXT NOT NULL,
                color TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT DEFAULT 'buffer',
                current_station INTEGER,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            )
        ''')
        
        # Stations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stations (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                order_id INTEGER,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        ''')
        
        # Station log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS station_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                station_id INTEGER NOT NULL,
                entered_at TEXT NOT NULL,
                exited_at TEXT,
                result TEXT DEFAULT 'OK',
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (station_id) REFERENCES stations(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def init_stations(self, station_names: List[str]):
        """Initialize stations with given names."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        for i, name in enumerate(station_names, 1):
            cursor.execute('''
                INSERT OR IGNORE INTO stations (id, name, order_id)
                VALUES (?, ?, NULL)
            ''', (i, name))
        
        conn.commit()
        conn.close()
    
    def get_next_order_number(self, batch: str) -> str:
        """Generate next order number for a batch."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT order_number FROM orders 
            WHERE batch = ? AND order_number LIKE ?
            ORDER BY id DESC LIMIT 1
        ''', (batch, f'{batch}-%'))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            last_num = int(row['order_number'].split('-')[-1])
            return f"{batch}-{last_num + 1:03d}"
        else:
            return f"{batch}-001"
    
    def create_order(self, batch: str, product_code: str, color: str, quantity: int) -> List[Dict[str, Any]]:
        """Create multiple orders based on quantity."""
        created_orders = []
        
        for i in range(quantity):
            order_number = self.get_next_order_number(batch)
            created_at = datetime.now().isoformat()
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO orders (batch, order_number, product_code, color, quantity, status, current_station, created_at)
                VALUES (?, ?, ?, ?, ?, 'buffer', NULL, ?)
            ''', (batch, order_number, product_code, color, 1, created_at))
            
            order_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            created_orders.append({
                'id': order_id,
                'batch': batch,
                'order_number': order_number,
                'product_code': product_code,
                'color': color,
                'quantity': 1,
                'status': 'buffer',
                'current_station': None,
                'created_at': created_at,
                'started_at': None,
                'completed_at': None
            })
        
        return created_orders
    
    def get_orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all orders, optionally filtered by status."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute('SELECT * FROM orders WHERE status = ? ORDER BY id DESC', (status,))
        else:
            cursor.execute('SELECT * FROM orders ORDER BY id DESC')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        """Get a single order by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def launch_order(self, order_id: int) -> bool:
        """Launch an order to station 1."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if station 1 is free
        cursor.execute('SELECT order_id FROM stations WHERE id = 1')
        row = cursor.fetchone()
        
        if row and row['order_id'] is not None:
            conn.close()
            return False
        
        started_at = datetime.now().isoformat()
        
        cursor.execute('''
            UPDATE orders 
            SET status = 'production', current_station = 1, started_at = ?
            WHERE id = ? AND status = 'buffer'
        ''', (started_at, order_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return False
        
        # Assign order to station 1
        cursor.execute('''
            UPDATE stations SET order_id = ? WHERE id = 1
        ''', (order_id,))
        
        # Log entry
        cursor.execute('''
            INSERT INTO station_log (order_id, station_id, entered_at, result)
            VALUES (?, ?, ?, 'OK')
        ''', (order_id, 1, started_at))
        
        conn.commit()
        conn.close()
        return True
    
    def move_order(self, order_id: int) -> bool:
        """Move order to next station."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        order = self.get_order(order_id)
        if not order or order['status'] != 'production':
            conn.close()
            return False
        
        current_station = order['current_station']
        if current_station is None or current_station >= 10:
            conn.close()
            return False
        
        next_station = current_station + 1
        
        # Check if next station is free
        cursor.execute('SELECT order_id FROM stations WHERE id = ?', (next_station,))
        row = cursor.fetchone()
        
        if row and row['order_id'] is not None:
            conn.close()
            return False
        
        exited_at = datetime.now().isoformat()
        
        # Update log for current station
        cursor.execute('''
            UPDATE station_log 
            SET exited_at = ?, result = 'OK'
            WHERE order_id = ? AND station_id = ? AND exited_at IS NULL
        ''', (exited_at, order_id, current_station))
        
        # Free current station
        cursor.execute('''
            UPDATE stations SET order_id = NULL WHERE id = ?
        ''', (current_station,))
        
        # Assign to next station
        cursor.execute('''
            UPDATE stations SET order_id = ? WHERE id = ?
        ''', (order_id, next_station))
        
        # Update order
        cursor.execute('''
            UPDATE orders SET current_station = ? WHERE id = ?
        ''', (next_station, order_id))
        
        # Log entry to next station
        entered_at = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO station_log (order_id, station_id, entered_at, result)
            VALUES (?, ?, ?, 'OK')
        ''', (order_id, next_station, entered_at))
        
        conn.commit()
        conn.close()
        return True
    
    def complete_order(self, order_id: int) -> bool:
        """Complete an order (mark as completed)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        order = self.get_order(order_id)
        if not order or order['status'] != 'production':
            conn.close()
            return False
        
        completed_at = datetime.now().isoformat()
        current_station = order['current_station']
        
        # Update order status
        cursor.execute('''
            UPDATE orders 
            SET status = 'completed', current_station = NULL, completed_at = ?
            WHERE id = ?
        ''', (completed_at, order_id))
        
        # Free current station if any
        if current_station:
            cursor.execute('''
                UPDATE stations SET order_id = NULL WHERE id = ?
            ''', (current_station,))
            
            # Update log
            cursor.execute('''
                UPDATE station_log 
                SET exited_at = ?, result = 'OK'
                WHERE order_id = ? AND station_id = ? AND exited_at IS NULL
            ''', (completed_at, order_id, current_station))
        
        conn.commit()
        conn.close()
        return True
    
    def cancel_order(self, order_id: int) -> bool:
        """Cancel an order."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        order = self.get_order(order_id)
        if not order or order['status'] in ('completed', 'cancelled'):
            conn.close()
            return False
        
        current_station = order['current_station']
        
        # Update order status
        cursor.execute('''
            UPDATE orders SET status = 'cancelled', current_station = NULL
            WHERE id = ?
        ''', (order_id,))
        
        # Free current station if any
        if current_station:
            cursor.execute('''
                UPDATE stations SET order_id = NULL WHERE id = ?
            ''', (current_station,))
        
        conn.commit()
        conn.close()
        return True
    
    def get_stations(self) -> List[Dict[str, Any]]:
        """Get all stations with their current orders."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.id, s.name, s.order_id, o.order_number, o.product_code, o.color, o.quantity
            FROM stations s
            LEFT JOIN orders o ON s.order_id = o.id
            ORDER BY s.id
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get production statistics."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Total orders
        cursor.execute('SELECT COUNT(*) as count FROM orders')
        stats['total'] = cursor.fetchone()['count']
        
        # By status
        cursor.execute('''
            SELECT status, COUNT(*) as count FROM orders GROUP BY status
        ''')
        for row in cursor.fetchall():
            stats[row['status']] = row['count']
        
        # In production
        stats['in_production'] = stats.get('production', 0)
        
        # Completion rate
        if stats['total'] > 0:
            stats['completion_rate'] = round(
                (stats.get('completed', 0) / stats['total']) * 100, 2
            )
        else:
            stats['completion_rate'] = 0.0
        
        conn.close()
        return stats
