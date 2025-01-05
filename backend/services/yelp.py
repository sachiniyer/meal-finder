"""
Yelp API service for retrieving business reviews and ratings.

This module provides functionality to:
- Search for businesses using location data
- Retrieve reviews and ratings
- Cache results in MongoDB for future use
"""

import requests
from typing import Dict, Any, Optional
from utils.logger import logger
from utils.clients import api_client_manager
from services.mongo_manager import get_place, update_place_field


def search_for_reviews(place_id: str) -> Dict[str, Any]:
    """
    Search for Yelp reviews for a given place.
    
    This function:
    1. Retrieves place data from MongoDB
    2. Searches Yelp for matching business using location
    3. Fetches reviews if business is found
    4. Caches results in MongoDB
    
    Args:
        place_id (str): Google Maps place ID to search reviews for
        
    Returns:
        Dict[str, Any]: A dictionary containing:
            - yelp_rating (float, optional): Business rating
            - yelp_review_count (int, optional): Total review count
            - yelp_reviews (list, optional): List of review texts
            - error (str, optional): Error message if search failed
    """
    logger.info(f"Starting Yelp review search for place_id: {place_id}")

    # Get place data from MongoDB
    logger.debug(f"Retrieving place data for place_id: {place_id}")
    place_data = get_place(place_id)
    if not place_data:
        error_msg = f"No place data found for place_id: {place_id}"
        logger.error(error_msg)
        return {"error": error_msg}

    try:
        # Extract location and name
        location = place_data.get("location")
        if not location:
            raise ValueError("Place has no location data")
            
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        if not latitude or not longitude:
            raise ValueError("Invalid location coordinates")

        name = place_data.get("displayName", {}).get("text")
        if not name:
            raise ValueError("Place has no display name")

        logger.info(
            f"Searching Yelp for business: '{name}' at ({latitude}, {longitude})"
        )

        # Search for business
        search_url = "https://api.yelp.com/v3/businesses/search"
        search_params = {
            "term": name,
            "sort_by": "best_match",
            "limit": 1,
            "latitude": latitude,
            "longitude": longitude
        }
        
        search_response = requests.get(
            search_url, 
            headers=api_client_manager.yelp_headers,
            params=search_params
        )
        search_response.raise_for_status()
        search_data = search_response.json()

        # Process search results
        if not search_data.get("businesses"):
            logger.warning(f"No businesses found on Yelp matching '{name}'")
            return {"error": "No businesses found in Yelp search"}

        # Get first matching business
        business = search_data["businesses"][0]
        logger.info(
            f"Found matching business on Yelp: {business.get('name')} (ID: {business.get('id')})"
        )

        # Store the Yelp business data
        update_place_field(place_id, "yelpData", business)

        # Initialize response with rating data
        response = {
            "yelp_rating": business.get("rating"),
            "yelp_review_count": business.get("review_count")
        }

        # Fetch reviews if we have a business ID
        if business_id := business.get("id"):
            reviews_url = f"https://api.yelp.com/v3/businesses/{business_id}/reviews"
            logger.info(f"Fetching reviews for business_id: {business_id}")

            reviews_response = requests.get(
                reviews_url, 
                headers=api_client_manager.yelp_headers
            )
            reviews_response.raise_for_status()
            reviews_data = reviews_response.json()

            if reviews := reviews_data.get("reviews", []):
                logger.info(f"Retrieved {len(reviews)} reviews")
                
                # Store reviews in MongoDB
                update_place_field(place_id, "yelpReviews", reviews)
                
                # Add review texts to response
                response["yelp_reviews"] = [review["text"] for review in reviews]
            else:
                logger.warning(f"No reviews found for business_id: {business_id}")
                response["yelp_reviews"] = []

        return response

    except ValueError as ve:
        error_msg = f"Invalid place data: {str(ve)}"
        logger.error(error_msg)
        return {"error": error_msg}
    except requests.exceptions.RequestException as e:
        error_msg = f"Yelp API request failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error in Yelp search: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"error": error_msg}
