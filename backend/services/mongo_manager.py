import uuid
from pymongo import MongoClient
from config import Config
from utils.logger import logger
import json
from pymongo import UpdateOne
from time import time
from typing import Any

# Initialize MongoDB client and get database
MONGODB_URI = f"mongodb://{Config.MONGODB_USER}:{Config.MONGODB_PASSWORD}@{Config.MONGODB_HOST}/{Config.MONGODB_DATABASE}?authSource={Config.MONGODB_DATABASE}"

logger.info("Initializing MongoDB client")
client = MongoClient(MONGODB_URI)
db = client[Config.MONGODB_DATABASE]

try:
    # The serverStatus command requires admin privileges, so we'll use a simpler command
    client.admin.command("ping")
    logger.info("Successfully connected to MongoDB")
except Exception as e:
    logger.error(
        f"Failed to connect to MongoDB: {str(e)}, {MONGODB_URI}, {Config.MONGODB_DATABASE}"
    )
    raise

# Get collections (equivalent to our previous DynamoDB tables)
chats_collection = db["chats"]
places_collection = db["places"]


def create_chat_data(location: dict):
    new_chat_id = str(uuid.uuid4())
    logger.info(f"Creating new chat with ID: {new_chat_id}")

    chat_doc = {
        "chat_id": new_chat_id,
        "messages": [],
        "places": [],
        "thread_id": None,  # NOTE(dev): This get initialized later when OpenAI requests are made
        "location": location,
        "created_at": int(time()),  # Unix timestamp in seconds
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


def create_or_get_chat_data(chat_id=None):
    """
    If chat_id is provided, try to retrieve from MongoDB. If not found, create a new item.
    If chat_id is not provided, create a new chat in MongoDB.
    """
    if chat_id:
        logger.debug(f"Attempting to retrieve existing chat: {chat_id}")
        existing = get_chat_data(chat_id)
        if existing:
            logger.info(f"Found existing chat: {chat_id}")
            return existing

    return create_chat_data()


def get_chat_data(chat_id):
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


def update_chat_data(chat_id, new_data):
    """
    Update or insert (upsert) chat data in MongoDB.
    """
    logger.debug(f"Updating chat data for ID: {chat_id}")
    logger.debug(f"New data to update: {json.dumps(new_data, indent=2)}")

    # Ensure chat_id is consistent
    new_data["chat_id"] = chat_id

    try:
        # Use update_one instead of replace_one to see if the update actually happened
        result = chats_collection.update_one(
            {"chat_id": chat_id}, {"$set": new_data}, upsert=True
        )

        logger.debug(
            f"MongoDB update result - matched: {result.matched_count}, modified: {result.modified_count}, upserted_id: {result.upserted_id}"
        )

        # Verify the update by retrieving the document
        updated_doc = chats_collection.find_one({"chat_id": chat_id}, {"_id": 0})
        logger.debug(
            f"Retrieved document after update: {json.dumps(updated_doc, indent=2)}"
        )

        if "thread_id" not in updated_doc:
            logger.error("thread_id not found in updated document!")

        return updated_doc

    except Exception as e:
        logger.error(f"Error updating chat data: {str(e)}", exc_info=True)
        raise


def update_chat_data_field(chat_id, field, value):
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


def add_chat_message(chat_id, message):
    """
    Add a message to the chat data.
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


def append_places(places: list):
    """
    Append multiple places to the places collection.
    Converts 'id' to 'place_id' and prevents overwriting existing records.
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


def add_place_fields(place_id: str, fields: dict):
    """
    Add fields to an existing place.
    """
    logger.debug(f"Adding fields to place: {place_id}")
    logger.debug(f"Fields to add: {fields}")
    try:
        result = places_collection.update_one(
            {"place_id": place_id}, {"$set": fields}, upsert=True
        )
        logger.debug(
            f"MongoDB update result - matched: {result.matched_count}, modified: {result.modified_count}, upserted_id: {result.upserted_id}"
        )

        updated_doc = places_collection.find_one({"place_id": place_id}, {"_id": 0})
        logger.debug(
            f"Retrieved document after update: {json.dumps(updated_doc, indent=2)}"
        )

        return updated_doc
    except Exception as e:
        logger.error(f"Error adding fields to place: {str(e)}", exc_info=True)
        raise


def get_place(place_id):
    """
    Retrieve a place by place_id.
    """
    return places_collection.find_one({"place_id": place_id}, {"_id": 0})


def update_place(place_id, updated_data):
    """
    Update an existing place.
    """
    updated_data["place_id"] = place_id
    places_collection.replace_one({"place_id": place_id}, updated_data, upsert=True)
    return updated_data


def update_place_field(place_id, field, value):
    logger.debug(f"Updating place data for ID: {place_id}")
    logger.debug(f"New data to update: {field} with value: {value}")
    try:
        place_data = get_place(place_id)
        place_data[field] = value
        result = places_collection.update_one(
            {"place_id": place_id}, {"$set": place_data}, upsert=True
        )
        logger.debug(
            f"MongoDB update result - matched: {result.matched_count}, modified: {result.modified_count}, upserted_id: {result.upserted_id}"
        )

        return place_data
    except Exception as e:
        logger.error(f"Error updating place data: {str(e)}", exc_info=True)
        raise


# Optional: Add some MongoDB-specific helper functions
def create_indexes():
    """
    Create indexes for better query performance.
    Call this when setting up your application.
    """
    chats_collection.create_index("chat_id", unique=True)
    places_collection.create_index("place_id", unique=True)


def get_all_chats():
    """
    Get all chats (with optional pagination).
    """
    return list(chats_collection.find({}, {"_id": 0}))


def get_all_places():
    """
    Get all places (with optional pagination).
    """
    return list(places_collection.find({}, {"_id": 0}))


def get_places_for_ids(place_ids: list):
    """
    Retrieve place documents from the 'places' collection for the given place_ids.
    """
    logger.debug(f"Retrieving documents for place_ids: {place_ids}")
    if not place_ids:
        return []
    # Using $in to fetch any matching place_ids
    cursor = places_collection.find(
        {"place_id": {"$in": place_ids}}, {"_id": 0}  # omit the Mongo _id field
    )
    return list(cursor)


def get_place_summary(place_id: str):
    """
    Retrieve the editorial summary for a place.
    """
    place_doc = places_collection.find_one(
        {"place_id": place_id},
        {"_id": 0, "place_id": 1, "editorialSummary": 1, "displayName": 1},
    )
    return place_doc
