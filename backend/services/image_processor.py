"""
AWS Bedrock service for processing and analyzing images.

This module provides functionality to:
- Download and encode images for AI processing
- Generate image descriptions using AWS Bedrock
- Extract specific information from images
- Cache results in MongoDB
"""

import requests
import base64
import json
import concurrent.futures
from PIL import Image
from io import BytesIO
from typing import Dict, Any, List, Tuple, Optional
from utils.logger import logger
from utils.clients import api_client_manager
from services.google_maps import get_images_for_place
from services.mongo_manager import get_place, update_place_field
from config import Config


def _encode_and_describe(img_url: str, model_id: str, prompt: str) -> str:
    """
    Process an image through AWS Bedrock.

    This function:
    1. Downloads the image from the URL
    2. Converts it to base64 encoding
    3. Sends it to AWS Bedrock for processing
    4. Returns the model's response

    Args:
        img_url (str): URL of the image to process
        model_id (str): AWS Bedrock model ID to use
        prompt (str): Prompt to send to the model

    Returns:
        str: The model's response text

    Raises:
        requests.exceptions.RequestException: If image download fails
        ValueError: If image processing fails
    """
    logger.debug(f"Downloading image")
    response = requests.get(img_url, timeout=10)
    response.raise_for_status()

    # Convert image to base64
    binary_data = response.content
    image = Image.open(BytesIO(binary_data)).convert("RGB")
    image_buffer = BytesIO()
    image.save(image_buffer, format="JPEG")
    base64_encoded_data = base64.b64encode(image_buffer.getvalue()).decode("utf-8")

    # Prepare request for Bedrock
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

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": message_list,
    }

    logger.debug(f"Invoking Bedrock model: {model_id}")
    bedrock_response = api_client_manager.bedrock_client.invoke_model(
        modelId=model_id,
        body=json.dumps(request_body),
    )

    model_response = json.loads(bedrock_response["body"].read())

    # Extract text from response
    content_list = model_response.get("content", [])
    if not content_list:
        return "No description returned."

    return content_list[0].get("text", "No description returned.")


def describe_images(place_id: str) -> List[Dict[str, Any]]:
    """
    Generate descriptions for all unprocessed images of a place.

    This function:
    1. Retrieves all images for the place
    2. Processes images that don't have descriptions
    3. Stores descriptions in MongoDB
    4. Returns all image data with descriptions

    Args:
        place_id (str): Google Maps place ID

    Returns:
        List[Dict[str, Any]]: List of image data including:
            - googleMapsUri (str): Image URL
            - description (str): Generated description
            - index (int): Image index
    """
    # Get images with their indices
    photo_data = get_images_for_place(place_id)
    if isinstance(photo_data, dict) and "error" in photo_data:
        return photo_data

    logger.info(f"Processing {len(photo_data)} images with Bedrock")

    model_id = Config.BEDROCK_MICRO_MODEL
    results = {}

    # Process images in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Map each image to a future
        future_map = {
            executor.submit(
                _encode_and_describe,
                photo_url,
                model_id,
                "Provide describe this image succinctly.",
            ): (photo_url, idx, photo_name)
            for photo_url, idx, photo_name in photo_data
        }

        # Process results as they complete
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

    # Update MongoDB with results
    logger.debug(f"Storing image descriptions for place_id: {place_id}")
    place_data = get_place(place_id)

    if not place_data or "photos" not in place_data:
        logger.error(f"No photo data found for place_id: {place_id}")
        return []

    photos = place_data["photos"]
    for idx, result in results.items():
        if idx < len(photos):
            photos[idx]["description"] = result.get("description", result.get("error"))

    update_place_field(place_id, "photos", photos)

    # Format response
    return [
        {
            "googleMapsUri": photo.get("googleMapsUri"),
            "description": photo.get("description"),
            "index": idx,
        }
        for idx, photo in enumerate(photos)
    ]


def extract_image_info(image_index: int, place_id: str, query: str) -> Dict[str, Any]:
    """
    Extract specific information from an image using AI analysis.

    This function:
    1. Validates the image index
    2. Retrieves the image URL
    3. Processes the image with a specific query
    4. Returns the extracted information

    Args:
        image_index (int): Index of the image to analyze
        place_id (str): Google Maps place ID
        query (str): Specific information to extract (e.g., "What items are on the menu?")

    Returns:
        Dict[str, Any]: Dictionary containing:
            - info (str): Extracted information
            - error (str, optional): Error message if processing failed
    """
    logger.info(f"Extracting info from image {image_index} for place_id {place_id}")

    # Get place data
    place_data = get_place(place_id)
    if not place_data:
        error_msg = f"Place not found for place_id: {place_id}"
        logger.error(error_msg)
        return {"error": error_msg}

    photo_data = place_data.get("photos")
    if not photo_data:
        error_msg = f"No photo data found for place_id: {place_id}"
        logger.error(error_msg)
        return {"error": error_msg}

    if image_index >= len(photo_data):
        error_msg = f"Invalid image index: {image_index}"
        logger.error(error_msg)
        return {"error": error_msg}

    # Get image URL
    photo_name = photo_data[image_index]["name"]
    photo_url = (
        f"{Config.GOOGLE_MAPS_PHOTOS_ENDPOINT}/{photo_name}/media"
        f"?maxHeightPx=400&maxWidthPx=400&key={Config.GOOGLE_MAPS_API_KEY}"
    )

    try:
        # Process image with larger model
        model_id = Config.BEDROCK_PRO_MODEL
        info = _encode_and_describe(photo_url, model_id, query)
        logger.debug(f"Extracted info from image {image_index}: {info[:100]}...")
        return {"info": info}

    except Exception as e:
        error_msg = f"Error extracting image info: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"error": error_msg}
