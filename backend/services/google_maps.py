"""
Google Maps Places API service for location-based search and place details.

This module provides functionality to:
- Search for places using text queries and location
- Retrieve detailed place information
- Manage place photos and data
- Cache results in MongoDB
"""

import time
import requests
from typing import Dict, Any, List, Optional, Union, Tuple
from utils.logger import logger
from utils.clients import api_client_manager
from services.mongo_manager import (
    get_place,
    append_places,
    get_chat_data_field,
    update_chat_data_field,
    get_chat_data,
    get_place_summary,
)
from utils.constants import Constants
from config import Config


import time
import requests
from typing import List, Dict, Any


def search_google_maps(
    query: str, radius: int = 5000, limit: int = 5, page: int = 0, chat_id: str = None
) -> List[Dict[str, Any]]:
    """
    Perform a text search using the Google Maps Places API v1.

    This function:
    1. Gets user location from chat data if available
    2. Executes the search with location bias
    3. Iterates pages if requested
    4. Stores results in MongoDB
    5. Associates places with the chat

    Args:
        query (str): The search query (e.g., "pizza near me")
        radius (int, optional): Search radius in meters. Defaults to 5000.
        limit (int, optional): Maximum number of results (1–20 per page). Defaults to 5.
        page (int, optional): Which page of results to fetch (0-based). Defaults to 0.
        chat_id (str, optional): Chat ID for location bias and place association.

    Returns:
        List[Dict[str, Any]]: List of places matching the search criteria.
    """
    location = get_chat_data_field(chat_id, "location") if chat_id else None
    logger.info(
        f"Executing Google Maps search for query: {query}, location: {location}, page: {page}"
    )

    headers = {
        **api_client_manager.google_maps_headers,
        "X-Goog-FieldMask": ",".join(
            [f"places.{field}" for field in Constants.DEFAULT_SEARCH_FIELDS]
            + ["nextPageToken"]
        ),
    }

    body = {
        "textQuery": query,
        "pageSize": min(max(1, limit), 20),  # Ensure limit is between 1 and 20
    }

    if location and "latitude" in location and "longitude" in location:
        logger.debug(f"Adding location bias: {location}")
        body["locationBias"] = {
            "circle": {
                "center": {
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                },
                "radius": min(max(0, radius), 50000),
            }
        }

    data = None

    try:
        for current_page in range(page + 1):
            response = requests.post(
                Config.GOOGLE_MAPS_SEARCH_ENDPOINT, headers=headers, json=body
            )
            response.raise_for_status()
            data = response.json()

            places = data.get("places", [])
            logger.info(f"Page {current_page}: Found {len(places)} results")

            if current_page == page:
                break

            next_token = data.get("nextPageToken")
            if not next_token:
                logger.warning(
                    f"No nextPageToken found at page {current_page}; returning results"
                )
                break

            # Prepare body for next page request - keep original parameters
            body["pageToken"] = next_token

            time.sleep(2)

        if places:
            append_places(places)

            if chat_id:
                old_places = get_chat_data_field(chat_id, "places", [])
                new_places = [place.get("id") for place in places]
                update_chat_data_field(chat_id, "places", old_places + new_places)

        # Remove photo data from response to reduce payload size
        return [{k: v for k, v in place.items() if k != "photos"} for place in places]

    except requests.exceptions.RequestException as e:
        error_msg = f"Error in Google Maps search: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error in Google Maps search: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"error": error_msg}


def describe_place(place_id: str, fields: List[str]) -> Dict[str, Any]:
    """
    Get detailed information about a specific place.

    This function:
    1. Validates requested fields
    2. Fetches place details from Google Maps API
    3. Updates MongoDB cache with new data

    Args:
        place_id (str): The Google Maps place ID
        fields (list): List of fields to retrieve from AVAILABLE_SEARCH_FIELDS

    Returns:
        Dict[str, Any]: Place details for the requested fields
    """
    logger.info(f"Describing place with place_id: {place_id}, fields: {fields}")

    # Validate fields
    invalid_fields = [f for f in fields if f not in Constants.AVAILABLE_SEARCH_FIELDS]
    if invalid_fields:
        error_msg = f"Invalid fields requested: {invalid_fields}"
        logger.error(error_msg)
        return {"error": error_msg}

    # Prepare headers
    headers = {
        **api_client_manager.google_maps_headers,
        "X-Goog-FieldMask": ",".join(fields),
    }

    try:
        logger.debug(f"Making request to: {Config.GOOGLE_MAPS_PLACES_ENDPOINT}")
        response = requests.get(
            f"{Config.GOOGLE_MAPS_PLACES_ENDPOINT}/{place_id}", headers=headers
        )
        response.raise_for_status()
        data = response.json()

        if not data:
            error_msg = f"No data returned for {place_id}"
            logger.warning(error_msg)
            return {"error": error_msg}

        logger.info(f"Successfully retrieved place details")
        return data

    except requests.exceptions.RequestException as e:
        error_msg = f"Error in Google Maps describe place: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error in Google Maps describe place: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"error": error_msg}


def get_stored_places_for_chat(chat_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all stored places for a chat from MongoDB.

    This function:
    1. Gets the chat document to find associated place IDs
    2. Retrieves minimal place data for each ID
    3. Returns a summary of each place

    Args:
        chat_id (str): The chat ID to get places for

    Returns:
        List[Dict[str, Any]]: List of place summaries with place_id and editorialSummary
    """
    logger.info(f"Retrieving stored places for chat_id: {chat_id}")

    chat_data = get_chat_data(chat_id)
    if not chat_data:
        logger.error(f"No chat data found for chat_id: {chat_id}")
        return {"error": f"No chat data for {chat_id}"}

    place_ids = chat_data.get("places", [])
    if not place_ids:
        logger.warning(f"No places found in chat_data for chat_id: {chat_id}")
        return []

    logger.debug(f"Found {len(place_ids)} place_ids in chat_data")

    # Get summaries for each place
    results = []
    for pid in place_ids:
        if place_doc := get_place_summary(pid):
            results.append(place_doc)
        else:
            logger.warning(f"No document found for place_id {pid}")

    logger.info(f"Returning {len(results)} place summaries")
    return results


def get_images_for_place(
    place_id: str,
) -> Union[List[Tuple[str, int, str]], Dict[str, str]]:
    """
    Get image URLs and metadata for a place.

    This function:
    1. Retrieves place data from MongoDB
    2. Generates image URLs for each photo
    3. Returns only photos without descriptions

    Args:
        place_id (str): The Google Maps place ID

    Returns:
        Union[List[Tuple[str, int, str]], Dict[str, str]]:
            List of tuples (photo_url, index, photo_name) or error dict
    """
    logger.info(f"Retrieving images for place_id: {place_id}")

    place_data = get_place(place_id)
    if not place_data:
        error_msg = f"No place data found for place_id: {place_id}"
        logger.error(error_msg)
        return {"error": error_msg}

    photos = place_data.get("photos", [])

    # Create list of tuples with (url, index, name), skip photos with descriptions
    photo_data = []
    for idx, photo in enumerate(photos):
        if photo.get("description"):
            logger.debug(f"Skipping photo {idx} - already has description")
            continue

        if photo_name := photo.get("name"):
            photo_url = (
                f"{Config.GOOGLE_MAPS_PHOTOS_ENDPOINT}/{photo_name}/media"
                f"?maxHeightPx=400&maxWidthPx=400&key={Config.GOOGLE_MAPS_API_KEY}"
            )
            photo_data.append((photo_url, idx, photo_name))

    logger.info(f"Found {len(photo_data)} photos without descriptions")
    return photo_data
