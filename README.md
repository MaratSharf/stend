# MES Production System

A Manufacturing Execution System (MES) for tracking and managing production orders through multiple workstations.

## Overview

This system provides a web-based interface for managing production orders as they move through various stations in a manufacturing process. It includes order creation, tracking, station management, and production statistics.

## Features

- **Order Management**: Create, launch, track, complete, and cancel production orders
- **Station Tracking**: Monitor orders as they progress through 10 production stations:
  1. Приёмка (Reception)
  2. Сортировка (Sorting)
  3. Подготовка (Preparation)
  4. Сборка (Assembly)
  5. Пайка (Soldering)
  6. Контроль (Inspection)
  7. Тестирование (Testing)
  8. Упаковка (Packaging)
  9. Маркировка (Labeling)
  10. Отгрузка (Shipping)
- **Real-time Statistics**: View production metrics and performance data
- **RESTful API**: Full API for integration with other systems
- **Responsive Web Interface**: Modern, user-friendly UI

## Project Structure

```
mes_production/
├── config.yaml          # Configuration file
├── requirements.txt     # Python dependencies
├── run.py              # Main entry point
├── core/
│   ├── __init__.py
│   └── controller.py   # Business logic controller
├── utils/
│   ├── __init__.py
│   ├── database.py     # SQLite database operations
│   └── logger.py       # Logging configuration
└── web/
    ├── __init__.py
    ├── app.py          # Flask application
    ├── static/
    │   ├── style.css   # Stylesheets
    │   ├── script.js   # Main JavaScript
    │   ├── orders.js   # Order management JS
    │   └── theme.js    # Theme configuration
    └── templates/
        ├── index.html  # Orders list page
        └── tracking.html # Station tracking page
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. Clone or navigate to the project directory:
   ```bash
   cd mes_production
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure the system (optional):
   Edit `config.yaml` to customize:
   - Database path
   - Server host and port
   - Station names
   - Logging settings

## Usage

### Starting the Server

Run the application using the provided entry point:

```bash
python run.py
```

The server will start on `http://0.0.0.0:5000` by default.

### Web Interface

Access the web interface in your browser:

- **Orders Page**: `http://localhost:5000/` - Create and manage orders
- **Tracking Page**: `http://localhost:5000/tracking` - View station status and order flow

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/orders` | Get all orders (optional `?status=` filter) |
| POST | `/api/orders` | Create a new order |
| POST | `/api/orders/<id>/launch` | Launch order to production |
| POST | `/api/orders/<id>/move` | Move order to next station |
| POST | `/api/orders/<id>/complete` | Complete an order |
| POST | `/api/orders/<id>/cancel` | Cancel an order |
| GET | `/api/stations` | Get all stations status |
| GET | `/api/statistics` | Get production statistics |

### Example API Usage

Create an order:
```bash
curl -X POST http://localhost:5000/api/orders \
  -H "Content-Type: application/json" \
  -d '{"batch": "B001", "product_code": "PROD-123", "color": "Red", "quantity": 10}'
```

Get all orders:
```bash
curl http://localhost:5000/api/orders
```

## Configuration

Edit `config.yaml` to customize settings:

```yaml
database:
  path: data/mes.db          # SQLite database location
server:
  host: 0.0.0.0              # Server bind address
  port: 5000                 # Server port
stations:                    # List of production stations
  - Приёмка
  - Сортировка
  # ... (add more as needed)
logging:
  level: INFO                # Log level (DEBUG, INFO, WARNING, ERROR)
  path: data/logs            # Log files directory
```

## Technology Stack

- **Backend**: Python, Flask, Waitress (WSGI server)
- **Database**: SQLite
- **Frontend**: HTML5, CSS3, JavaScript
- **Configuration**: YAML

## License

This project is provided as-is for manufacturing execution and production tracking purposes.

