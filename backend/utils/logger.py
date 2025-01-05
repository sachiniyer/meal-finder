"""
Logging configuration for the application.

This module provides a centralized logging configuration that:
- Sets up console and file logging with colored output
- Configures log formats and levels
- Creates rotating file handlers to manage log files
- Provides a consistent logging interface across the application
"""

import logging
import logging.handlers
import sys
import os
from pathlib import Path
from config import Config


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds colors to log levels in console output.
    
    Colors:
        DEBUG: Blue
        INFO: Green
        WARNING: Yellow
        ERROR: Red
        CRITICAL: Red (Bold)
    """
    
    COLORS = {
        'DEBUG': '\033[94m',     # Blue
        'INFO': '\033[92m',      # Green
        'WARNING': '\033[93m',   # Yellow
        'ERROR': '\033[91m',     # Red
        'CRITICAL': '\033[1;91m' # Bold Red
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Save original levelname
        orig_levelname = record.levelname
        # Add color to levelname
        if record.levelname in self.COLORS:
            record.levelname = (f"{self.COLORS[record.levelname]}"
                              f"{record.levelname:8}"
                              f"{self.RESET}")
        # Format the message
        result = super().format(record)
        # Restore original levelname
        record.levelname = orig_levelname
        return result


class LoggerManager:
    """
    Manages application-wide logging configuration.
    
    This is a singleton class to ensure consistent logging setup across the application.
    
    Attributes:
        logger (logging.Logger): The configured logger instance
        log_dir (Path): Directory where log files are stored
        log_file (Path): Path to the main log file
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggerManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the logger manager (only runs once for singleton)"""
        if self._initialized:
            return
            
        # Create logs directory if it doesn't exist
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / "app.log"
        
        # Create logger
        self.logger = logging.getLogger("assistant_app")
        self.logger.setLevel(self._get_log_level())
        
        # Remove any existing handlers
        self.logger.handlers = []
        
        # Add handlers
        self._add_console_handler()
        self._add_file_handler()
        
        self._initialized = True
        self.logger.info("Initialized LoggerManager singleton")
    
    def _get_log_level(self) -> int:
        """
        Get the log level from config or environment.
        
        Returns:
            int: The logging level (e.g., logging.DEBUG)
        """
        level_name = Config.LOG_LEVEL.upper()
        return getattr(logging, level_name, logging.INFO)
    
    def _add_console_handler(self) -> None:
        """Add a colored console handler with timestamp and custom formatting."""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        # Format: [TIME] LEVEL - MESSAGE
        console_format = ColoredFormatter(
            fmt='%(asctime)s %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
    
    def _add_file_handler(self) -> None:
        """Add a rotating file handler with custom formatting."""
        # Create a rotating file handler (10 MB per file, keep 5 backup files)
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_file,
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        file_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)


# Create the singleton instance and expose the logger
logger_manager = LoggerManager()
logger = logger_manager.logger
