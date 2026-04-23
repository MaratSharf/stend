"""
Tests for the Database module.
"""
import re
from utils.database import Database


class TestDatabaseInit:
    def test_creates_tables(self, db):
        conn = db.get_connection()
        cursor = db._cursor(conn)
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        tables = [row['table_name'] for row in cursor.fetchall()]
        conn.close()

        assert 'orders' in tables
        assert 'stations' in tables
        assert 'station_log' in tables

    def test_initialises_stations(self, db):
        stations = db.get_stations()
        assert len(stations) == 13  # 10 main + 3 sub-stations
        assert stations[0]['id'] == 1.0
        assert stations[1]['id'] == 1.1
        assert stations[2]['id'] == 1.2


class TestOrderNumberFormat:
    def test_format_matches_ord_pattern(self, controller):
        result = controller.create_order("TEST", "PROD-X", "Black", 1)
        order_number = result['orders'][0]['order_number']
        assert re.match(r'^ORD-\d{4,}, order_number), f"Invalid format: {order_number}"

    def test_multiple_orders_have_sequential_numbers(self, controller):
        result = controller.create_order("BATCH-TEST", "PROD-X", "Black", 5)
        orders = result['orders']
        numbers = [o['order_number'] for o in orders]
        # Sequential numbers should increment
        assert all(re.match(r'^ORD-\d{4,}, n) for n in numbers)
        for i in range(1, len(numbers)):
            prev_id = int(numbers[i - 1].split('-')[1])
            curr_id = int(numbers[i].split('-')[1])
            assert curr_id == prev_id + 1


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
            assert re.match(r'^ORD-\d{4,}, order['order_number'])

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

    def test_launch_multiple_orders_to_same_station(self, controller):
        """Multiple orders can be launched to station 1 simultaneously."""
        r1 = controller.create_order("B1", "P1", "R", 1)
        r2 = controller.create_order("B2", "P2", "G", 1)
        o1 = r1['orders'][0]
        o2 = r2['orders'][0]
        assert controller.launch_order(o1['id'])['success'] is True
        assert controller.launch_order(o2['id'])['success'] is True
        # Both orders should now be on station 1
        assert controller.get_order(o1['id'])['current_station'] == 1
        assert controller.get_order(o2['id'])['current_station'] == 1


class TestMoveOrder:
    def test_move_to_next_station(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        controller.launch_order(orders[0]['id'])
        # Station 1 has sub-stations 1.1, 1.2 — complete them first
        controller.db.complete_sub_station(orders[0]['id'], 1.1)
        controller.db.complete_sub_station(orders[0]['id'], 1.2)
        result = controller.move_order(orders[0]['id'])
        assert result['success'] is True
        assert result['order']['current_station'] == 2.0

    def test_move_blocked_by_pending_subs(self, controller):
        """Cannot move from station 1 if sub-stations aren't completed."""
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        controller.launch_order(orders[0]['id'])
        result = controller.move_order(orders[0]['id'])
        assert result['success'] is False
        assert 'подстанции' in result['message'].lower()

    def test_auto_complete_at_last_station(self, controller):
        result = controller.create_order("B1", "P1", "R", 1)
        orders = result['orders']
        controller.launch_order(orders[0]['id'])
        # Complete sub-stations for station 1
        controller.db.complete_sub_station(orders[0]['id'], 1.1)
        controller.db.complete_sub_station(orders[0]['id'], 1.2)
        # Now move from 1.0 → 2.0 (1 move)
        controller.move_order(orders[0]['id'])
        # 2.0 has no subs → move 2.0 → 3.0 (2nd move)
        controller.move_order(orders[0]['id'])
        # Complete sub-stations for station 3
        controller.db.complete_sub_station(orders[0]['id'], 3.1)
        # Move 3.0 → 4.0 (3rd move)
        controller.move_order(orders[0]['id'])
        # Remaining: 4→5→6→7→8→9→10 = 6 more moves
        for _ in range(6):
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
        assert stations[0]['name'] == "Station 1"
        assert len(stations[0]['orders']) == 1
        assert stations[0]['orders'][0]['id'] == orders[0]['id']