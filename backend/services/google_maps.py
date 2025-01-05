"""
This service interacts with the Google Maps Places API v1 to perform text search queries.

"""

import requests
from config import Config
from utils.logger import logger
from services.mongo_manager import (
    get_place,
    append_places,
    get_chat_data_field,
    update_chat_data_field,
    get_chat_data,
    get_place_summary,
)

from utils.constants import Constants


def search_google_maps(query: str, radius: int, limit: int, chat_id: str):
    """
    Perform a text search using the Google Maps Places API v1.

    Args:
        query (str): The search query (e.g., "pizza near me")
        location (dict, optional): Dictionary containing latitude and longitude

    Returns:
        list: List of places matching the search criteria
    """

    location = get_chat_data_field(chat_id, "location")

    logger.info(
        f"Executing Google Maps search for query: {query}, location: {location}"
    )

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": Config.GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": ",".join(
            [f"places.{field}" for field in Constants.DEFAULT_SEARCH_FIELDS]
        ),
    }

    # Prepare request body
    body = {
        "textQuery": query,
        "pageSize": limit,
    }

    # Add location bias if provided
    if location and "latitude" in location and "longitude" in location:
        logger.debug(f"Adding location bias: {location}")
        body["locationBias"] = {
            "circle": {
                "center": {
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                },
                "radius": radius,  # 5km radius
            }
        }

    try:
        logger.debug(
            f"Making request to endpoint: {Config.GOOGLE_MAPS_SEARCH_ENDPOINT}"
        )

        logger.debug(f"Request body: {body}")
        logger.debug(f"Request headers: {headers}")
        response = requests.post(
            Config.GOOGLE_MAPS_SEARCH_ENDPOINT, headers=headers, json=body
        )
        response.raise_for_status()
        data = response.json()

        places = data.get("places", [])
        logger.info(f"Found {len(places)} results for query: {query}")

        if places:
            logger.debug(f"First result: {places[0]}")

        # Transform the response to match your application's expected format
        append_places(places)
        old_places = get_chat_data_field(chat_id, "places")
        old_places.extend([place.get("id") for place in places])
        update_chat_data_field(chat_id, "places", old_places)

        return [{k: v for k, v in place.items() if k != "photos"} for place in places]

    except requests.exceptions.RequestException as e:
        logger.error(f"Error in Google Maps search: {str(e)}", exc_info=True)
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in Google Maps search: {str(e)}", exc_info=True)
        return {"error": f"Unexpected error: {str(e)}"}


def describe_place(place_id: str, fields: list):
    """
    Similar to search_google_maps, but allows specifying a custom subset of fields
    from AVAILABLE_SEARCH_FIELDS via 'fields' argument.
    """
    logger.info(f"Describing place with place_id: {place_id}, fields: {fields}")

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": Config.GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": ",".join(fields),
    }

    try:
        logger.debug(
            f"Making request to endpoint: {Config.GOOGLE_MAPS_SEARCH_ENDPOINT}"
        )

        response = requests.get(
            f"{Config.GOOGLE_MAPS_PLACES_ENDPOINT}/{place_id}", headers=headers
        )

        response.raise_for_status()
        data = response.json()

        logger.info(f"Received response data: {data}")

        # check if data is {}
        if not data:
            return {"error": f"No data in google for {place_id}, and fields {fields}"}

        return data

    except requests.exceptions.RequestException as e:
        logger.error(f"Error in Google Maps describe place: {str(e)}", exc_info=True)
        return {"error": str(e)}
    except Exception as e:
        logger.error(
            f"Unexpected error in Google Maps describe place: {str(e)}", exc_info=True
        )
        return {"error": f"Unexpected error: {str(e)}"}


def get_stored_places_for_chat(chat_id: str):
    """
    Retrieves all stored places (from the MongoDB 'places' collection) for the given chat_id.
    Returns a list with each place's place_id and editorialSummary.
    """
    logger.info(f"Retrieving stored places for chat_id: {chat_id}")

    # 1. Fetch the chat document to see what place_ids are stored
    chat_data = get_chat_data(chat_id)
    if not chat_data:
        logger.error(f"No chat data found for chat_id: {chat_id}")
        return {"error": f"No chat data for {chat_id}"}

    place_ids = chat_data.get("places", [])
    if not place_ids:
        logger.warning(f"No places found in chat_data for chat_id: {chat_id}")
        return []

    logger.debug(f"Found {len(place_ids)} place_ids in chat_data: {place_ids}")

    # 2. For each place_id, retrieve minimal fields from the places collection
    results = []
    for pid in place_ids:
        # The place doc might contain editorialSummary or other fields
        place_doc = get_place_summary(pid)
        if place_doc:
            results.append(place_doc)
        else:
            logger.warning(f"No document found in 'places' for place_id {pid}")

    logger.info(f"Returning {len(results)} place documents for chat_id: {chat_id}")
    return results


def get_images_for_place(place_id: str):
    """
    Retrieves image URLs and their indices for the given place_id.
    Returns a list of tuples containing (photo_url, photo_index, photo_name).
    Skips photos that already have descriptions.
    """
    logger.info(f"Retrieving images for place_id: {place_id}")
    place_data = get_place(place_id)
    if not place_data:
        logger.error(f"No place data found for place_id: {place_id}")
        return {"error": f"No place data found for {place_id}"}
    photos = place_data.get("photos", [])

    # Create list of tuples with (url, index, name), skip photos with descriptions
    photo_data = []
    for idx, photo in enumerate(photos):
        # Skip if photo already has a description
        if photo.get("description"):
            logger.debug(f"Skipping photo {idx} as it already has a description")
            continue
            
        photo_name = photo.get("name")
        if photo_name:
            photo_url = f"{Config.GOOGLE_MAPS_PHOTOS_ENDPOINT}/{photo_name}/media?maxHeightPx=400&maxWidthPx=400&key={Config.GOOGLE_MAPS_API_KEY}"
            photo_data.append((photo_url, idx, photo_name))

    logger.info(f"Found {len(photo_data)} photos without descriptions for place_id: {place_id}")
    return photo_data
