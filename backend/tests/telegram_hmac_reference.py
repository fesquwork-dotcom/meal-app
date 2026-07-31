"""
Independent reference implementation for Telegram initData HMAC tests.

Must NOT import signing helpers from telegram_auth — duplicates the correct
algorithm locally so a shared bug in production code cannot fake a pass.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import urlencode

REFERENCE_BOT_TOKEN = "111111111:TEST-VECTOR-TOKEN"
REFERENCE_AUTH_DATE = "1700000000"
REFERENCE_USER = {
    "id": 424242,
    "first_name": "Vector",
    "username": "vec",
}
REFERENCE_USER_JSON = json.dumps(REFERENCE_USER, separators=(",", ":"), ensure_ascii=False)
REFERENCE_DATA_CHECK_STRING = (
    f"auth_date={REFERENCE_AUTH_DATE}\nuser={REFERENCE_USER_JSON}"
)


def reference_secret_key(bot_token: str) -> bytes:
    return hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()


def reference_hash(bot_token: str, data_check_string: str) -> str:
    secret_key = reference_secret_key(bot_token)
    return hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def wrong_order_secret_key(bot_token: str) -> bytes:
    """Inverted key/msg — must NOT match Telegram's algorithm."""
    return hmac.new(
        key=bot_token.encode("utf-8"),
        msg=b"WebAppData",
        digestmod=hashlib.sha256,
    ).digest()


def wrong_order_hash(bot_token: str, data_check_string: str) -> str:
    secret_key = wrong_order_secret_key(bot_token)
    return hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


REFERENCE_EXPECTED_HASH = reference_hash(REFERENCE_BOT_TOKEN, REFERENCE_DATA_CHECK_STRING)


def build_reference_init_data(
    *,
    bot_token: str = REFERENCE_BOT_TOKEN,
    auth_date: str = REFERENCE_AUTH_DATE,
    user_json: str = REFERENCE_USER_JSON,
    hash_value: str = REFERENCE_EXPECTED_HASH,
) -> str:
    return urlencode(
        {
            "auth_date": auth_date,
            "user": user_json,
            "hash": hash_value,
        }
    )


def build_reference_init_data_signed_at(
    bot_token: str,
    auth_date: str,
    user: dict[str, object],
) -> str:
    user_json = json.dumps(user, separators=(",", ":"), ensure_ascii=False)
    data_check_string = f"auth_date={auth_date}\nuser={user_json}"
    hash_value = reference_hash(bot_token, data_check_string)
    return build_reference_init_data(
        bot_token=bot_token,
        auth_date=auth_date,
        user_json=user_json,
        hash_value=hash_value,
    )
