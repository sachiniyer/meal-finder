from flask import Flask
from config import Config
from utils.logger import logger
from routes.socket_routes import socketio


def create_app():
    logger.info("Initializing Flask application")
    app = Flask(__name__)
    app.config.from_object(Config)

    socketio.init_app(app)

    logger.info("Flask application initialized successfully")
    return app


if __name__ == "__main__":
    app = create_app()
    # TODO(siyer): Make the port configurable
    logger.info("Starting Flask + Socket.IO server on 0.0.0.0:5000")
    socketio.run(app, host="0.0.0.0", port=5000)
