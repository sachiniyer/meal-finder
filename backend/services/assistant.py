"""
OpenAI Assistant service for managing AI conversations.

This module provides functionality to:
- Initialize and manage OpenAI assistant instances
- Handle conversation threads and messages
- Integrate with external tools (Google Maps, Yelp, etc.)
- Cache assistant data for persistence

NOTE(dev): This service relies heavily on external APIs and MongoDB for storage.
TODO(dev): Add retry logic for OpenAI API calls to handle rate limits.
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
from utils.clients import api_client_manager


class AssistantManager:
    """
    Manages OpenAI assistant initialization and caching.

    This is a singleton class to ensure only one assistant instance exists.

    Attributes:
        assistant_id (str): The cached or newly created assistant ID
        openai_client (OpenAI): The OpenAI client instance
    """

    _instance = None

    def __new__(cls):
        """Create a new instance of the AssistantManager singleton."""
        if cls._instance is None:
            cls._instance = super(AssistantManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the assistant manager (only runs once for singleton)."""
        if self._initialized:
            return

        self.openai_client = api_client_manager.openai
        self.assistant = self._get_or_create_assistant()
        self._initialized = True
        logger.info("Initialized AssistantManager singleton")

    def _get_or_create_assistant(self):
        """
        Retrieve assistant ID from cache file or create a new assistant.

        This method:
        1. Checks for cached assistant ID
        2. Tries to retrieve existing assistant
        3. Creates new assistant if needed
        4. Caches the assistant ID

        Returns:
            Assistant: The OpenAI assistant instance

        NOTE(dev): Cache file helps persist assistant ID across restarts
        """
        if os.path.exists(Config.ASSISTANT_CACHE_FILE):
            try:
                with open(Config.ASSISTANT_CACHE_FILE, "r") as f:
                    cache = json.load(f)
                    assistant_id = cache.get("assistant_id")
                    if assistant_id:
                        logger.info(f"Loading cached assistant ID: {assistant_id}")
                        try:
                            assistant = self.openai_client.beta.assistants.retrieve(
                                assistant_id
                            )
                            logger.info("Successfully retrieved existing assistant")
                            return assistant
                        except Exception as e:
                            logger.warning(f"Cached assistant not found: {e}")
            except Exception as e:
                logger.error(f"Error reading cache file: {e}")

        logger.info("Creating new OpenAI assistant with tools")
        assistant = self.openai_client.beta.assistants.create(
            instructions="You are a meal finding assistant. Your goal is to take all the information you have to help the user find meals."
            "Avoid naming google, yelp, exa and other service by name. Additionally, please provide links as citations\n"
            "Avoid saying that there were issues with the service. Instead say there was no information available\n"  # NOTE(dev): Usually it responds no information as there was an issue
            "Unless requested, provide an opinionated choice on a single restaurant instead of listing restaurants that you found\n"
            "When displaying google maps images, just provide a link instead of displaying it inline\n"
            "Here are some common requests:\n"
            "1. To find restaurants use search_google_maps\n"
            "2. To get menus do the search_website tool and describe the images to see if there are any menu images\n"
            "3. To look at ratings, use the describe_place tool with ratings (for google ratings) and use the yelp api\n"
            "4. Use the extract_image_info tool to more information about an image after using the describe_images tool\n"
            "5. Use the fetch_chat_data tool if you need a reminder of what happened in the conversation earlier",
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

    def chat_with_assistant(self, user_input: str, chat_id: str, tool_callback) -> str:
        """
        Process user input and generate assistant response.

        This method:
        1. Retrieves or creates chat thread
        2. Adds user message to thread
        3. Runs assistant to process message
        4. Handles any tool calls
        5. Returns final response

        Args:
            user_input (str): The user's message
            chat_id (str): Unique identifier for the chat session
            tool_callback: Function to notify client of tool usage

        Returns:
            str: The assistant's response message

        NOTE(dev): Tool calls are handled asynchronously through callbacks
        """
        logger.info(f"Processing chat message for chat_id: {chat_id}")

        thread_id = get_chat_data_field(chat_id, "thread_id")
        if not thread_id:
            logger.debug(f"Creating new thread for chat_id: {chat_id}")
            thread = self.openai_client.beta.threads.create()
            thread_id = thread.id
            logger.debug(f"Updating chat data with thread_id: {thread_id}")
            update_chat_data_field(chat_id, "thread_id", thread_id)

            logger.info(f"Created new thread with ID: {thread_id}")

        try:
            logger.debug("Adding user message to thread")
            self.openai_client.beta.threads.messages.create(
                thread_id=thread_id, role="user", content=user_input
            )

            logger.info("Creating run with assistant")
            run = self.openai_client.beta.threads.runs.create(
                thread_id=thread_id, assistant_id=self.assistant.id
            )

            logger.debug("Waiting for run to complete")
            while True:
                run_status = self.openai_client.beta.threads.runs.retrieve(
                    thread_id=thread_id, run_id=run.id
                )
                if run_status.status == "completed":
                    break
                elif run_status.status == "requires_action":
                    tool_calls = (
                        run_status.required_action.submit_tool_outputs.tool_calls
                    )
                    tool_outputs = []

                    for tool_call in tool_calls:
                        function_name = tool_call.function.name
                        arguments = json.loads(tool_call.function.arguments)
                        logger.debug(f"Handling function call: {function_name}")
                        tool_callback(
                            {"function": function_name, "arguments": arguments}, chat_id
                        )

                        output = self.handle_assistant_function_call(
                            function_name, arguments, chat_id
                        )

                        tool_outputs.append(
                            {"tool_call_id": tool_call.id, "output": json.dumps(output)}
                        )

                    self.openai_client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id, run_id=run.id, tool_outputs=tool_outputs
                    )
                elif run_status.status in ["failed", "expired", "cancelled"]:
                    logger.error(f"Run failed with status: {run_status.status}")
                    return f"Error: OpenAI assistant entered failed state (state {run_status.status}), start a new chat"

            messages = self.openai_client.beta.threads.messages.list(
                thread_id=thread_id
            )
            assistant_message = next(msg for msg in messages if msg.role == "assistant")
            response = assistant_message.content[0].text.value

            logger.debug(f"Received response: {response[:100]}...")
            return response

        except Exception as e:
            logger.error(f"Error in chat_with_assistant: {str(e)}", exc_info=True)
            return f"Error: {str(e)}"

    def handle_assistant_function_call(
        self, function_name: str, arguments: dict, chat_id: str
    ) -> dict:
        """
        Execute tool functions requested by the assistant.

        This method:
        1. Maps function names to actual implementations
        2. Validates and processes arguments
        3. Returns tool execution results

        Args:
            function_name (str): Name of the tool to execute
            arguments (dict): Arguments for the tool
            chat_id (str): The chat ID for context

        Returns:
            dict: Results from the tool execution

        NOTE(dev): New tools must be added to both TOOL_CONFIG and this handler
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


# Create the singleton instance
assistant_manager = AssistantManager()


# Create function aliases that use the singleton
# This preserves the existing API while using the new class internally
def chat_with_assistant(user_input, chat_id, tool_callback):
    """Chat with the assistant using the singleton instance."""
    return assistant_manager.chat_with_assistant(user_input, chat_id, tool_callback)


def handle_assistant_function_call(function_name, arguments, chat_id):
    """Handle assistant function calls using the singleton instance."""
    return assistant_manager.handle_assistant_function_call(
        function_name, arguments, chat_id
    )
