"""
MES Production System - Logger utility
"""
import logging
import os
from datetime import datetime


def setup_logger(name: str, log_path: str, level: str = "INFO") -> logging.Logger:
    """Setup and return a logger instance."""
    os.makedirs(log_path, exist_ok=True)

    logger = logging.getLogger(name)

    # Prevent handler duplication on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # File handler
    log_file = os.path.join(log_path, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
