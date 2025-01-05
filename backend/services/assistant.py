"""
This service handles the interaction with your OpenAI or AWS Bedrock assistant,
and stores the conversation in Redis.
"""

import json
import os
from openai import OpenAI
from config import Config
from services.mongo_manager import (
    get_chat_data,
    get_chat_data_field,
    update_chat_data_field,
)
from services.google_maps import (
    search_google_maps,
    describe_place,
    get_stored_places_for_chat,
)
from services.image_processor import (
    describe_images,
    extract_image_info,
)
from services.yelp import search_for_reviews
from utils.logger import logger
from utils.constants import Constants, TOOL_CONFIG
from services.exa import search_domain

logger.info("Initializing OpenAI client")
client = OpenAI(api_key=Config.OPENAI_API_KEY)


def get_or_create_assistant():
    """
    Retrieve assistant ID from cache file or create a new assistant
    """
    if os.path.exists(Config.ASSISTANT_CACHE_FILE):
        try:
            with open(Config.ASSISTANT_CACHE_FILE, "r") as f:
                cache = json.load(f)
                assistant_id = cache.get("assistant_id")
                if assistant_id:
                    logger.info(f"Loading cached assistant ID: {assistant_id}")
                    try:
                        assistant = client.beta.assistants.retrieve(assistant_id)
                        logger.info("Successfully retrieved existing assistant")
                        return assistant
                    except Exception as e:
                        logger.warning(f"Cached assistant not found: {e}")
        except Exception as e:
            logger.error(f"Error reading cache file: {e}")

    logger.info("Creating new OpenAI assistant with tools")
    assistant = client.beta.assistants.create(
        instructions="You are a helpful assistant with specialized tools. Use these functions to handle user requests.",
        model=Config.OPENAI_MODEL_ID,
        tools=TOOL_CONFIG,
    )

    try:
        with open(Config.ASSISTANT_CACHE_FILE, "w") as f:
            json.dump({"assistant_id": assistant.id}, f)
        logger.info(f"Cached new assistant ID: {assistant.id}")
    except Exception as e:
        logger.error(f"Error caching assistant ID: {e}")

    return assistant


assistant = get_or_create_assistant()
logger.debug(f"Using assistant with ID: {assistant.id}")


def chat_with_assistant(user_message: str, chat_id: str, emit_tool_call) -> str:
    """
    Use the OpenAI assistants API to handle conversation:
    1. Get or create a thread
    2. Add the user's message to the thread
    3. Create a run with our assistant
    4. Wait for the run to complete
    5. Return the assistant's response
    """
    logger.info(f"Processing chat message for chat_id: {chat_id}")

    thread_id = get_chat_data_field(chat_id, "thread_id")
    if not thread_id:
        logger.debug(f"Creating new thread for chat_id: {chat_id}")
        thread = client.beta.threads.create()
        thread_id = thread.id
        logger.debug(f"Updating chat data with thread_id: {thread_id}")
        update_chat_data_field(chat_id, "thread_id", thread_id)

        logger.info(f"Created new thread with ID: {thread_id}")

    try:
        logger.debug("Adding user message to thread")
        client.beta.threads.messages.create(
            thread_id=thread_id, role="user", content=user_message
        )

        logger.info("Creating run with assistant")
        run = client.beta.threads.runs.create(
            thread_id=thread_id, assistant_id=assistant.id
        )

        logger.debug("Waiting for run to complete")
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id, run_id=run.id
            )
            if run_status.status == "completed":
                break
            elif run_status.status == "requires_action":
                tool_calls = run_status.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    logger.debug(f"Handling function call: {function_name}")
                    emit_tool_call(
                        {"function": function_name, "arguments": arguments}, chat_id
                    )

                    output = handle_assistant_function_call(
                        function_name, arguments, chat_id
                    )

                    tool_outputs.append(
                        {"tool_call_id": tool_call.id, "output": json.dumps(output)}
                    )

                client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id, run_id=run.id, tool_outputs=tool_outputs
                )
            elif run_status.status in ["failed", "expired", "cancelled"]:
                logger.error(f"Run failed with status: {run_status.status}")
                return f"Error: Run {run_status.status}"

        messages = client.beta.threads.messages.list(thread_id=thread_id)
        assistant_message = next(msg for msg in messages if msg.role == "assistant")
        response = assistant_message.content[0].text.value

        logger.debug(f"Received response: {response[:100]}...")
        return response

    except Exception as e:
        logger.error(f"Error in chat_with_assistant: {str(e)}", exc_info=True)
        return f"Error: {str(e)}"


def handle_assistant_function_call(function_name: str, arguments: dict, chat_id: str):
    """
    Handle function calls from the assistant.
    """
    logger.info(f"Handling function call: {function_name}")
    logger.debug(f"Function arguments: {arguments}")

    try:
        if function_name == "search_google_maps":
            query_val = arguments.get("query", "")
            radius_val = arguments.get("radius", 5000)
            limit_val = arguments.get("limit", 5)
            logger.debug(
                f"Executing Google Maps search with query: {query_val}, radius: {radius_val}, limit: {limit_val}"
            )
            return search_google_maps(query_val, radius_val, limit_val, chat_id)

        elif function_name == "describe_place":
            place_id = arguments.get("place_id", "")
            fields_val = arguments.get("fields", [])
            if not all(
                field in Constants.AVAILABLE_SEARCH_FIELDS for field in fields_val
            ):
                invalid_fields = [
                    field
                    for field in fields_val
                    if field not in Constants.AVAILABLE_SEARCH_FIELDS
                ]
                return {"error": f"Invalid fields: {invalid_fields}"}
            logger.debug(
                f"Describing place with ID: {place_id} and fields: {fields_val}"
            )
            return describe_place(place_id, fields_val)

        elif function_name == "describe_images":
            place_id = arguments.get("place_id", [])
            logger.debug(f"Describing images for place_id {place_id}")
            return describe_images(place_id)

        elif function_name == "extract_image_info":
            query = arguments.get("query", "")
            place_id = arguments.get("place_id", "")
            image_index = arguments.get("image_index", 0)
            logger.debug(
                f"Extracting info from: {query} for place_id: {place_id}, image_index: {image_index}"
            )
            return extract_image_info(image_index, place_id, query)

        elif function_name == "fetch_chat_data":
            logger.debug(f"Fetching chat data for: {chat_id}")
            return get_chat_data(chat_id) or {}

        elif function_name == "get_stored_places_for_chat":
            logger.debug("Retrieving stored places for a chat")
            return get_stored_places_for_chat(chat_id)

        elif function_name == "get_yelp_reviews":
            place_id = arguments.get("place_id")
            logger.debug(f"Getting Yelp reviews for place_id: {place_id}")
            return search_for_reviews(place_id)

        elif function_name == "get_user_location":
            logger.debug(f"Getting User Location for chat_id: {chat_id}")

            return get_chat_data_field(chat_id, "location")

        elif function_name == "search_website":
            domain = arguments.get("domain", "")
            query = arguments.get("query", "")
            logger.debug(f"Searching website {domain} for: {query}")
            return search_domain(domain, query)

        logger.error(f"Unknown function: {function_name}")
        return {"error": f"Function '{function_name}' not recognized."}

    except Exception as e:
        logger.error(
            f"Error executing function {function_name}: {str(e)}", exc_info=True
        )
        return {"error": f"Error executing function: {str(e)}"}
