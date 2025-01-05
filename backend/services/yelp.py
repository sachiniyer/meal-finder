import requests
from config import Config
from services.mongo_manager import get_place, update_place_field
from utils.logger import logger


def search_for_reviews(place_id: str):
    """
    Search for reviews for a given place_id.
    """
    logger.info(f"Starting Yelp review search for place_id: {place_id}")

    headers = {
        "Authorization": f"Bearer {Config.YELP_API_KEY}",
    }
    logger.debug(f"Using Yelp API key: {Config.YELP_API_KEY[:10]}...")

    # Get place data from MongoDB
    logger.debug(f"Retrieving place data for place_id: {place_id}")
    place_data = get_place(place_id)
    if not place_data:
        logger.error(f"No place data found for place_id: {place_id}")
        return {"error": "Place not found in database"}

    latitude = place_data.get("location").get("latitude")
    longitude = place_data.get("location").get("longitude")

    name = place_data.get("displayName", {}).get("text")
    logger.info(
        f"Searching Yelp for business: '{name}' at latitude: {latitude} and longitude: {longitude}"
    )

    # Construct search URL
    url = f"https://api.yelp.com/v3/businesses/search?term={name}&sort_by=best_match&limit=1&latitude={latitude}&longitude={longitude}"
    logger.debug(f"Yelp search URL: {url}")

    business_id = None
    response = {}

    try:
        # First API call - Search for business
        logger.info("Making initial Yelp API call to search for business")
        search_response = requests.get(url, headers=headers)
        search_response.raise_for_status()
        data = search_response.json()
        logger.debug(f"Received search response: {data}")

        if data.get("businesses") and len(data.get("businesses")) > 0:
            business = data["businesses"][0]
            logger.info(
                f"Found matching business on Yelp: {business.get('name')} (ID: {business.get('id')})"
            )

            # Store the Yelp business data
            logger.debug(f"Updating place with Yelp business data")
            update_place_field(place_id, "yelpData", business)

            business_id = business.get("id")
            response["yelp_rating"] = business.get("rating")
            response["yelp_review_count"] = business.get("review_count")

            logger.info(
                f"Business has {response['yelp_review_count']} reviews with {response['yelp_rating']} average rating"
            )
        else:
            logger.warning(f"No businesses found on Yelp matching '{name}'")
            return {"error": "No businesses found in Yelp search"}

        # Second API call - Get reviews
        if business_id:
            reviews_url = f"https://api.yelp.com/v3/businesses/{business_id}/reviews"
            logger.info(f"Fetching reviews for business_id: {business_id}")
            logger.debug(f"Reviews URL: {reviews_url}")

            reviews_response = requests.get(reviews_url, headers=headers)
            reviews_response.raise_for_status()
            reviews_data = reviews_response.json()
            logger.debug(f"Received reviews response: {reviews_data}")

            if reviews_data.get("reviews") and len(reviews_data.get("reviews")) > 0:
                yelp_reviews = reviews_data["reviews"]
                logger.info(f"Retrieved {len(yelp_reviews)} reviews")

                # Store the reviews
                logger.debug("Updating place with Yelp reviews")
                update_place_field(place_id, "yelpReviews", yelp_reviews)

                # Extract review texts
                response["yelp_reviews"] = [review["text"] for review in yelp_reviews]
                logger.debug(f"Processed {len(response['yelp_reviews'])} review texts")
            else:
                logger.warning(f"No reviews found for business_id: {business_id}")
                response["yelp_reviews"] = []

        logger.info("Successfully completed Yelp review search")
        return response

    except requests.exceptions.RequestException as e:
        logger.error(f"Yelp API request failed: {str(e)}", exc_info=True)
        logger.debug(f"Failed URL: {url}")
        return {"error": f"Error in Yelp search: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in Yelp search: {str(e)}", exc_info=True)
        return {"error": str(e)}
