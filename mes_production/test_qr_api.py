#!/usr/bin/env python
"""
Проверка API QR-сканера
"""
import requests

MES_API_URL = 'http://localhost:5000'
QR_SCANNER_URL = 'http://localhost:5001'
API_KEY = 'change-me-to-a-secure-key'

print("Проверка API станций MES...")
try:
    response = requests.get(
        f'{MES_API_URL}/api/stations',
        headers={'X-API-Key': API_KEY},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        stations = response.json()
        station_6_1 = next((s for s in stations if s['id'] == 6.1), None)
        print(f"Станция 6.1: {station_6_1}")
except Exception as e:
    print(f"Ошибка: {e}")

print("\nПроверка API QR-сканера /api/current-order...")
try:
    response = requests.get(
        f'{QR_SCANNER_URL}/api/current-order',
        headers={'X-API-Key': API_KEY},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Ошибка: {e}")
