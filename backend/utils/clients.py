"""
Client session management for Socket.IO connections and API clients.

This module provides singleton managers to handle:
- Socket.IO sessions and chat rooms
- API client instances (Exa, Yelp, AWS, MongoDB, etc.)
"""

from flask_socketio import SocketIO
from exa_py import Exa
import boto3
from botocore.config import Config as BotoConfig
from pymongo import MongoClient
from utils.logger import logger
from typing import Optional, Set, Dict
from config import Config
from openai import OpenAI


class APIClientManager:
    """
    Manages API client instances.

    This is a singleton class to ensure only one instance of each client exists.

    Attributes:
        exa (Exa): The Exa API client instance
        yelp_headers (dict): Headers for Yelp API requests
        bedrock_client: AWS Bedrock client for AI image processing
        mongodb (MongoClient): MongoDB client instance
        mongodb_db: MongoDB database instance
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(APIClientManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize API clients (only runs once for singleton)"""
        if self._initialized:
            return

        # Initialize Exa client
        self.exa = Exa(api_key=Config.EXA_API_KEY)

        # Initialize Yelp headers
        self.yelp_headers = {
            "Authorization": f"Bearer {Config.YELP_API_KEY}",
        }

        # Initialize Google Maps headers
        self.google_maps_headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": Config.GOOGLE_MAPS_API_KEY,
        }

        # Initialize MongoDB client
        mongodb_uri = (
            f"mongodb://{Config.MONGODB_USER}:{Config.MONGODB_PASSWORD}"
            f"@{Config.MONGODB_HOST}:27017/{Config.MONGODB_DATABASE}"
            f"?authSource={Config.MONGODB_DATABASE}"
        )

        try:
            self.mongodb = MongoClient(mongodb_uri)
            self.mongodb_db = self.mongodb[Config.MONGODB_DATABASE]

            # Verify connection
            self.mongodb.admin.command("ping")
            logger.info("Successfully connected to MongoDB")

        except Exception as e:
            logger.error(
                f"Failed to connect to MongoDB: {str(e)}, {mongodb_uri}, "
                f"{Config.MONGODB_DATABASE}"
            )
            raise

        # Initialize AWS Bedrock client
        boto_config = BotoConfig(
            region_name=Config.AWS_REGION,
            retries={
                "max_attempts": 5,
                "mode": "adaptive",
                "total_max_attempts": 5,
            },
            signature_version="v4",
        )

        logger.debug(
            f"AWS Bedrock client configuration: {boto_config}, {Config.AWS_REGION}"
        )

        self.bedrock_client = boto3.client(
            "bedrock-runtime",
            config=boto_config,
            region_name=Config.AWS_REGION,
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
        )

        # Verify AWS access
        sts_client = boto3.client(
            "sts",
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
        )
        sts_client.get_caller_identity()

        # Initialize OpenAI client
        logger.info("Initializing OpenAI client")
        self.openai = OpenAI(api_key=Config.OPENAI_API_KEY)

        self._initialized = True
        logger.info("Initialized APIClientManager singleton")


class SessionManager:
    """
    Manages Socket.IO client sessions and chat room memberships.

    This is a singleton class to ensure only one instance manages all sessions.

    Attributes:
        socketio (SocketIO): The Flask-SocketIO instance
        active_sessions (dict): Maps session IDs to chat IDs
        chat_sessions (dict): Maps chat IDs to sets of session IDs
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
            # Initialize the singleton instance
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the session manager (only runs once for singleton)"""
        if self._initialized:
            return

        # TODO(dev): Consider making CORS origins configurable via environment variables
        self.socketio = SocketIO(cors_allowed_origins="*", manage_session=False)
        self.active_sessions: Dict[str, Optional[str]] = {}  # sid -> chat_id
        self.chat_sessions: Dict[str, Set[str]] = {}  # chat_id -> set(sids)
        self._initialized = True

        logger.info("Initialized SessionManager singleton")

    def add_session(self, sid: str) -> None:
        """
        Add a new client session.

        Args:
            sid (str): The session ID to add
        """
        self.active_sessions[sid] = None
        logger.debug(f"Added new session: {sid}")

    def remove_session(self, sid: str) -> None:
        """
        Remove a client session and clean up its chat memberships.

        Args:
            sid (str): The session ID to remove
        """
        if sid in self.active_sessions:
            chat_id = self.active_sessions[sid]
            if chat_id and chat_id in self.chat_sessions:
                self.chat_sessions[chat_id].remove(sid)
                if not self.chat_sessions[chat_id]:
                    del self.chat_sessions[chat_id]
                    logger.debug(f"Removed empty chat room: {chat_id}")
            del self.active_sessions[sid]
            logger.debug(f"Removed session: {sid}")

    def join_chat(self, sid: str, chat_id: str) -> None:
        """
        Add a client to a chat room.

        Args:
            sid (str): The session ID to add
            chat_id (str): The chat room to join
        """
        self.active_sessions[sid] = chat_id
        if chat_id not in self.chat_sessions:
            self.chat_sessions[chat_id] = set()
        self.chat_sessions[chat_id].add(sid)
        logger.debug(f"Session {sid} joined chat: {chat_id}")

    def get_chat_members(self, chat_id: str) -> Set[str]:
        """
        Get all session IDs in a chat room.

        Args:
            chat_id (str): The chat room to query

        Returns:
            Set[str]: Set of session IDs in the chat room
        """
        return self.chat_sessions.get(chat_id, set())

    def get_session_chat(self, sid: str) -> Optional[str]:
        """
        Get the chat ID for a session.

        Args:
            sid (str): The session ID to query

        Returns:
            Optional[str]: The chat ID or None if not in a chat
        """
        return self.active_sessions.get(sid)


# Create the singleton instances
session_manager = SessionManager()
api_client_manager = APIClientManager()
