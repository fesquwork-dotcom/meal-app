"""Test-only helpers. Must not be imported by production modules."""

from __future__ import annotations

import json
from time import time
from typing import Optional
from urllib.parse import urlencode

from telegram_auth import _build_data_check_string, _compute_hash, _compute_secret_key


def build_signed_init_data(
    bot_token: str,
    user: dict[str, object],
    auth_date: Optional[int] = None,
) -> str:
    """Builds signed initData for tests using the production HMAC helpers."""
    timestamp = auth_date if auth_date is not None else int(time())
    user_json = json.dumps(user, separators=(",", ":"), ensure_ascii=False)

    payload = {
        "auth_date": str(timestamp),
        "user": user_json,
    }

    data_check_string = _build_data_check_string(payload)
    secret_key = _compute_secret_key(bot_token)
    payload["hash"] = _compute_hash(secret_key, data_check_string)

    return urlencode(payload)
