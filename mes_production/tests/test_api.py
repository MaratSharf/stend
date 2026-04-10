"""
Tests for the Flask API endpoints.
"""
import json


class TestGetOrders:
    def test_empty_orders(self, client):
        resp = client.get('/api/orders')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == []

    def test_filter_by_status(self, auth_client, client):
        auth_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 2
        })
        resp = client.get('/api/orders?status=buffer')
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2


class TestCreateOrder:
    def test_create_single_order(self, auth_client):
        resp = auth_client.post('/api/orders', json={
            'batch': 'BATCH-1',
            'product_code': 'PROD-42',
            'color': 'Blue',
            'quantity': 1
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['count'] == 1
        assert len(data['orders']) == 1
        assert data['orders'][0]['batch'] == 'BATCH-1'
        assert data['orders'][0]['status'] == 'buffer'

    def test_create_multiple_orders(self, auth_client):
        resp = auth_client.post('/api/orders', json={
            'batch': 'BATCH-2',
            'product_code': 'PROD-43',
            'color': 'Red',
            'quantity': 3
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['count'] == 3
        assert len(data['orders']) == 3
        for order in data['orders']:
            assert order['batch'] == 'BATCH-2'
            assert order['quantity'] == 1

    def test_create_order_missing_fields(self, auth_client):
        resp = auth_client.post('/api/orders', json={'batch': 'B1'})
        assert resp.status_code == 400

    def test_create_order_no_body(self, auth_client):
        resp = auth_client.post('/api/orders', content_type='application/json')
        assert resp.status_code == 400

    def test_create_order_bad_quantity(self, auth_client):
        resp = auth_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 'abc'
        })
        assert resp.status_code == 400

    def test_create_unauthorized(self, unauth_client):
        resp = unauth_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 10
        })
        assert resp.status_code == 401

    def test_create_wrong_key(self, client):
        resp = client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 10
        }, headers={'X-API-Key': 'wrong-key'})
        assert resp.status_code == 401


class TestLaunchOrder:
    def test_launch_success(self, auth_client):
        order_resp = auth_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 1
        })
        order_id = order_resp.get_json()['orders'][0]['id']

        resp = auth_client.post(f'/api/orders/{order_id}/launch')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_launch_nonexistent(self, auth_client):
        resp = auth_client.post('/api/orders/9999/launch')
        assert resp.status_code == 400

    def test_launch_unauthorized(self, unauth_client):
        resp = unauth_client.post('/api/orders/1/launch')
        assert resp.status_code == 401


class TestMoveOrder:
    def test_move_success(self, auth_client):
        order_resp = auth_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 1
        })
        order_id = order_resp.get_json()['orders'][0]['id']
        auth_client.post(f'/api/orders/{order_id}/launch')

        resp = auth_client.post(f'/api/orders/{order_id}/move')
        assert resp.status_code == 200
        assert resp.get_json()['order']['current_station'] == 2

    def test_move_unauthorized(self, unauth_client):
        resp = unauth_client.post('/api/orders/1/move')
        assert resp.status_code == 401


class TestCompleteOrder:
    def test_complete_success(self, auth_client):
        order_resp = auth_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 1
        })
        order_id = order_resp.get_json()['orders'][0]['id']
        auth_client.post(f'/api/orders/{order_id}/launch')

        resp = auth_client.post(f'/api/orders/{order_id}/complete')
        assert resp.status_code == 200
        assert resp.get_json()['order']['status'] == 'completed'

    def test_complete_unauthorized(self, unauth_client):
        resp = unauth_client.post('/api/orders/1/complete')
        assert resp.status_code == 401


class TestCancelOrder:
    def test_cancel_success(self, auth_client):
        order_resp = auth_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 1
        })
        order_id = order_resp.get_json()['orders'][0]['id']

        resp = auth_client.post(f'/api/orders/{order_id}/cancel')
        assert resp.status_code == 200
        assert resp.get_json()['order']['status'] == 'cancelled'

    def test_cancel_unauthorized(self, unauth_client):
        resp = unauth_client.post('/api/orders/1/cancel')
        assert resp.status_code == 401


class TestStations:
    def test_get_stations(self, client):
        resp = client.get('/api/stations')
        assert resp.status_code == 200
        assert len(resp.get_json()) == 10


class TestStatistics:
    def test_get_statistics(self, client):
        resp = client.get('/api/statistics')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total' in data
        assert 'completion_rate' in data

    def test_statistics_reflects_orders(self, auth_client, client):
        auth_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 5
        })
        resp = client.get('/api/statistics')
        assert resp.get_json()['total'] == 5


class TestPageRoutes:
    def test_index(self, client):
        resp = client.get('/')
        assert resp.status_code == 200

    def test_tracking(self, client):
        resp = client.get('/tracking')
        assert resp.status_code == 200
