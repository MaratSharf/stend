"""
Tests for the Flask API endpoints.
"""
import json


class TestGetOrders:
    def test_empty_orders(self, logged_client):
        resp = logged_client.get('/api/orders')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == []

    def test_filter_by_status(self, logged_client):
        logged_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 2
        })
        resp = logged_client.get('/api/orders?status=buffer')
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2


class TestCreateOrder:
    def test_create_single_order(self, logged_client):
        resp = logged_client.post('/api/orders', json={
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

    def test_create_multiple_orders(self, logged_client):
        resp = logged_client.post('/api/orders', json={
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

    def test_create_order_missing_fields(self, logged_client):
        resp = logged_client.post('/api/orders', json={'batch': 'B1'})
        assert resp.status_code == 400

    def test_create_order_no_body(self, logged_client):
        resp = logged_client.post('/api/orders', content_type='application/json')
        assert resp.status_code == 400

    def test_create_order_bad_quantity(self, logged_client):
        resp = logged_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 'abc'
        })
        assert resp.status_code == 400

    def test_create_unauthorized(self, unauth_client):
        """No session + no API key → 401."""
        resp = unauth_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 10
        })
        assert resp.status_code == 401

    def test_create_wrong_key(self, client):
        """Wrong API key → 401."""
        resp = client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 10
        }, headers={'X-API-Key': 'wrong-key'})
        assert resp.status_code == 401


class TestLaunchOrder:
    def test_launch_success(self, logged_client):
        order_resp = logged_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 1
        })
        order_id = order_resp.get_json()['orders'][0]['id']

        resp = logged_client.post(f'/api/orders/{order_id}/launch')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_launch_nonexistent(self, logged_client):
        resp = logged_client.post('/api/orders/9999/launch')
        assert resp.status_code == 400

    def test_launch_unauthorized(self, unauth_client):
        """No session + no API key → 401."""
        resp = unauth_client.post('/api/orders/1/launch')
        assert resp.status_code == 401


class TestMoveOrder:
    def test_move_success(self, logged_client):
        order_resp = logged_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 1
        })
        order_id = order_resp.get_json()['orders'][0]['id']
        logged_client.post(f'/api/orders/{order_id}/launch')

        resp = logged_client.post(f'/api/orders/{order_id}/move')
        assert resp.status_code == 200
        assert resp.get_json()['order']['current_station'] == 1.1

    def test_move_unauthorized(self, unauth_client):
        resp = unauth_client.post('/api/orders/1/move')
        assert resp.status_code == 401


class TestCompleteOrder:
    def test_complete_success(self, logged_client):
        order_resp = logged_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 1
        })
        order_id = order_resp.get_json()['orders'][0]['id']
        logged_client.post(f'/api/orders/{order_id}/launch')

        resp = logged_client.post(f'/api/orders/{order_id}/complete')
        assert resp.status_code == 200
        assert resp.get_json()['order']['status'] == 'completed'

    def test_complete_unauthorized(self, unauth_client):
        resp = unauth_client.post('/api/orders/1/complete')
        assert resp.status_code == 401


class TestCancelOrder:
    def test_cancel_success(self, logged_client):
        order_resp = logged_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 1
        })
        order_id = order_resp.get_json()['orders'][0]['id']

        resp = logged_client.post(f'/api/orders/{order_id}/cancel')
        assert resp.status_code == 200
        assert resp.get_json()['order']['status'] == 'cancelled'

    def test_cancel_unauthorized(self, unauth_client):
        resp = unauth_client.post('/api/orders/1/cancel')
        assert resp.status_code == 401


class TestStations:
    def test_get_stations(self, logged_client):
        resp = logged_client.get('/api/stations')
        assert resp.status_code == 200
        assert len(resp.get_json()) == 13  # 10 main + 3 sub-stations


class TestStatistics:
    def test_get_statistics(self, logged_client):
        resp = logged_client.get('/api/statistics')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'total' in data
        assert 'completion_rate' in data

    def test_statistics_reflects_orders(self, logged_client):
        logged_client.post('/api/orders', json={
            'batch': 'B1', 'product_code': 'P1',
            'color': 'R', 'quantity': 5
        })
        resp = logged_client.get('/api/statistics')
        assert resp.get_json()['total'] == 5


class TestPageRoutes:
    def test_index(self, logged_client):
        resp = logged_client.get('/')
        assert resp.status_code == 200

    def test_tracking(self, logged_client):
        resp = logged_client.get('/tracking')
        assert resp.status_code == 200

    def test_station(self, logged_client):
        resp = logged_client.get('/station')
        assert resp.status_code == 200

    def test_map(self, logged_client):
        resp = logged_client.get('/map')
        assert resp.status_code == 200

    def test_login_page(self, client):
        """Login page is accessible without auth."""
        resp = client.get('/login')
        assert resp.status_code == 200

    def test_login_redirect(self, client):
        """Unauthenticated user is redirected to /login."""
        resp = client.get('/', follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_logout(self, logged_client):
        resp = logged_client.get('/logout', follow_redirects=True)
        assert resp.status_code == 200
        assert '/login' in resp.request.path


class TestUserAuth:
    """Tests for user login functionality."""

    def test_login_success(self, client):
        resp = client.post('/login', data={
            'username': 'admin',
            'password': 'admin'
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_login_wrong_password(self, client):
        """Wrong password renders login page with error (200)."""
        resp = client.post('/login', data={
            'username': 'admin',
            'password': 'wrong'
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_users_page_requires_admin(self, client, logged_client):
        """Non-admin cannot access /users."""
        # Login as viewer
        resp = client.post('/login', data={
            'username': 'viewer',
            'password': 'viewer'
        }, follow_redirects=True)
        assert resp.status_code == 200

        # Viewer is redirected from /users (not forbidden = not admin)
        resp = client.get('/users', follow_redirects=False)
        assert resp.status_code in (301, 302)

        # Admin can access
        resp = logged_client.get('/users')
        assert resp.status_code == 200
