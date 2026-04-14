# MES Production System

## Project Overview

**MES (Manufacturing Execution System)** is a web application for managing production orders and tracking their progression through a series of workstations with sub-station support. Built with Python, Flask, and SQLite, it provides a complete production workflow management solution with a web UI and REST API, user authentication with role-based access control.

### Core Features
- **Batch order creation** — generate multiple orders at once with sequential unique numbers (`ORD-0001`, `ORD-0002`, ...)
- **User authentication** — login/password via Flask-Login with session-based auth for browsers
- **Role-based access control** — `admin`, `operator`, `viewer` roles with hierarchical permissions
- **Sub-stations support** — main stations can have child sub-stations (e.g. 1.1, 1.2, 3.1)
- **Multiple orders per station** — stations can process several orders simultaneously
- **Launch orders** into production and move them through sequential workstations
- **Auto-complete** orders when they reach the final station
- **Real-time statistics** — production dashboard with live counts
- **Order status management** — buffer, production, completed, cancelled

### Workstations (configurable)
10 main stations + configurable sub-stations:
1. Приёмка (1.1, 1.2) → 2. Сортировка → 3. Подготовка (3.1) → 4. Сборка → 5. Пайка → 6. Контроль → 7. Тестирование → 8. Упаковка → 9. Маркировка → 10. Отгрузка

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.10+ |
| Web Framework | Flask >= 3.0.0 |
| Auth | Flask-Login >= 0.6.3 + Werkzeug password hashing |
| Production Server | Waitress >= 3.0.0 |
| Database | SQLite (FK enabled, transactions with rollback, auto-migration) |
| Configuration | YAML (PyYAML >= 6.0) |
| Frontend | HTML/CSS/JavaScript (dark/light theme, SVG pipeline) |
| Testing | pytest >= 8.0, pytest-cov >= 5.0 |

## Project Structure

```
stend/
├── README.md                          # Project documentation
├── QWEN.md                            # AI assistant context
├── GIT_INSTRUCTIONS.md                # Git remote workflow guide
├── AUTH_IMPLEMENTATION.md             # Auth implementation guide
├── .gitignore
├── mes_production/
│   ├── run.py                         # Entry point (Waitress server)
│   ├── config.yaml                    # System configuration (stations with subs)
│   ├── requirements.txt               # Python dependencies
│   ├── pytest.ini                     # Pytest configuration
│   ├── core/
│   │   └── controller.py              # Business logic controller
│   ├── utils/
│   │   ├── database.py                # SQLite operations (sub-station aware, logging, no conn leaks)
│   │   └── logger.py                  # Logging setup (no handler duplication)
│   ├── web/
│   │   ├── app.py                     # Flask application factory + all routes
│   │   ├── auth.py                    # API key authentication middleware
│   │   ├── auth_user.py               # Flask-Login user auth, @require_role, dual auth
│   │   ├── models.py                  # User model (UserMixin, roles)
│   │   ├── static/
│   │   │   ├── style.css              # Main stylesheet (theme vars, dark mode)
│   │   │   ├── script.js              # Shared utilities (MESUtils, MESRefresh)
│   │   │   ├── orders.js              # Orders page logic
│   │   │   ├── station.js             # Station detail page logic
│   │   │   ├── map.js                 # SVG pipeline tracking page logic
│   │   │   └── theme.js               # Theme toggle (light/dark)
│   │   └── templates/
│   │       ├── login.html             # Login page
│   │       ├── index.html             # Main orders list
│   │       ├── tracking.html          # Station cards with modal order details
│   │       ├── station.html           # Station detail with dropdown + order table
│   │       ├── map.html               # SVG pipeline visualization
│   │       └── users.html             # User management (admin only)
│   ├── tests/
│   │   ├── conftest.py                # Shared fixtures (db, controller, logged_client, etc.)
│   │   ├── test_database.py           # Unit tests (DB + Controller)
│   │   └── test_api.py                # Integration tests (Flask API + auth + user mgmt)
│   └── data/
│       ├── mes.db                      # SQLite database (auto-created, auto-migrated)
│       ├── users.db                    # Users database (auto-created)
│       └── logs/                       # Application logs
└── venv/                               # Python virtual environment
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

## Pages

| Page | URL | Description |
|------|-----|-------------|
| Login | `/login` | Username/password login |
| Orders | `/` | Main orders list with create modal and status filter |
| Tracking | `/tracking` | Station cards (click → modal with order details) |
| Station | `/station` | Dropdown station selector → orders table for selected station |
| Pipeline | `/map` | SVG pipeline visualization with animated pipes and sub-stations |
| Users | `/users` | User management (admin only) |
| Logout | `/logout` | Log out |

## API Reference

### Orders

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/orders` | 🔒 Session or Key | Get all orders (optional: `?status=buffer/production/completed/cancelled`) |
| POST | `/api/orders` | 🔒 Session or Key | Create orders (body: `batch`, `product_code`, `color?`, `quantity` = count to generate) |
| POST | `/api/orders/<id>/launch` | 🔒 Session or Key | Launch order to first station |
| POST | `/api/orders/<id>/move` | 🔒 Session or Key | Move order to next station/sub-station |
| POST | `/api/orders/<id>/complete` | 🔒 Session or Key | Complete order manually |
| POST | `/api/orders/<id>/cancel` | 🔒 Session or Key | Cancel order |

### Stations & Statistics

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/stations` | 🔒 Session or Key | Get all stations (incl. sub-stations) with current orders |
| GET | `/api/statistics` | 🔒 Session or Key | Get production statistics |

### Users (admin only)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/users` | 🔒 Session (admin) | Create user (body: `username`, `password`, `role`) |
| POST | `/api/users/<id>` | 🔒 Session (admin) | Update user (body: `role`, `password?`, `is_active`) |
| DELETE | `/api/users/<id>` | 🔒 Session (admin) | Delete user |

### Dual Authentication

All API endpoints accept **either**:
- **Browser session** — user logged in via `/login` (cookie-based)
- **API key header** — `X-API-Key: your-secret-key` (for scripts/curl)

```bash
# Via session (browser — automatic)
curl -b cookie_jar http://localhost:5000/api/orders

# Via API key
curl -X POST http://localhost:5000/api/orders \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key" \
  -d '{"batch":"B1","product_code":"P1","color":"Red","quantity":3}'

# Public: no auth needed if API keys are empty in config
curl http://localhost:5000/api/orders
```

## User Roles

| Role | Level | Permissions |
|------|-------|-------------|
| `viewer` | 1 | Read-only — view orders, stations, statistics |
| `operator` | 2 | Viewer + create/launch/move/complete/cancel orders |
| `admin` | 3 | Operator + manage users, access `/users` page |

Default admin: `admin` / `admin` (created on first startup, should be changed).

## Configuration

All settings are in `mes_production/config.yaml`:

```yaml
database:
  path: data/mes.db
server:
  host: 0.0.0.0
  port: 5000
stations:
  - name: Приёмка
    subs:
      - Приёмка 1.1
      - Приёмка 1.2
  - name: Сортировка
  - name: Подготовка
    subs:
      - Подготовка 3.1
  - name: Сборка
  # ... (all stations)
auth:
  api_keys:
    - change-me-to-a-secure-key
logging:
  level: INFO
  path: data/logs
```

## Database

### Tables
| Table | Purpose |
|---|---|
| **orders** | Production orders (status, `current_station REAL` for sub-stations) |
| **stations** | Workstation slots (`id REAL` for sub-stations: 1.0, 1.1, 1.2, etc.) |
| **station_log** | Audit log of order movements |
| **users** (users.db) | User accounts (username, password_hash, role, is_active) |

### Features
- **Foreign keys** enabled (`PRAGMA foreign_keys = ON`)
- **Transactions** with rollback for multi-step operations
- **Auto-migration** — old `INTEGER` station IDs automatically migrated to `REAL` for sub-station support
- **Sequential order numbers** — `ORD-0001`, `ORD-0002`, ... (atomic via `lastrowid`)
- **Multiple orders per station** — no occupancy checks, orders move freely
- **Sub-station ordering** — stations sorted by decimal ID (1.0 → 1.1 → 1.2 → 2.0 → ...)

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

**55 tests, all passing.**

| File | Coverage |
|---|---|
| `core/controller.py` | 100% |
| `utils/database.py` | 91% |
| `utils/logger.py` | 100% |
| `web/app.py` | 90% |
| `web/auth.py` | 86% |

- `tests/test_database.py` — Unit tests for DB init, order generation, CRUD, stations, sub-stations, statistics
- `tests/test_api.py` — Integration tests for all endpoints, auth, user management, page routes
- `tests/conftest.py` — Shared fixtures (`db`, `controller`, `app`, `logged_client`, `auth_client`, `unauth_client`, `client`)

## Development Conventions

- **Architecture:** MVC-style — `Controller` for business logic, `Database` for persistence, `AuthService` for auth
- **App Factory:** Flask app via `create_app()` pattern for testability
- **UTF-8:** Russian language in station names, UI, and documentation
- **Error Handling:** 400 on invalid input, 401 on missing/invalid auth, 403 on insufficient role
- **Auto-completion:** Orders reaching the last station auto-complete
- **Logger:** Handler duplication prevented (`if logger.handlers: return`), all exceptions logged with `exc_info=True`
- **Connection safety:** All DB methods wrap entire body in `try/finally: conn.close()`
- **Each order has quantity=1** — the "quantity" field in the create API means "count of orders to generate"
- **Station config format:** `{name: str, subs?: str[]}` — sub-stations get decimal IDs (1.1, 1.2), main stations get integer IDs (1.0, 2.0)
- **Dark/light theme:** Toggle via `data-theme` attribute, persisted in `localStorage`
