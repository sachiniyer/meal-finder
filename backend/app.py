"""
Flask application entry point.

This module:
- Initializes the Flask application
- Sets up Socket.IO integration
- Configures application settings
- Starts the development server
"""

from flask import Flask
from config import Config
from utils.logger import logger
from routes.socket_routes import socketio
import os


def create_app() -> Flask:
    """
    Create and configure the Flask application.
    
    Returns:
        Flask: The configured Flask application instance
    """
    logger.info("Initializing Flask application")
    app = Flask(__name__)
    app.config.from_object(Config)

    socketio.init_app(app)

    logger.info("Flask application initialized successfully")
    return app


if __name__ == "__main__":
    try:
        app = create_app()
        port = int(os.environ.get("FLASK_PORT", 8000))
        
        logger.info(f"Starting Flask + Socket.IO server on 0.0.0.0:{port}")
        socketio.run(app, host="0.0.0.0", port=port)
        
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}", exc_info=True)
        raise
