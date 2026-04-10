"""
Tests for the Database module.
"""
import re
import time
from utils.database import Database


class TestDatabaseInit:
    def test_creates_tables(self, db):
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row['name'] for row in cursor.fetchall()]
        conn.close()

        assert 'orders' in tables
        assert 'stations' in tables
        assert 'station_log' in tables

    def test_initialises_10_stations(self, db):
        stations = db.get_stations()
        assert len(stations) == 10
        assert stations[0]['name'] == "Station 1"
        assert stations[9]['name'] == "Station 10"


class TestOrderNumberFormat:
    def test_format_matches_ord_pattern(self, db):
        order_number = db.get_next_order_number("TEST")
        # Should match ORD-XXXX-XXX pattern
        assert re.match(r'^ORD-\d{4}-\d{3}$', order_number), f"Invalid format: {order_number}"

    def test_multiple_orders_have_unique_numbers(self, db):
        numbers = set()
        for _ in range(20):
            num = db.get_next_order_number("TEST")
            numbers.add(num)
            time.sleep(0.001)  # Small delay to ensure timestamp changes
        # With timestamp + random, should be unique
        assert len(numbers) == 20


class TestCreateOrder:
    def test_creates_multiple_orders(self, controller):
        result = controller.create_order("BATCH-A", "PROD-1", "Red", 3)
        orders = result['orders']
        assert len(orders) == 3
        for order in orders:
            assert order['batch'] == "BATCH-A"
            assert order['product_code'] == "PROD-1"
            assert order['color'] == "Red"
            assert order['quantity'] == 1
            assert order['status'] == 'buffer'
            assert order['current_station'] is None
            assert re.match(r'^ORD-\d{4}-\d{3}$', order['order_number'])

    def test_single_order_creation(self, controller):
        result = controller.create_order("BATCH-B", "PROD-2", "Blue", 1)
        orders = result['orders']
        assert len(orders) == 1
        assert orders[0]['batch'] == "BATCH-B"

    def test_order_numbers_are_unique(self, controller):
        result = controller.create_order("BATCH-C", "PROD-3", "Green", 5)
        orders = result['orders']
        order_numbers = [o['order_number'] for o in orders]
        assert len(set(order_numbers)) == 5


class TestGetOrders:
    def test_empty_db(self, controller):
        assert controller.get_orders() == []

    def test_returns_all_orders(self, controller):
        controller.create_order("B1", "P1", "R", 2)
        controller.create_order("B2", "P2", "G", 1)
        orders = controller.get_orders()
        assert len(orders) == 3

    def test_filter_by_status(self, controller):
        controller.create_order("B1", "P1", "R", 2)
        controller.create_order("B2", "P2", "G", 1)
        orders = controller.get_orders(status='buffer')
        assert len(orders) == 3


class TestLaunchOrder:
    def test_launch_moves_to_station_1(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        result = controller.launch_order(orders[0]['id'])
        assert result['success'] is True
        assert result['order']['status'] == 'production'
        assert result['order']['current_station'] == 1

    def test_launch_buffer_order_only(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        controller.launch_order(orders[0]['id'])
        result = controller.launch_order(orders[0]['id'])
        assert result['success'] is False

    def test_launch_station_occupied(self, controller):
        r1 = controller.create_order("B1", "P1", "R", 1)
        r2 = controller.create_order("B2", "P2", "G", 1)
        o1 = r1['orders'][0]
        o2 = r2['orders'][0]
        controller.launch_order(o1['id'])
        result = controller.launch_order(o2['id'])
        assert result['success'] is False


class TestMoveOrder:
    def test_move_to_next_station(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        controller.launch_order(orders[0]['id'])
        result = controller.move_order(orders[0]['id'])
        assert result['success'] is True
        assert result['order']['current_station'] == 2

    def test_auto_complete_at_station_10(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        controller.launch_order(orders[0]['id'])
        # Move through stations 2-10 (9 moves from station 1)
        for _ in range(9):
            controller.move_order(orders[0]['id'])
        order_data = controller.get_order(orders[0]['id'])
        assert order_data['status'] == 'completed'

    def test_move_not_production(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        result = controller.move_order(orders[0]['id'])
        assert result['success'] is False


class TestCompleteOrder:
    def test_complete_production_order(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        controller.launch_order(orders[0]['id'])
        result = controller.complete_order(orders[0]['id'])
        assert result['success'] is True
        assert result['order']['status'] == 'completed'

    def test_complete_buffer_order_fails(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        result = controller.complete_order(orders[0]['id'])
        assert result['success'] is False


class TestCancelOrder:
    def test_cancel_buffer_order(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        result = controller.cancel_order(orders[0]['id'])
        assert result['success'] is True
        assert result['order']['status'] == 'cancelled'

    def test_cancel_completed_fails(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        controller.launch_order(orders[0]['id'])
        controller.complete_order(orders[0]['id'])
        result = controller.cancel_order(orders[0]['id'])
        assert result['success'] is False

    def test_cancel_already_cancelled(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        controller.cancel_order(orders[0]['id'])
        result = controller.cancel_order(orders[0]['id'])
        assert result['success'] is False


class TestStatistics:
    def test_initial_stats(self, controller):
        stats = controller.get_statistics()
        assert stats['total'] == 0
        assert stats['completion_rate'] == 0.0

    def test_stats_with_orders(self, controller):
        r1 = controller.create_order("B1", "P1", "R", 1)
        r2 = controller.create_order("B2", "P2", "G", 2)
        o1 = r1['orders'][0]
        controller.launch_order(o1['id'])
        controller.complete_order(o1['id'])

        stats = controller.get_statistics()
        assert stats['total'] == 3
        assert stats['completed'] == 1
        assert stats['buffer'] == 2
        assert stats['completion_rate'] == round((1 / 3) * 100, 2)


class TestStations:
    def test_stations_show_current_orders(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        controller.launch_order(orders[0]['id'])
        stations = controller.get_stations()
        assert stations[0]['order_id'] == orders[0]['id']
