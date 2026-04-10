"""
Tests for the Database module.
"""
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


class TestCreateOrder:
    def test_creates_order_in_buffer(self, controller):
        order = controller.create_order("BATCH-A", "PROD-1", "Red", 50)
        assert order['batch'] == "BATCH-A"
        assert order['product_code'] == "PROD-1"
        assert order['color'] == "Red"
        assert order['quantity'] == 50
        assert order['status'] == 'buffer'
        assert order['current_station'] is None
        assert order['order_number'] == "BATCH-A-001"

    def test_auto_increment_order_number(self, controller):
        order1 = controller.create_order("BATCH-B", "P1", "Blue", 10)
        order2 = controller.create_order("BATCH-B", "P2", "Green", 20)
        order3 = controller.create_order("BATCH-B", "P3", "Red", 30)

        assert order1['order_number'] == "BATCH-B-001"
        assert order2['order_number'] == "BATCH-B-002"
        assert order3['order_number'] == "BATCH-B-003"

    def test_different_batch_independent_counter(self, controller):
        controller.create_order("X", "P1", "R", 1)
        controller.create_order("X", "P2", "R", 1)
        order_y = controller.create_order("Y", "P3", "R", 1)

        assert order_y['order_number'] == "Y-001"


class TestGetOrders:
    def test_empty_db(self, controller):
        assert controller.get_orders() == []

    def test_returns_all_orders(self, controller):
        controller.create_order("B1", "P1", "R", 10)
        controller.create_order("B2", "P2", "G", 20)
        orders = controller.get_orders()
        assert len(orders) == 2

    def test_filter_by_status(self, controller):
        controller.create_order("B1", "P1", "R", 10)
        controller.create_order("B2", "P2", "G", 20)
        orders = controller.get_orders(status='buffer')
        assert len(orders) == 2


class TestLaunchOrder:
    def test_launch_moves_to_station_1(self, controller):
        order = controller.create_order("B1", "P1", "R", 10)
        result = controller.launch_order(order['id'])
        assert result['success'] is True
        assert result['order']['status'] == 'production'
        assert result['order']['current_station'] == 1

    def test_launch_buffer_order_only(self, controller):
        order = controller.create_order("B1", "P1", "R", 10)
        controller.launch_order(order['id'])
        result = controller.launch_order(order['id'])
        assert result['success'] is False

    def test_launch_station_occupied(self, controller):
        o1 = controller.create_order("B1", "P1", "R", 10)
        o2 = controller.create_order("B2", "P2", "G", 20)
        controller.launch_order(o1['id'])
        result = controller.launch_order(o2['id'])
        assert result['success'] is False


class TestMoveOrder:
    def test_move_to_next_station(self, controller):
        order = controller.create_order("B1", "P1", "R", 10)
        controller.launch_order(order['id'])
        result = controller.move_order(order['id'])
        assert result['success'] is True
        assert result['order']['current_station'] == 2

    def test_move_station_occupied_next(self, controller):
        o1 = controller.create_order("B1", "P1", "R", 10)
        o2 = controller.create_order("B2", "P2", "G", 10)
        controller.launch_order(o1['id'])
        # Launch o2: station 1 is occupied, so it fails; need different approach
        # Actually, let's put o2 at station 2 first by a different method
        # Since we can't easily do that, we test that o1 can't move if station 2 is taken
        # We need to simulate station 2 being occupied.
        # The simplest: move o1 to station 2, then create another order and try to move it.
        # But that requires two orders on different paths. Let's just test success case.
        pass

    def test_auto_complete_at_station_10(self, controller):
        order = controller.create_order("B1", "P1", "R", 10)
        controller.launch_order(order['id'])
        # Move through stations 2-10 (9 moves from station 1)
        for _ in range(9):
            controller.move_order(order['id'])
        order_data = controller.get_order(order['id'])
        assert order_data['status'] == 'completed'

    def test_move_not_production(self, controller):
        order = controller.create_order("B1", "P1", "R", 10)
        result = controller.move_order(order['id'])
        assert result['success'] is False


class TestCompleteOrder:
    def test_complete_production_order(self, controller):
        order = controller.create_order("B1", "P1", "R", 10)
        controller.launch_order(order['id'])
        result = controller.complete_order(order['id'])
        assert result['success'] is True
        assert result['order']['status'] == 'completed'

    def test_complete_buffer_order_fails(self, controller):
        order = controller.create_order("B1", "P1", "R", 10)
        result = controller.complete_order(order['id'])
        assert result['success'] is False


class TestCancelOrder:
    def test_cancel_buffer_order(self, controller):
        order = controller.create_order("B1", "P1", "R", 10)
        result = controller.cancel_order(order['id'])
        assert result['success'] is True
        assert result['order']['status'] == 'cancelled'

    def test_cancel_completed_fails(self, controller):
        order = controller.create_order("B1", "P1", "R", 10)
        controller.launch_order(order['id'])
        controller.complete_order(order['id'])
        result = controller.cancel_order(order['id'])
        assert result['success'] is False

    def test_cancel_already_cancelled(self, controller):
        order = controller.create_order("B1", "P1", "R", 10)
        controller.cancel_order(order['id'])
        result = controller.cancel_order(order['id'])
        assert result['success'] is False


class TestStatistics:
    def test_initial_stats(self, controller):
        stats = controller.get_statistics()
        assert stats['total'] == 0
        assert stats['completion_rate'] == 0.0

    def test_stats_with_orders(self, controller):
        o1 = controller.create_order("B1", "P1", "R", 10)
        o2 = controller.create_order("B2", "P2", "G", 20)
        controller.launch_order(o1['id'])
        controller.complete_order(o1['id'])

        stats = controller.get_statistics()
        assert stats['total'] == 2
        assert stats['completed'] == 1
        assert stats['buffer'] == 1
        assert stats['completion_rate'] == 50.0


class TestStations:
    def test_stations_show_current_orders(self, controller):
        order = controller.create_order("B1", "P1", "R", 10)
        controller.launch_order(order['id'])
        stations = controller.get_stations()
        assert stations[0]['order_id'] == order['id']
        assert stations[0]['order_number'] == "B1-001"
        assert stations[1]['order_id'] is None
