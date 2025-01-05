import boto3
from botocore.config import Config as BotoConfig
from config import Config
from services.google_maps import get_images_for_place
from services.mongo_manager import get_place, update_place_field
from utils.logger import logger
import requests
import base64
import json
import concurrent.futures
from PIL import Image
from io import BytesIO

# Configure boto3 client with retry strategy
boto_config = BotoConfig(
    region_name=Config.AWS_REGION,
    retries={
        "max_attempts": 5,
        "mode": "adaptive",  # Adaptive mode automatically adjusts retry rate
        # Initial retry delay is 3 seconds, doubles each retry with jitter
        "total_max_attempts": 5,
    },
    signature_version="v4",  # Explicitly specify signature version
)

logger.info("Initializing AWS Bedrock client with retry configuration")

logger.debug(
    f"AWS Bedrock client configuration: {boto_config}, {Config.AWS_REGION}, '{Config.AWS_ACCESS_KEY_ID}'"
)

bedrock_client = boto3.client(
    "bedrock-runtime",
    config=boto_config,
    region_name=Config.AWS_REGION,
    aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
)

# verify access
sts_client = boto3.client(
    "sts",
    aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
)
sts_client.get_caller_identity()


def _encode_and_describe(img_url: str, model_id: str, prompt: str):
    """
    Helper function to:
    1) Download an image
    2) Convert it to base64
    3) Construct Bedrock messages-v1 request
    4) Invoke model with retry
    Returns the text content from the response
    """
    logger.debug(f"Downloading image")
    response = requests.get(img_url, timeout=10)
    response.raise_for_status()

    # Convert to base64
    binary_data = response.content

    binary_data = response.content
    image = Image.open(BytesIO(binary_data)).convert("RGB")
    image_buffer = BytesIO()
    image.save(image_buffer, format="JPEG")
    base64_encoded_data = base64.b64encode(image_buffer.getvalue()).decode("utf-8")

    message_list = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64_encoded_data,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }
    ]

    native_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": message_list,
    }

    logger.debug(f"Invoking model {model_id}")

    # Use the retry wrapper for the API call
    bedrock_response = bedrock_client.invoke_model(
        modelId=model_id,
        body=json.dumps(native_request),
    )
    model_response = json.loads(bedrock_response["body"].read())
    # Safely extract text from response
    content_list = model_response.get("content")
    if not content_list:
        return "No description returned."
    if len(content_list) >= 1:
        return content_list[0].get("text", "No description returned.")
    return "No description returned."


def describe_images(place_id):
    # Get images with their indices
    photo_data = get_images_for_place(place_id)
    if isinstance(photo_data, dict) and "error" in photo_data:
        return photo_data

    logger.info(f"Processing {len(photo_data)} images with Bedrock")

    model_id = Config.BEDROCK_MICRO_MODEL
    results = {}

    # Use a thread pool to process images in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Map each image data tuple to a future
        future_map = {
            executor.submit(
                _encode_and_describe,
                photo_url,
                model_id,
                "Provide describe this image succinctly.",
            ): (photo_url, idx, photo_name)
            for photo_url, idx, photo_name in photo_data
        }

        # As each future completes, store the results with indices
        for future in concurrent.futures.as_completed(future_map):
            photo_url, idx, photo_name = future_map[future]
            try:
                description = future.result()
                results[idx] = {
                    "description": description,
                    "photo_name": photo_name,
                    "url": photo_url,
                }
                logger.debug(f"Processed image {idx}: {description[:100]}...")
            except Exception as e:
                logger.error(f"Error processing image {idx}: {str(e)}", exc_info=True)
                results[idx] = {
                    "error": str(e),
                    "photo_name": photo_name,
                    "url": photo_url,
                }

    logger.debug(f"Storing Image Description results for place_id: {place_id}")
    place_data = get_place(place_id)

    if place_data and "photos" in place_data:
        photos = place_data["photos"]
        for idx, result in results.items():
            if idx < len(photos):
                photos[idx]["description"] = result.get(
                    "description", result.get("error")
                )
        update_place_field(place_id, "photos", photos)

        return [
            {
                "googleMapsUri": photo.get("googleMapsUri"),
                "description": photo.get("description"),
                "index": idx,
            }
            for idx, photo in enumerate(photos)
        ]
    return []


def extract_image_info(image_index: int, place_id: str, query: str):
    # TODO(siyer): Consider caching this result as well (but there is a query so it may not work so well)
    logger.info(f"Extracting info from image {image_index} for place_id {place_id}")
    place_data = get_place(place_id)

    if not place_data:
        logger.error(f"Place not found for place_id: {place_id}")
        return {"error": "Place not found."}
    photo_data = place_data.get("photos")
    if not photo_data:
        logger.error(f"No photo data found for place_id: {place_id}")
        return {"error": "No photo data found."}

    if image_index >= len(photo_data):
        logger.error(f"Invalid image index: {image_index}")
        return {"error": "Invalid image index."}
    photo_name = photo_data[image_index]["name"]
    photo_url = f"{Config.GOOGLE_MAPS_PHOTOS_ENDPOINT}/{photo_name}/media?maxHeightPx=400&maxWidthPx=400&key={Config.GOOGLE_MAPS_API_KEY}"
    model_id = Config.BEDROCK_PRO_MODEL
    info = _encode_and_describe(photo_url, model_id, query)
    logger.debug(f"Extracted info from image {image_index}: {info[:100]}...")
    return {"info": info}
