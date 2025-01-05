"""
Exa API service for searching website content.

This module provides functionality to:
- Search specific domains for content
- Process and validate search results
- Handle API errors gracefully
"""

from typing import Optional, Dict, Any
from utils.logger import logger
from utils.clients import api_client_manager


def search_domain(domain: str, query: str) -> Dict[str, Any]:
    """
    Perform a search on a specific domain using Exa API.

    This function:
    1. Validates input parameters
    2. Executes the search using the Exa client
    3. Processes and formats the results
    4. Handles any API errors

    Args:
        domain (str): The domain to search within (e.g., 'portagebaycafe.com')
        query (str): The search query to execute

    Returns:
        Dict[str, Any]: A dictionary containing:
            - results (list): List of text content from search results
            - count (int): Number of results found
            - error (str, optional): Error message if search failed

    Example:
        >>> result = search_domain("restaurant.com", "lunch menu")
        >>> print(result)
        {
            'results': ['Menu content...', 'More content...'],
            'count': 2
        }
    """
    logger.info(f"Starting Exa search for domain: {domain} with query: {query}")

    try:
        # Input validation
        if not domain or not query:
            raise ValueError("Both domain and query parameters are required")

        # Get Exa client from manager
        exa_client = api_client_manager.exa
        logger.debug(f"Making Exa API call for domain: {domain}")
        
        # Execute search
        result = exa_client.search_and_contents(
            query, 
            type="auto", 
            include_domains=[domain], 
            text=True
        )

        if not result:
            logger.warning("Exa API returned no results")
            return {"results": [], "count": 0}

        if not result.results:
            logger.warning("No matching content found in search results")
            return {"results": [], "count": 0}

        # Extract and combine text content from results
        combined_results = []
        for item in result.results:
            if hasattr(item, "text") and item.text:
                combined_results.append(item.text)
            else:
                logger.debug(f"Skipping result without text content: {item}")

        logger.info(f"Successfully found {len(combined_results)} results")
        return {
            "results": combined_results, 
            "count": len(combined_results)
        }

    except ValueError as ve:
        error_msg = f"Invalid input parameters: {str(ve)}"
        logger.error(error_msg)
        return {"error": error_msg, "results": [], "count": 0}
    except Exception as e:
        error_msg = f"Error performing Exa search: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"error": error_msg, "results": [], "count": 0}
