#!/usr/bin/env python
"""
Проверка API станций после миграции
"""
import sys
sys.path.insert(0, 'mes_production')

from web.app import create_app
from core.controller import Controller
from utils.database import Database

app = create_app()

with app.app_context():
    with app.test_client() as client:
        # Тест без API ключа (публичный endpoint)
        response = client.get('/api/stations')
        print(f"GET /api/stations — Status: {response.status_code}")
        
        import json
        stations = response.get_json()
        
        print("\nВсе станции:")
        for s in stations:
            print(f"  ID={s['id']}, name={s['name']}, order_id={s.get('order_id')}")
        
        # Проверка станции 6.1
        station_6_1 = next((s for s in stations if s['id'] == 6.1), None)
        if station_6_1:
            print(f"\n✓ Станция 6.1 найдена: {station_6_1}")
        else:
            print("\n✗ Станция 6.1 НЕ найдена!")