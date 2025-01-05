from flask_socketio import SocketIO, emit, disconnect
from flask import request
from utils.logger import logger
from utils.constants import Constants
from services.mongo_manager import (
    get_chat_data,
    get_all_chats,
    create_chat_data,
    add_chat_message,
)
from services.assistant import chat_with_assistant
from config import Config

# Initialize SocketIO with CORS and manage session
socketio = SocketIO(cors_allowed_origins="*", manage_session=False)

# Store active chat sessions: { sid: chat_id, ... }
active_sessions = {}
# Reverse lookup for chat sessions: { chat_id: set(sids), ... }
chat_sessions = {}

def validate_token(token):
    """Validate the API token"""
    return token == Config.API_TOKEN

@socketio.on("connect")
def handle_connect():
    """Validate token on connection"""
    token = request.args.get('token')
    if not token or not validate_token(token):
        logger.warning(f"Invalid token attempt from {request.sid}")
        disconnect()
        return False
        
    logger.info(f"Client connected with valid token: {request.sid}")
    active_sessions[request.sid] = None
    return True


@socketio.on("disconnect")
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")
    if request.sid in active_sessions:
        chat_id = active_sessions[request.sid]
        if chat_id and chat_id in chat_sessions:
            chat_sessions[chat_id].remove(request.sid)
            if not chat_sessions[chat_id]:  # If no more sessions for this chat
                del chat_sessions[chat_id]
        del active_sessions[request.sid]


@socketio.on("send_message")
def handle_send_message(data):
    """
    Handle incoming chat messages and process them through the assistant.

    Expected data format:
    {
      "chat_id": "uuid" (optional),
      "content": "User's message",
      "location": { "latitude": ..., "longitude": ... } (optional)
    }
    If chat_id isn't provided, we'll create a new chat (like search.py),
    storing the user's location if present.
    """
    logger.info(f"Received 'send_message' event: {data}")
    try:
        chat_id = data.get("chat_id")
        content = data.get("content")
        location = data.get("location")  # optional location data

        if not content:
            raise ValueError("Message content is required")

        # If the client didn't provide a chat_id, create a new chat
        if not chat_id:
            # create_chat_data optionally takes a location
            chat_doc = create_chat_data(location or {})
            chat_id = chat_doc["chat_id"]
            logger.info(f"Created new chat with ID: {chat_id}")

        # Store chat_id in active_sessions + chat_sessions
        active_sessions[request.sid] = chat_id
        if chat_id not in chat_sessions:
            chat_sessions[chat_id] = set()
        chat_sessions[chat_id].add(request.sid)

        # Add the user message to the database just like in search.py
        add_chat_message(chat_id, {"role": "user", "content": content})
        # Process message through assistant, storing its replies in DB
        response = chat_with_assistant(content, chat_id, emit_tool_call)
        add_chat_message(chat_id, {"role": "assistant", "content": response})

        # Send the assistant's response back to all clients in this chat
        emit_assistant_message(response, chat_id)

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        emit_error(str(e))


@socketio.on("get_chats")
def handle_get_chats():
    """
    Retrieve all available chats from the database.
    (Extra functionality that search.py didn't have by default)
    """
    logger.info("Received 'get_chats' event")
    try:
        chats = get_all_chats()
        emit("chats", {"chats": chats}, room=request.sid)
    except Exception as e:
        logger.error(f"Error retrieving chats: {str(e)}")
        emit_error(str(e))


@socketio.on("get_messages")
def handle_get_messages(data):
    """
    Retrieve message history for a specific chat.
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


###
# New event that retrieves the entire chat doc (like search.py's "GET /api/search")
###
@socketio.on("get_chat_data")
def handle_get_chat_data(data):
    """
    Retrieve the full chat document for a specific chat.
    search.py used to return the entire chat_data in GET /api/search.
    This event replicates that behavior over Socket.IO.

    Expects: { "chat_id": "UUID" }
    Emits: "chat_data" with { "chat_data": {...} }
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


def emit_assistant_message(content: str, chat_id: str):
    """
    Emit an assistant's response to the client.
    """
    logger.info(f"Emitting assistant message: {content[:100]}...")
    if chat_id in chat_sessions:
        for sid in chat_sessions[chat_id]:
            emit("message", {"chat_id": chat_id, "content": content}, room=sid)


def emit_tool_call(data: dict, chat_id: str):
    """
    Emit a tool call event when the assistant uses a tool.
    """
    logger.info(f"Emitting tool call: {data}")
    tool_message = Constants.TOOL_DESCRIPTIONS[data["function"]]
    if chat_id in chat_sessions:
        for sid in chat_sessions[chat_id]:
            emit("tool_call", {"chat_id": chat_id, "tool_data": tool_message}, room=sid)


def emit_error(error_message: str):
    """
    Emit an error message to the client.
    """
    logger.error(f"Emitting error: {error_message}")
    emit(
        "error",
        {"chat_id": active_sessions.get(request.sid), "error": error_message},
        room=request.sid,
    )
