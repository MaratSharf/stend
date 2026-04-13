# MES Production System

## Project Overview

**MES (Manufacturing Execution System)** is a web application for managing production orders and tracking their progression through a series of 10 workstations. Built with Python, Flask, and SQLite, it provides a complete production workflow management solution with a web UI and REST API.

### Core Features
- **Batch order creation** — generate multiple orders at once with auto-generated unique numbers
- **Auto-generated order numbers** — format `ORD-<timestamp-last4>-<random-3digits>` (e.g. `ORD-4521-789`)
- **Launch orders** into production and move them through 10 sequential workstations
- **Auto-complete** orders when they reach the final station (Отгрузка)
- **Real-time statistics** — production dashboard with live counts
- **Order status management** — buffer, production, completed, cancelled

### 10 Workstations
1. Приёмка (Receiving) → 2. Сортировка (Sorting) → 3. Подготовка (Preparation) → 4. Сборка (Assembly) → 5. Пайка (Soldering) → 6. Контроль (QC) → 7. Тестирование (Testing) → 8. Упаковка (Packaging) → 9. Маркировка (Labeling) → 10. Отгрузка (Shipping)

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.10+ |
| Web Framework | Flask >= 3.0.0 |
| Production Server | Waitress >= 3.0.0 |
| Database | SQLite (FK enabled, transactions with rollback) |
| Configuration | YAML (PyYAML >= 6.0) |
| Frontend | HTML/CSS/JavaScript (dark/light theme) |
| Testing | pytest >= 8.0, pytest-cov >= 5.0 |

## Project Structure

```
stend/
├── README.md                 # Project documentation
├── QWEN.md                   # AI assistant context
├── .gitignore
├── mes_production/
│   ├── run.py                # Entry point (Waitress server)
│   ├── config.yaml           # System configuration
│   ├── requirements.txt      # Python dependencies
│   ├── pytest.ini            # Pytest configuration
│   ├── core/
│   │   └── controller.py     # Business logic controller
│   ├── utils/
│   │   ├── database.py       # SQLite database operations
│   │   └── logger.py         # Logging setup (no handler duplication)
│   ├── web/
│   │   ├── app.py            # Flask application factory
│   │   ├── auth.py           # API key authentication middleware
│   │   ├── static/           # Static assets (CSS, JS)
│   │   └── templates/        # HTML templates (index, tracking)
│   ├── tests/
│   │   ├── conftest.py       # Shared fixtures (db, controller, auth_client)
│   │   ├── test_database.py  # Unit tests (DB + Controller)
│   │   └── test_api.py       # Integration tests (Flask API + auth)
│   └── data/
│       ├── mes.db            # SQLite database (auto-created)
│       └── logs/             # Application logs
└── venv/                     # Python virtual environment
```

## Building and Running

### Prerequisites
- Python 3.10+
- Activate the virtual environment: `venv\Scripts\activate`

### Install Dependencies
```bash
pip install -r mes_production\requirements.txt
```

### Run (Production)
```bash
python mes_production\run.py
```
Server starts on `http://0.0.0.0:5000`

### Run (Development with debug mode)
```bash
python -m mes_production.web.app
```

### Stop
Press `Ctrl+C` in the terminal.

## API Reference

### Orders

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/orders` | Public | Get all orders (optional: `?status=buffer/production/completed/cancelled`) |
| POST | `/api/orders` | 🔒 Key | Create orders (body: `batch`, `product_code`, `color?`, `quantity` = count to generate) |
| POST | `/api/orders/<id>/launch` | 🔒 Key | Launch order to station 1 |
| POST | `/api/orders/<id>/move` | 🔒 Key | Move order to next station |
| POST | `/api/orders/<id>/complete` | 🔒 Key | Complete order manually |
| POST | `/api/orders/<id>/cancel` | 🔒 Key | Cancel order |

### Stations & Statistics

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/stations` | Public | Get all stations with current orders |
| GET | `/api/statistics` | Public | Get production statistics |

### Batch Creation Response
```json
{
  "success": true,
  "orders": [...],
  "count": 3,
  "message": "Created 3 order(s)"
}
```

Each order has `quantity: 1` and a unique auto-generated `order_number` like `ORD-4521-789`.

## Authentication

Write operations (POST) require a valid API key in the `X-API-Key` header.
Read operations (GET) and page routes are public.

```bash
# Create orders (authenticated)
curl -X POST http://localhost:5000/api/orders \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{"batch":"B1","product_code":"P1","color":"Red","quantity":3}'

# Get orders (public)
curl http://localhost:5000/api/orders
```

Frontend automatically includes the API key via `<meta name="api-key">` tag rendered from server config.

Configure API keys in `config.yaml`:

```yaml
auth:
  api_keys:
    - your-secret-key-here
    - another-key
```

If `api_keys` is empty or missing, auth is disabled (all requests pass through).

## Configuration

All settings are in `mes_production/config.yaml`:

```yaml
database:
  path: data/mes.db
server:
  host: 0.0.0.0
  port: 5000
stations:
  - Приёмка
  - Сортировка
  # ... (10 stations total)
auth:
  api_keys:
    - change-me-to-a-secure-key
logging:
  level: INFO
  path: data/logs
```

## Database

- **Foreign keys** enabled (`PRAGMA foreign_keys = ON`)
- **Transactions** with rollback for multi-step operations (launch, move, complete, cancel)
- **Order numbers** auto-generated: `ORD-<timestamp-last4>-<random-3digits>`

Three tables:
| Table | Purpose |
|---|---|
| **orders** | Production orders with status tracking |
| **stations** | 10 workstation slots with current order references |
| **station_log** | Audit log of order movements between stations |

## Testing

```bash
# Run all tests with coverage
cd mes_production
pytest --cov=utils --cov=core --cov=web -v

# Run specific test file
pytest tests/test_api.py -v

# Run tests matching a keyword
pytest -k "launch" -v
```

**Current coverage: 92%** (47 tests)

| File | Coverage |
|---|---|
| `core/controller.py` | 100% |
| `utils/database.py` | 90% |
| `utils/logger.py` | 100% |
| `web/app.py` | 92% |
| `web/auth.py` | 86% |

- `tests/test_database.py` — Unit tests for DB init, order generation, CRUD, stations, statistics
- `tests/test_api.py` — Integration tests for all endpoints including auth (unauthorized, wrong key, success)
- `tests/conftest.py` — Shared fixtures (`db`, `controller`, `app`, `auth_client`, `unauth_client`, `client`)

## Development Conventions

- **Architecture:** MVC-style — `Controller` for business logic, `Database` for persistence, `AuthService` for auth
- **App Factory:** Flask app via `create_app()` pattern for testability
- **UTF-8:** Russian language in station names, UI, and documentation
- **Error Handling:** 400 on invalid input, 401 on missing/invalid API key
- **Auto-completion:** Orders reaching station 10 auto-complete
- **Logger:** Handler duplication prevented (`if logger.handlers: return`)
- **Each order has quantity=1** — the "quantity" field in the create API means "count of orders to generate"
