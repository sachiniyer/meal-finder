"""
Socket.IO routes for handling real-time chat functionality.

This module provides WebSocket endpoints for:
- Managing chat connections and sessions
- Handling messages between clients and the AI assistant
- Managing chat history and data retrieval

The module uses Flask-SocketIO for WebSocket functionality and maintains session
state for active connections.
"""

from flask_socketio import emit, disconnect
from flask import request
from utils.logger import logger
from utils.constants import Constants
from utils.clients import session_manager
from services.mongo_manager import (
    get_chat_data,
    get_all_chats,
    create_chat_data,
    add_chat_message,
)
from services.assistant import chat_with_assistant
from config import Config

# Get the socketio instance from the session manager
socketio = session_manager.socketio

def validate_token(token: str) -> bool:
    """
    Validate the API token provided by the client.

    Args:
        token (str): The token to validate

    Returns:
        bool: True if token is valid, False otherwise
    """
    return token == Config.API_TOKEN


@socketio.on("connect")
def handle_connect() -> bool:
    """
    Handle new client connections and validate their tokens.
    
    This handler:
    1. Extracts the token from request args
    2. Validates the token
    3. Initializes session state for valid connections
    4. Disconnects invalid connections

    Returns:
        bool: True if connection is accepted, False if rejected
    """
    token = request.args.get('token')
    if not token or not validate_token(token):
        logger.warning(f"Invalid token attempt from {request.sid}")
        disconnect()
        return False
        
    logger.info(f"Client connected with valid token: {request.sid}")
    session_manager.add_session(request.sid)
    return True


@socketio.on("disconnect")
def handle_disconnect() -> None:
    """
    Clean up session state when a client disconnects.
    
    This handler:
    1. Removes the client's session ID from active_sessions
    2. Removes the client from any chat rooms they were in
    3. Cleans up empty chat sessions
    """
    logger.info(f"Client disconnected: {request.sid}")
    session_manager.remove_session(request.sid)


@socketio.on("send_message")
def handle_send_message(data: dict) -> None:
    """
    Handle incoming chat messages and process them through the assistant.

    This handler:
    1. Creates a new chat if needed
    2. Adds the message to the chat history
    3. Processes the message through the AI assistant
    4. Broadcasts the response to all clients in the chat

    Args:
        data (dict): Message data containing:
            - chat_id (str, optional): UUID of existing chat
            - content (str): User's message
            - location (dict, optional): User's location {latitude: float, longitude: float}

    Raises:
        ValueError: If message content is missing
    """
    logger.info(f"Received 'send_message' event: {data}")
    try:
        chat_id = data.get("chat_id")
        content = data.get("content")
        location = data.get("location")

        if not content:
            raise ValueError("Message content is required")

        if not chat_id:
            chat_doc = create_chat_data(location or {})
            chat_id = chat_doc["chat_id"]
            logger.info(f"Created new chat with ID: {chat_id}")

        session_manager.join_chat(request.sid, chat_id)

        add_chat_message(chat_id, {"role": "user", "content": content})
        response = chat_with_assistant(content, chat_id, emit_tool_call)
        add_chat_message(chat_id, {"role": "assistant", "content": response})

        emit_assistant_message(response, chat_id)

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        emit_error(str(e))


@socketio.on("get_chats")
def handle_get_chats() -> None:
    """
    Retrieve all available chats from the database.
    
    This handler:
    1. Fetches all chats from the database
    2. Emits them to the requesting client only
    """
    logger.info("Received 'get_chats' event")
    try:
        chats = get_all_chats()
        emit("chats", {"chats": chats}, room=request.sid)
    except Exception as e:
        logger.error(f"Error retrieving chats: {str(e)}")
        emit_error(str(e))


@socketio.on("get_messages")
def handle_get_messages(data: dict) -> None:
    """
    Retrieve message history for a specific chat.

    Args:
        data (dict): Request data containing:
            - chat_id (str): UUID of chat to fetch messages for

    Raises:
        ValueError: If chat_id is missing or chat not found
    """
    logger.info(f"Received 'get_messages' event: {data}")
    try:
        chat_id = data.get("chat_id")
        if not chat_id:
            raise ValueError("chat_id is required")

        chat_data = get_chat_data(chat_id)
        logger.info(f"Retrieved chat data: {chat_data}")
        if not chat_data:
            raise ValueError(f"Chat not found: {chat_id}")

        messages = chat_data.get("messages", [])
        logger.info(f"Sending {len(messages)} messages")

        emit("messages", {"chat_id": chat_id, "messages": messages}, room=request.sid)

    except Exception as e:
        logger.error(f"Error retrieving messages: {str(e)}")
        emit_error(str(e))


@socketio.on("get_chat_data")
def handle_get_chat_data(data: dict) -> None:
    """
    Retrieve the full chat document for a specific chat.
    
    This handler replicates the behavior of the REST endpoint "GET /api/search"
    but over Socket.IO.

    Args:
        data (dict): Request data containing:
            - chat_id (str): UUID of chat to fetch data for

    Raises:
        ValueError: If chat_id is missing or chat not found
    """
    logger.info(f"Received 'get_chat_data' event: {data}")
    try:
        chat_id = data.get("chat_id")
        if not chat_id:
            raise ValueError("chat_id is required")

        chat_data = get_chat_data(chat_id)
        if not chat_data:
            raise ValueError(f"Chat not found: {chat_id}")

        emit(
            "chat_data", {"chat_id": chat_id, "chat_data": chat_data}, room=request.sid
        )

    except Exception as e:
        logger.error(f"Error retrieving full chat data: {str(e)}")
        emit_error(str(e))


def emit_assistant_message(content: str, chat_id: str) -> None:
    """
    Emit an assistant's response to all clients in a chat room.

    Args:
        content (str): The message content to emit
        chat_id (str): The chat room to emit to
    """
    logger.info(f"Emitting assistant message: {content[:100]}...")
    for sid in session_manager.get_chat_members(chat_id):
        emit("message", {"chat_id": chat_id, "content": content}, room=sid)


def emit_tool_call(data: dict, chat_id: str) -> None:
    """
    Emit a tool call event when the assistant uses a tool.

    Args:
        data (dict): Tool call data containing:
            - function (str): Name of the tool being called
            - arguments (dict): Arguments passed to the tool
        chat_id (str): The chat room to emit to
    """
    logger.info(f"Emitting tool call: {data}")
    tool_message = Constants.TOOL_DESCRIPTIONS[data["function"]]
    for sid in session_manager.get_chat_members(chat_id):
        emit("tool_call", {"chat_id": chat_id, "tool_data": tool_message}, room=sid)


def emit_error(error_message: str) -> None:
    """
    Emit an error message to the client that caused the error.

    Args:
        error_message (str): The error message to emit
    """
    logger.error(f"Emitting error: {error_message}")
    chat_id = session_manager.get_session_chat(request.sid)
    emit(
        "error",
        {"chat_id": chat_id, "error": error_message},
        room=request.sid,
    )
