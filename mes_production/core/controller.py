"""
MES Production System - Controller
Manages orders and station operations.
"""
from typing import Optional, List, Dict, Any
from utils.database import Database


class Controller:
    def __init__(self, db: Database):
        self.db = db
    
    def create_order(self, batch: str, product_code: str, color: str, quantity: int) -> Dict[str, Any]:
        """Create multiple orders based on quantity."""
        created_orders = self.db.create_order(batch, product_code, color, quantity)
        
        return {
            'success': True,
            'orders': created_orders,
            'count': len(created_orders),
            'message': f'Created {len(created_orders)} order(s)'
        }
    
    def get_orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all orders, optionally filtered by status."""
        return self.db.get_orders(status)
    
    def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        """Get a single order by ID."""
        return self.db.get_order(order_id)
    
    def launch_order(self, order_id: int) -> Dict[str, Any]:
        """Launch an order to production (station 1)."""
        success = self.db.launch_order(order_id)
        order = self.db.get_order(order_id)
        
        return {
            'success': success,
            'order': order,
            'message': 'Order launched successfully' if success else 'Failed to launch order (station 1 may be occupied or order not in buffer)'
        }
    
    def move_order(self, order_id: int) -> Dict[str, Any]:
        """Move order to next station."""
        success = self.db.move_order(order_id)
        order = self.db.get_order(order_id)
        
        # Check if order completed all stations
        if success and order and order['current_station'] == 10:
            # Auto-complete when reaching station 10
            self.db.complete_order(order_id)
            order = self.db.get_order(order_id)
            return {
                'success': True,
                'order': order,
                'message': 'Order moved to station 10 and completed automatically'
            }
        
        return {
            'success': success,
            'order': order,
            'message': 'Order moved successfully' if success else 'Failed to move order (next station may be occupied)'
        }
    
    def complete_order(self, order_id: int) -> Dict[str, Any]:
        """Complete an order manually."""
        success = self.db.complete_order(order_id)
        order = self.db.get_order(order_id)
        
        return {
            'success': success,
            'order': order,
            'message': 'Order completed successfully' if success else 'Failed to complete order'
        }
    
    def cancel_order(self, order_id: int) -> Dict[str, Any]:
        """Cancel an order."""
        success = self.db.cancel_order(order_id)
        order = self.db.get_order(order_id)
        
        return {
            'success': success,
            'order': order,
            'message': 'Order cancelled successfully' if success else 'Failed to cancel order'
        }
    
    def get_stations(self) -> List[Dict[str, Any]]:
        """Get all stations with current orders."""
        return self.db.get_stations()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get production statistics."""
        return self.db.get_statistics()
