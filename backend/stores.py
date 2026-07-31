import logging

logger = logging.getLogger(__name__)

async def get_prices(store: str, proteins: list) -> dict:
    logger.info(f"Магазин {store} временно отключен для Web App MVP")
    return {}

def format_prices_for_prompt(prices: dict, store: str, limit: int = 30) -> str:
    return ""