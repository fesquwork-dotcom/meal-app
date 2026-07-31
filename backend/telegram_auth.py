"""
Telegram Mini App initData validation.

Official algorithm:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl

import config

logger = logging.getLogger(__name__)

AUTH_HEADER_SCHEME = "tma"
AUTH_FAILED_MESSAGE = "Telegram authentication failed"
WEBAPP_DATA_CONSTANT = b"WebAppData"
CRITICAL_INIT_DATA_FIELDS = frozenset({"hash", "user", "auth_date"})


class TelegramAuthError(Exception):
    """Raised when initData validation fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class TelegramAuthData:
    user_id: int
    first_name: str
    username: Optional[str]
    auth_date: datetime
    raw_user: dict[str, object]
    is_development: bool = False


def _build_data_check_string(parsed_items: dict[str, str]) -> str:
    return "\n".join(f"{key}={value}" for key, value in sorted(parsed_items.items()))


def _compute_secret_key(bot_token: str) -> bytes:
    return hmac.new(
        key=WEBAPP_DATA_CONSTANT,
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()


def _compute_hash(secret_key: bytes, data_check_string: str) -> str:
    return hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def _parse_query_pairs(init_data: str) -> dict[str, str]:
    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    parsed: dict[str, str] = {}

    for key, value in pairs:
        if key in parsed:
            if key in CRITICAL_INIT_DATA_FIELDS:
                raise TelegramAuthError("duplicate critical field")
            raise TelegramAuthError("duplicate field")
        parsed[key] = value

    return parsed


def _parse_auth_date(raw_auth_date: str) -> datetime:
    try:
        timestamp = int(raw_auth_date)
    except ValueError as exc:
        raise TelegramAuthError("invalid auth_date") from exc

    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _validate_auth_date(auth_date: datetime) -> None:
    now = datetime.now(timezone.utc)
    skew = config.TELEGRAM_AUTH_CLOCK_SKEW_SECONDS
    max_age = config.TELEGRAM_INIT_DATA_MAX_AGE_SECONDS

    auth_ts = auth_date.timestamp()
    now_ts = now.timestamp()

    if auth_ts > now_ts + skew:
        raise TelegramAuthError("auth_date too far in the future")

    if now_ts - auth_ts > max_age + skew:
        raise TelegramAuthError("expired initData")


def _parse_user_payload(raw_user: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw_user)
    except json.JSONDecodeError as exc:
        raise TelegramAuthError("invalid user json") from exc

    if not isinstance(parsed, dict):
        raise TelegramAuthError("invalid user json")

    return parsed


def _validate_user_id(user_id: object) -> int:
    if type(user_id) is not int or user_id <= 0:
        raise TelegramAuthError("invalid user id")
    return user_id


def validate_init_data(init_data: str, bot_token: str) -> TelegramAuthData:
    """Validates Telegram WebApp initData and returns authenticated user data."""
    if not init_data.strip():
        raise TelegramAuthError("empty initData")

    if not bot_token:
        raise TelegramAuthError("bot token not configured")

    parsed = _parse_query_pairs(init_data)

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("missing hash")

    data_check_string = _build_data_check_string(parsed)
    secret_key = _compute_secret_key(bot_token)
    calculated_hash = _compute_hash(secret_key, data_check_string)

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TelegramAuthError("invalid signature")

    raw_auth_date = parsed.get("auth_date")
    if not raw_auth_date:
        raise TelegramAuthError("missing auth_date")

    auth_date = _parse_auth_date(raw_auth_date)
    _validate_auth_date(auth_date)

    raw_user_value = parsed.get("user")
    if not raw_user_value:
        raise TelegramAuthError("missing user")

    user_payload = _parse_user_payload(raw_user_value)
    user_id = _validate_user_id(user_payload.get("id"))

    first_name = user_payload.get("first_name")
    username = user_payload.get("username")

    return TelegramAuthData(
        user_id=user_id,
        first_name=first_name if isinstance(first_name, str) else "",
        username=username if isinstance(username, str) else None,
        auth_date=auth_date,
        raw_user=user_payload,
    )

