"""
MongoDB service for managing chat and place data.

This module provides functionality to:
- Initialize and manage MongoDB connections
- Handle CRUD operations for chat data
- Handle CRUD operations for place data
- Cache place information from external APIs

NOTE(dev): This module assumes MongoDB is running and accessible.
"""

import uuid
from pymongo import UpdateOne
from typing import Optional, Dict, Any, List
from utils.logger import logger
from utils.clients import api_client_manager
import json
from time import time


# TODO(siyer): Avoid global variables, and just put this logic into each function
chats_collection = api_client_manager.mongodb_db["chats"]
places_collection = api_client_manager.mongodb_db["places"]


def create_chat_data(location: dict):
    """
    Create a new chat document in MongoDB.

    Args:
        location (dict): Location data to associate with chat

    Returns:
        dict: The created chat document

    NOTE(dev): Thread ID is initialized as None and set later when OpenAI requests are made
    """
    new_chat_id = str(uuid.uuid4())
    logger.info(f"Creating new chat with ID: {new_chat_id}")

    chat_doc = {
        "chat_id": new_chat_id,
        "messages": [],
        "places": [],
        "thread_id": None,
        "location": location,
        "created_at": int(time()),
    }

    try:
        result = chats_collection.insert_one(chat_doc)
        logger.debug(f"Insert result: {result.inserted_id}")

        # Verify the insertion
        created_doc = chats_collection.find_one({"chat_id": new_chat_id}, {"_id": 0})
        logger.debug(f"Created document: {json.dumps(created_doc, indent=2)}")

        return created_doc
    except Exception as e:
        logger.error(f"Error creating new chat: {str(e)}", exc_info=True)
        raise


def get_chat_data(chat_id: str):
    """
    Retrieve the chat document from MongoDB by chat_id.

    Returns None if not found.
    """
    logger.debug(f"Retrieving chat data for ID: {chat_id}")
    try:
        result = chats_collection.find_one({"chat_id": chat_id}, {"_id": 0})
        if result:
            logger.info(f"Found chat data for ID: {chat_id}")
        else:
            logger.warning(f"No chat data found for ID: {chat_id}")
        return result
    except Exception as e:
        logger.error(f"Error retrieving chat data: {str(e)}", exc_info=True)
        raise


def update_chat_data_field(chat_id: str, field: str, value: Any) -> Any:
    """
    Update a singular field of the chat object with a given value.

    Args:
        chat_id (str): The chat ID to query
        field (str): The field name to retrieve
        default (Any): Value to set the field to

    Returns:
       chat_data (Any): The chat data

    """
    logger.debug(f"Updating chat data for ID: {chat_id}")
    logger.debug(f"New data to update: {field} with value: {value}")
    try:
        chat_data = get_chat_data(chat_id)
        chat_data[field] = value
        result = chats_collection.update_one(
            {"chat_id": chat_id}, {"$set": chat_data}, upsert=True
        )
        logger.debug(
            f"MongoDB update result - matched: {result.matched_count}, modified: {result.modified_count}, upserted_id: {result.upserted_id}"
        )

        return chat_data
    except Exception as e:
        logger.error(f"Error updating chat data: {str(e)}", exc_info=True)
        raise


def get_chat_data_field(chat_id: str, field: str, default: Any = None) -> Any:
    """
    Get a specific field from a chat document.

    Args:
        chat_id (str): The chat ID to query
        field (str): The field name to retrieve
        default (Any, optional): Default value if field doesn't exist. Defaults to None.

    Returns:
        Any: The field value or default if not found
    """
    logger.debug(f"Getting field '{field}' from chat {chat_id}")
    chat_data = get_chat_data(chat_id)
    if not chat_data:
        logger.warning(f"No chat data found for {chat_id}")
        return default
    return chat_data.get(field, default)


def add_chat_message(chat_id: str, message: str) -> Any:
    """
    Add a message to the chat data.

    Args:
        chat_id (str): The chat ID to update
        message (str): The message to add
    Returns:
        chat_data (Any): The updated chat data
    """
    logger.debug(f"Adding message to chat data for ID: {chat_id}")
    logger.debug(f"Message to add: {message}")
    try:
        chat_data = get_chat_data(chat_id)
        chat_data["messages"].append(message)
        result = chats_collection.update_one(
            {"chat_id": chat_id}, {"$set": chat_data}, upsert=True
        )
        logger.debug(
            f"MongoDB update result - matched: {result.matched_count}, modified: {result.modified_count}, upserted_id: {result.upserted_id}"
        )

        return chat_data
    except Exception as e:
        logger.error(f"Error adding message to chat data: {str(e)}", exc_info=True)
        raise


def append_places(places: List[Dict[str, Any]]) -> None:
    """
    Append multiple places to the places collection.

    Uses bulk operations for efficiency and prevents duplicate entries.

    Args:
        places (List[Dict[str, Any]]): List of place documents to store

    NOTE(dev): Converts 'id' to 'place_id' for consistency in the database
    """
    logger.debug(f"Appending {len(places)} places to the collection")
    try:
        operations = []
        for place in places:
            # Convert id to place_id
            place["place_id"] = place.get("id")

            operations.append(
                UpdateOne(
                    filter={"place_id": place["place_id"]},
                    update={"$setOnInsert": place},
                    upsert=True,
                )
            )

        # Execute bulk write operation
        if operations:
            result = places_collection.bulk_write(operations, ordered=False)
            logger.debug(
                f"MongoDB bulk write result - "
                f"Inserted: {result.upserted_count}, "
                f"Modified: {result.modified_count}, "
                f"Matched: {result.matched_count}"
            )
    except Exception as e:
        logger.error(f"Error appending places: {str(e)}", exc_info=True)
        raise


def get_place(place_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a place document by its ID.

    Args:
        place_id (str): The place ID to retrieve

    Returns:
        Optional[Dict[str, Any]]: The place document or None if not found
    """
    try:
        return places_collection.find_one({"place_id": place_id}, {"_id": 0})
    except Exception as e:
        logger.error(f"Error retrieving place: {str(e)}", exc_info=True)
        raise


def update_place_field(place_id: str, field: str, value: Any) -> Dict[str, Any]:
    """
    Update a specific field in a place document.

    Args:
        place_id (str): The place ID to update
        field (str): The field name to update
        value (Any): The new value to set

    Returns:
        Dict[str, Any]: The updated place document
    """
    logger.debug(f"Updating place data for ID: {place_id}")
    logger.debug(f"New data to update: {field} with value: {value}")
    try:
        place_data = get_place(place_id)
        if not place_data:
            place_data = {"place_id": place_id}
        place_data[field] = value
        result = places_collection.update_one(
            {"place_id": place_id}, {"$set": place_data}, upsert=True
        )
        logger.debug(
            f"MongoDB update result - matched: {result.matched_count}, "
            f"modified: {result.modified_count}, "
            f"upserted_id: {result.upserted_id}"
        )

        return place_data
    except Exception as e:
        logger.error(f"Error updating place data: {str(e)}", exc_info=True)
        raise


def get_all_chats() -> List[Dict[str, Any]]:
    """
    Get all chat documents, sorted by creation time.

    Returns:
        List[Dict[str, Any]]: List of all chat documents

    NOTE(dev): Excludes MongoDB _id field from results
    """
    try:
        return list(chats_collection.find({}, {"_id": 0}).sort("created_at", -1))
    except Exception as e:
        logger.error(f"Error retrieving all chats: {str(e)}", exc_info=True)
        raise


def get_place_summary(place_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a minimal summary of a place, typically for display in lists.

    Args:
        place_id (str): The place ID to query

    Returns:
        Optional[Dict[str, Any]]: Dictionary containing:
            - place_id (str): Place identifier
            - editorialSummary (dict, optional): Place description
            - displayName (dict): Place name information
    """
    try:
        return places_collection.find_one(
            {"place_id": place_id},
            {"_id": 0, "place_id": 1, "editorialSummary": 1, "displayName": 1},
        )
    except Exception as e:
        logger.error(f"Error retrieving place summary: {str(e)}", exc_info=True)
        raise
