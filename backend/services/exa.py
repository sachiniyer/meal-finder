#!/usr/bin/env python3

from exa_py import Exa
from typing import Optional, Dict, Any, List
from config import Config
from utils.logger import logger

exa = Exa(api_key=Config.EXA_API_KEY)
logger.info("Initialized Exa API client")


def search_domain(domain: str, query: str) -> Optional[Dict[str, Any]]:
    """
    Perform a search on a specific domain using Exa API.

    Args:
        domain (str): The domain to search within (e.g., 'portagebaycafe.com')
        query (str): The search query

    Returns:
        Optional[Dict[str, Any]]: The search results or None if the search fails
    """
    logger.info(f"Starting Exa search for domain: {domain} with query: {query}")

    try:

        logger.debug(f"Making Exa API call for domain: {domain}")
        result = exa.search_and_contents(
            query, type="auto", include_domains=[domain], text=True
        )

        if result and result.results:
            logger.info("Successfully completed Exa search")

            # Extract and combine all text content from results
            combined_results = []
            for item in result.results:
                if hasattr(item, "text"):
                    combined_results.append(item.text)

            return {"results": combined_results, "count": len(combined_results)}
        else:
            logger.warning("No results found in Exa search")
            return {"results": [], "count": 0}

    except Exception as e:
        logger.error(f"Error performing Exa search: {str(e)}", exc_info=True)
        return {"error": str(e)}
