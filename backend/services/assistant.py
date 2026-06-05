"""
OpenAI service for managing AI conversations (Responses API).

This module provides functionality to:
- Drive multi-turn conversations using the OpenAI Responses API
- Chain turns via `previous_response_id` (stored per-chat in MongoDB)
- Integrate with external tools (Google Maps, Yelp, etc.)

NOTE(dev): Migrated from the legacy Assistants API (assistants/threads/runs) to
the Responses API so that newer models (e.g. gpt-5.x) can be used. Conversation
state is now a `response_id` stored per chat instead of a `thread_id`.
"""

import json
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


# System instructions for the meal-finding assistant. Passed on every turn
# (Responses API does not persist instructions across `previous_response_id`).
INSTRUCTIONS = (
    "You are a meal finding assistant. Your goal is to take all the information you have to help the user find meals."
    "Avoid naming google, yelp, exa and other service by name. Additionally, please provide links as citations\n"
    "Avoid saying that there were issues with the service. Instead say there was no information available\n"
    "Unless requested, provide an opinionated choice on a single restaurant instead of listing restaurants that you found\n"
    "When displaying google maps images, just provide a link instead of displaying it inline\n"
    "Here are some common requests:\n"
    "1. To find restaurants use search_google_maps\n"
    "2. To get menus do the search_website tool and describe the images to see if there are any menu images\n"
    "3. To look at ratings, use the describe_place tool with ratings (for google ratings)"
    "4. Use the extract_image_info tool to more information about an image after using the describe_images tool\n"
    "5. Use the fetch_chat_data tool if you need a reminder of what happened in the conversation earlier"
)

# Maximum number of tool-call round trips before giving up, to avoid loops.
MAX_TOOL_ITERATIONS = 25


def _to_responses_tools(assistant_tools):
    """
    Convert tool definitions from the Assistants API schema to the Responses API
    schema.

    Assistants: {"type": "function", "function": {"name", "description", "parameters"}}
    Responses:  {"type": "function", "name", "description", "parameters"}

    Keeping TOOL_CONFIG in the original shape (utils/constants.py) means new tools
    only have to be defined once.
    """
    converted = []
    for tool in assistant_tools:
        if tool.get("type") == "function" and "function" in tool:
            fn = tool["function"]
            converted.append(
                {
                    "type": "function",
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "parameters": fn.get(
                        "parameters", {"type": "object", "properties": {}}
                    ),
                }
            )
        else:
            # Already in Responses format (or a built-in tool) - pass through.
            converted.append(tool)
    return converted


class AssistantManager:
    """
    Manages OpenAI conversation state via the Responses API.

    This is a singleton class. Unlike the previous Assistants-API implementation,
    no remote assistant object is created at startup; tools are converted once and
    each turn is a stateless `responses.create` call chained by `previous_response_id`.

    Attributes:
        openai_client (OpenAI): The OpenAI client instance
        tools (list): Tool definitions in Responses API schema
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
        self.tools = _to_responses_tools(TOOL_CONFIG)
        self._initialized = True
        logger.info("Initialized AssistantManager singleton (Responses API)")

    def chat_with_assistant(self, user_input: str, chat_id: str, tool_callback) -> str:
        """
        Process user input and generate assistant response.

        This method:
        1. Looks up the previous response id for the chat (conversation state)
        2. Sends the user message via the Responses API
        3. Executes any requested tool calls and feeds the outputs back
        4. Persists the latest response id and returns the final text

        Args:
            user_input (str): The user's message
            chat_id (str): Unique identifier for the chat session
            tool_callback: Function to notify client of tool usage

        Returns:
            str: The assistant's response message
        """
        logger.info(f"Processing chat message for chat_id: {chat_id}")

        previous_response_id = get_chat_data_field(chat_id, "response_id")

        try:
            logger.info("Creating response")
            response = self.openai_client.responses.create(
                model=Config.OPENAI_MODEL_ID,
                instructions=INSTRUCTIONS,
                input=[{"role": "user", "content": user_input}],
                tools=self.tools,
                previous_response_id=previous_response_id,
            )

            iterations = 0
            while True:
                function_calls = [
                    item
                    for item in response.output
                    if getattr(item, "type", None) == "function_call"
                ]
                if not function_calls:
                    break

                iterations += 1
                if iterations > MAX_TOOL_ITERATIONS:
                    logger.error(
                        f"Exceeded max tool iterations ({MAX_TOOL_ITERATIONS}) for chat_id: {chat_id}"
                    )
                    break

                tool_inputs = []
                for fc in function_calls:
                    function_name = fc.name
                    arguments = json.loads(fc.arguments) if fc.arguments else {}
                    logger.debug(f"Handling function call: {function_name}")
                    tool_callback(
                        {"function": function_name, "arguments": arguments}, chat_id
                    )

                    output = self.handle_assistant_function_call(
                        function_name, arguments, chat_id
                    )

                    tool_inputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": fc.call_id,
                            "output": json.dumps(output),
                        }
                    )

                response = self.openai_client.responses.create(
                    model=Config.OPENAI_MODEL_ID,
                    instructions=INSTRUCTIONS,
                    input=tool_inputs,
                    tools=self.tools,
                    previous_response_id=response.id,
                )

            if getattr(response, "status", None) not in ("completed", None):
                detail = ""
                incomplete = getattr(response, "incomplete_details", None)
                if incomplete:
                    detail = f" ({getattr(incomplete, 'reason', incomplete)})"
                logger.error(
                    f"Response did not complete (status {response.status}){detail}"
                )
                return (
                    f"Error: OpenAI response did not complete (status {response.status})"
                    f"{detail}, start a new chat"
                )

            update_chat_data_field(chat_id, "response_id", response.id)

            response_text = response.output_text
            logger.debug(f"Received response: {response_text[:100]}...")
            return response_text

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
                page_val = arguments.get("page", 0)
                logger.debug(
                    f"Executing Google Maps search with query: {query_val}, radius: {radius_val}, limit: {limit_val}, page: {page_val}"
                )
                return search_google_maps(
                    query_val, radius_val, limit_val, page_val, chat_id
                )

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
