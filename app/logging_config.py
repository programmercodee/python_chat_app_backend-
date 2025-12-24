"""
Logging configuration for the messaging platform.
Logs everything to both console and app.log file.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Get the directory where this file is located
BASE_DIR = Path(__file__).parent

# Log file path
LOG_FILE = BASE_DIR / "app.log"


def setup_logging():
    """
    Configure logging to write to both console and file.
    
    Logs:
    - All HTTP requests
    - Errors and exceptions
    - Database queries (if DEBUG)
    - Socket.IO events
    - Application startup/shutdown
    """
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler (INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # File handler (DEBUG and above, rotates at 10MB)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    
    # Uvicorn access logs
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.setLevel(logging.INFO)
    
    # Uvicorn error logs
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.setLevel(logging.INFO)
    
    # SQLAlchemy logs (queries)
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.setLevel(logging.WARNING)  # Change to DEBUG to see all queries
    
    # Socket.IO logs (suppress verbose connection logs)
    socketio_logger = logging.getLogger("socketio")
    socketio_logger.setLevel(logging.WARNING)
    
    # Engine.IO logs (suppress heartbeat logs)
    engineio_logger = logging.getLogger("engineio")
    engineio_logger.setLevel(logging.WARNING)
    
    # PyMongo logs (suppress heartbeat/topology logs)
    pymongo_logger = logging.getLogger("pymongo")
    pymongo_logger.setLevel(logging.WARNING)
    
    # Motor logs (async MongoDB driver)
    motor_logger = logging.getLogger("motor")
    motor_logger.setLevel(logging.WARNING)
    
    return logging.getLogger("app")


# Create app logger
logger = setup_logging()
