"""Constants file."""


class Constants:
    """Constants Class."""

    AVAILABLE_SEARCH_FIELDS = {
        # NOTE(dev): Places Basic SKU
        "accessibilityOptions",
        "addressComponents",
        "adrFormatAddress",
        "businessStatus",
        "containingPlaces",
        "displayName",
        "formattedAddress",
        "googleMapsLinks*",
        "googleMapsUri",
        "iconBackgroundColor",
        "iconMaskBaseUri",
        "location",
        "photos",
        "plusCode",
        "primaryType",
        "primaryTypeDisplayName",
        "pureServiceAreaBusiness",
        "shortFormattedAddress",
        "subDestinations",
        "types",
        "utcOffsetMinutes",
        "viewport",
        # NOTE(dev): Places Advanced SKU
        "currentOpeningHours",
        "currentSecondaryOpeningHours",
        "internationalPhoneNumber",
        "nationalPhoneNumber",
        "priceLevel",
        "priceRange",
        "rating",
        "regularOpeningHours",
        "regularSecondaryOpeningHours",
        "userRatingCount",
        "websiteUri",
        # NOTE(dev): Places Preferred SKU
        "allowsDogs",
        "curbsidePickup",
        "delivery",
        "dineIn",
        "editorialSummary",
        "evChargeOptions",
        "fuelOptions",
        "goodForChildren",
        "goodForGroups",
        "goodForWatchingSports",
        "liveMusic",
        "menuForChildren",
        "parkingOptions",
        "paymentOptions",
        "outdoorSeating",
        "reservable",
        "restroom",
        "reviews",
        "servesBeer",
        "servesBreakfast",
        "servesBrunch",
        "servesCocktails",
        "servesCoffee",
        "servesDessert",
        "servesDinner",
        "servesLunch",
        "servesVegetarianFood",
        "servesWine",
        "takeout",
    }

    DEFAULT_SEARCH_FIELDS = {
        "displayName",
        "id",
        "formattedAddress",
        "websiteUri",
        "location",
        "photos",
        "editorialSummary",
    }

    NON_DEFAULT_SEARCH_FIELDS = AVAILABLE_SEARCH_FIELDS - DEFAULT_SEARCH_FIELDS

    TOOL_DESCRIPTIONS = {
        "search_google_maps": "Searching Google Maps",
        "describe_images": "Analyzing images from Google Maps",
        "extract_image_info": "Extracting information from Google Maps images",
        "fetch_chat_data": "Recollecting information from historical chat data",
        "describe_place": "Getting more information from Google Maps",
        "get_stored_places_for_chat": "Retrieving all the places we have talked about",
        "get_yelp_reviews": "Fetching Yelp reviews",
        "get_user_location": "Getting your location",
        "search_website": "Searching website content",
    }


TOOL_CONFIG = [
    {
        "type": "function",
        "function": {
            "name": "search_google_maps",
            "description": "Search Google Maps for a query. Include any relevant terms you think are necessary to get a better result",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query, e.g. 'pizza in new york'. The user's location will be attached to the query",
                    },
                    "radius": {
                        "type": "number",
                        "description": "The search radius in meters (default: 5000). The radius must be between 0.0 and 50000.0, inclusive",
                    },
                    "limit": {
                        "type": "number",
                        "description": "The maximum number of places to return (default: 5). The limit must be between 0 and 20, inclusive",
                    },
                    "page": {
                        "type": "number",
                        "description": "The page of results to retrieve. The default is 0",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_images",
            "description": "Apply a short description to each image (use this function to determine which images have menus associated)",
            "parameters": {
                "type": "object",
                "properties": {
                    "place_id": {
                        "type": "string",
                        "description": "The place id, e.g. 'ChIJj61dQgK6j4AR4GeTYWZsKWw'.",
                    }
                },
                "required": ["place_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_image_info",
            "description": "Extract information from one of the images (use this function to tell what items a restaurant has)",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_index": {
                        "type": "number",
                        "description": "The index of an image from the list of images associated with the place",
                    },
                    "place_id": {
                        "type": "string",
                        "description": "The place id, e.g. 'ChIJj61dQgK6j4AR4GeTYWZsKWw'.",
                    },
                    "query": {
                        "type": "string",
                        "description": "A question that you have about the image that you want answered. (e.g. what are all the items on the menu)",
                    },
                },
                "required": ["image_index", "place_id", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_chat_data",
            "description": "Fetch all chat data so far (use this function sparingly and only when necessary to avoid processing a lot of data)",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_place",
            "description": (
                "Use the google maps api to describe a place with the given place_id and fields to retrieve"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "place_id": {
                        "type": "string",
                        "description": "The place id, e.g. 'ChIJj61dQgK6j4AR4GeTYWZsKWw'.",
                    },
                    "fields": {
                        "type": "array",
                        "description": "A list of fields to return from the known available fields (e.g. takeout)",
                        "items": {
                            "type": "string",
                            "enum": list(Constants.NON_DEFAULT_SEARCH_FIELDS),
                        },
                    },
                },
                "required": ["place_id", "fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stored_places_for_chat",
            "description": "Retrieve all stored places for a given chat_id, returning place_id and editorialSummary.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "get_yelp_reviews",
    #         "description": "Get Yelp reviews and ratings for a specific place. Use this after finding a place through Google Maps to get additional customer feedback.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "place_id": {
    #                     "type": "string",
    #                     "description": "The Google Maps place_id of the business to get reviews for",
    #                 }
    #             },
    #             "required": ["place_id"],
    #         },
    #     },
    # },
    {
        "type": "function",
        "function": {
            "name": "get_user_location",
            "description": "Get the location of the user chatting with you",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_website",
            "description": "Search a specific website's content for information using Exa. Use this to find menu items, business hours, or other details from a business's website.",
            "parameters": {
                "type": "object",
                "properties": {
                    # NOTE(dev): actually better to let the ai fill in the domain, because it can find it from yelp, google maps, or another source
                    "domain": {
                        "type": "string",
                        "description": "The website domain to search (e.g., 'restaurant.com')",
                    },
                    "query": {
                        "type": "string",
                        "description": "What to search for on the website (e.g., 'lunch menu', 'business hours')",
                    },
                },
                "required": ["domain", "query"],
            },
        },
    },
]
