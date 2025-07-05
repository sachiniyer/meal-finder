import os


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "flask-secret-key")
    DEBUG = os.environ.get("FLASK_DEBUG", "True").lower() == "true"

    # AWS Configuration
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "aws-access-key-id")
    AWS_SECRET_ACCESS_KEY = os.environ.get(
        "AWS_SECRET_ACCESS_KEY", "aws-secret-access-key"
    )
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

    # MongoDB Configuration
    MONGODB_USER = os.environ.get("MONGODB_USER", "assistant_user")
    MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD", "assistant_pass")
    MONGODB_HOST = os.environ.get("MONGODB_HOST", "localhost")
    MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "assistant_db")

    # OpenAI Configuration
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "open-api-key")
    OPENAI_MODEL_ID = os.environ.get("OPENAI_MODEL_ID", "gpt-3.5-turbo-0613")

    # Yelp Configuration
    YELP_API_KEY = os.environ.get("YELP_API_KEY", "yelp-api-key")

    # Google Maps Configuration
    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "google-maps-api-key")
    # TODO(siyer): These endpoint's defaults have potentially duplicate info.
    # Consider generating them from base.
    GOOGLE_MAPS_SEARCH_ENDPOINT = os.environ.get(
        "GOOGLE_MAPS_SEARCH_ENDPOINT",
        "https://places.googleapis.com/v1/places:searchText",
    )
    GOOGLE_MAPS_PLACES_ENDPOINT = os.environ.get(
        "GOOGLE_MAPS_PLACES_ENDPOINT",
        "https://places.googleapis.com/v1/places",
    )
    GOOGLE_MAPS_PHOTOS_ENDPOINT = os.environ.get(
        "GOOGLE_MAPS_PHOTOS_ENDPOINT",
        "https://places.googleapis.com/v1",
    )

    # AWS Bedrock Models
    # NOTE(dev): This is the smaller model used to describe images
    BEDROCK_MICRO_MODEL = os.environ.get(
        "BEDROCK_MICRO_MODEL", "amazon.nova-micro-v1:0"
    )
    # NOTE(dev): This is the larger model used to extract info from images
    BEDROCK_PRO_MODEL = os.environ.get("BEDROCK_PRO_MODEL", "amazon.nova-pro-v1:0")

    # Cache Files
    ASSISTANT_CACHE_FILE = os.environ.get(
        "ASSISTANT_CACHE_FILE", "assistant_cache.json"
    )

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    API_TOKEN = os.environ.get(
        "API_TOKEN", "api-token"
    )  # Required for API authentication

    EXA_API_KEY: str = os.getenv("EXA_API_KEY", "exa-api-key")
