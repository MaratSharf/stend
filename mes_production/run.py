#!/usr/bin/env python3
"""
MES Production System - Entry Point
Run with: python run.py
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from waitress import serve
from web.app import create_app, load_config


def main():
    """Main entry point."""
    # Load configuration
    config = load_config()
    
    # Create Flask app
    app = create_app(config)
    
    # Get server settings
    host = config.get('server', {}).get('host', '0.0.0.0')
    port = config.get('server', {}).get('port', 5000)
    
    print(f"🏭 MES Production System starting...")
    print(f"   Server: http://{host}:{port}")
    print(f"   Database: {config.get('database', {}).get('path', 'data/mes.db')}")
    print(f"   Press Ctrl+C to stop")
    print()
    
    # Run with Waitress production server
    serve(app, host=host, port=port, threads=4)


if __name__ == '__main__':
    main()
