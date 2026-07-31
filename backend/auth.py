import hashlib
import hmac
import logging
from typing import Optional

from fastapi import Header, HTTPException

import config
from telegram_auth import (
    AUTH_FAILED_MESSAGE,
    AUTH_HEADER_SCHEME,
    TelegramAuthData,
    TelegramAuthError,
    validate_init_data,
)

logger = logging.getLogger(__name__)
SERVICE_UNAVAILABLE_MESSAGE = "Service temporarily unavailable"


def _scheme_matches_tma(scheme: str) -> bool:
    return hmac.compare_digest(scheme.lower().encode("utf-8"), AUTH_HEADER_SCHEME.encode("utf-8"))


def _create_dev_user() -> TelegramAuthData:
    from datetime import datetime, timezone

    logger.warning("Development auth fallback used for user_id=%s", config.DEV_TELEGRAM_USER_ID)

    return TelegramAuthData(
        user_id=config.DEV_TELEGRAM_USER_ID,
        first_name="Developer",
        username=None,
        auth_date=datetime.now(timezone.utc),
        raw_user={"id": config.DEV_TELEGRAM_USER_ID},
        is_development=True,
    )


async def get_current_telegram_user(
    authorization: Optional[str] = Header(default=None),
) -> TelegramAuthData:
    """Extracts and validates Telegram user from Authorization: tma <initData>."""
    if authorization:
        scheme, _, init_data = authorization.partition(" ")

        if not _scheme_matches_tma(scheme) or not init_data.strip():
            logger.warning("Malformed Authorization scheme")
            raise HTTPException(status_code=401, detail=AUTH_FAILED_MESSAGE)

        try:
            auth_data = validate_init_data(init_data.strip(), config.TELEGRAM_BOT_TOKEN)
        except TelegramAuthError as exc:
            if exc.reason == "bot token not configured":
                logger.error("Telegram bot token is not configured")
                raise HTTPException(status_code=503, detail=SERVICE_UNAVAILABLE_MESSAGE) from exc

            logger.warning("Telegram auth failed: %s", exc.reason)
            raise HTTPException(status_code=401, detail=AUTH_FAILED_MESSAGE) from exc

        logger.info("Authenticated Telegram user_id=%s", auth_data.user_id)
        return auth_data

    if config.ALLOW_DEV_AUTH:
        return _create_dev_user()

    logger.warning("Authorization header missing")
    raise HTTPException(status_code=401, detail=AUTH_FAILED_MESSAGE)
