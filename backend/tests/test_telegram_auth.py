import hashlib
import hmac
import inspect
import time

import pytest

import config
from telegram_auth import (
    TelegramAuthError,
    validate_init_data,
)
from tests.telegram_hmac_reference import (
    REFERENCE_AUTH_DATE,
    REFERENCE_BOT_TOKEN,
    REFERENCE_EXPECTED_HASH,
    REFERENCE_USER,
    REFERENCE_USER_JSON,
    build_reference_init_data,
    build_reference_init_data_signed_at,
    reference_hash,
    wrong_order_hash,
)

TEST_BOT_TOKEN = "test-bot-token-for-tests"


@pytest.fixture(autouse=True)
def _configure_bot_token(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", TEST_BOT_TOKEN)
    monkeypatch.setattr(config, "TELEGRAM_INIT_DATA_MAX_AGE_SECONDS", 3600)
    monkeypatch.setattr(config, "TELEGRAM_AUTH_CLOCK_SKEW_SECONDS", 60)


@pytest.fixture
def allow_reference_auth_date(monkeypatch):
    """REFERENCE_AUTH_DATE is fixed; disable expiry for vector acceptance tests."""
    monkeypatch.setattr(config, "TELEGRAM_INIT_DATA_MAX_AGE_SECONDS", 10**12)


def test_independent_reference_vector_is_accepted(allow_reference_auth_date):
    init_data = build_reference_init_data()
    auth = validate_init_data(init_data, REFERENCE_BOT_TOKEN)

    assert auth.user_id == REFERENCE_USER["id"]
    assert auth.first_name == REFERENCE_USER["first_name"]
    assert auth.username == REFERENCE_USER["username"]


def test_independent_reference_vector_uses_precomputed_hash(allow_reference_auth_date):
    assert REFERENCE_EXPECTED_HASH == reference_hash(
        REFERENCE_BOT_TOKEN,
        f"auth_date={REFERENCE_AUTH_DATE}\nuser={REFERENCE_USER_JSON}",
    )

    init_data = build_reference_init_data(hash_value=REFERENCE_EXPECTED_HASH)
    auth = validate_init_data(init_data, REFERENCE_BOT_TOKEN)
    assert auth.user_id == 424242


def test_wrong_order_hmac_is_rejected(allow_reference_auth_date):
    wrong_hash = wrong_order_hash(
        REFERENCE_BOT_TOKEN,
        f"auth_date={REFERENCE_AUTH_DATE}\nuser={REFERENCE_USER_JSON}",
    )

    assert wrong_hash != REFERENCE_EXPECTED_HASH

    init_data = build_reference_init_data(hash_value=wrong_hash)

    with pytest.raises(TelegramAuthError, match="invalid signature"):
        validate_init_data(init_data, REFERENCE_BOT_TOKEN)


def test_tampered_reference_vector_fails(allow_reference_auth_date):
    init_data = build_reference_init_data()
    tampered = init_data.replace("Vector", "Eve")

    with pytest.raises(TelegramAuthError, match="invalid signature"):
        validate_init_data(tampered, REFERENCE_BOT_TOKEN)


def test_invalid_hash_rejected(allow_reference_auth_date):
    init_data = build_reference_init_data(hash_value="deadbeef")

    with pytest.raises(TelegramAuthError, match="invalid signature"):
        validate_init_data(init_data, REFERENCE_BOT_TOKEN)


def test_missing_hash_rejected():
    init_data = build_reference_init_data().split("&hash=")[0]

    with pytest.raises(TelegramAuthError, match="missing hash"):
        validate_init_data(init_data, REFERENCE_BOT_TOKEN)


def test_expired_auth_date_rejected():
    old_timestamp = str(int(time.time()) - config.TELEGRAM_INIT_DATA_MAX_AGE_SECONDS - 120)
    init_data = build_reference_init_data_signed_at(
        REFERENCE_BOT_TOKEN,
        old_timestamp,
        REFERENCE_USER,
    )

    with pytest.raises(TelegramAuthError, match="expired initData"):
        validate_init_data(init_data, REFERENCE_BOT_TOKEN)


def test_future_auth_date_rejected():
    future_timestamp = str(int(time.time()) + config.TELEGRAM_AUTH_CLOCK_SKEW_SECONDS + 120)
    init_data = build_reference_init_data_signed_at(
        REFERENCE_BOT_TOKEN,
        future_timestamp,
        REFERENCE_USER,
    )

    with pytest.raises(TelegramAuthError, match="too far in the future"):
        validate_init_data(init_data, REFERENCE_BOT_TOKEN)


def test_compare_digest_used_in_validation():
    source = inspect.getsource(validate_init_data)
    assert "compare_digest" in source


def test_invalid_user_json_rejected():
    import time as time_module
    from urllib.parse import urlencode

    auth_date = str(int(time_module.time()))
    user_json = "not-valid-json"
    data_check_string = f"auth_date={auth_date}\nuser={user_json}"
    hash_value = reference_hash(TEST_BOT_TOKEN, data_check_string)
    init_data = urlencode(
        {
            "auth_date": auth_date,
            "user": user_json,
            "hash": hash_value,
        }
    )

    with pytest.raises(TelegramAuthError, match="invalid user json"):
        validate_init_data(init_data, TEST_BOT_TOKEN)


def test_user_without_id_rejected():
    init_data = build_reference_init_data_signed_at(
        TEST_BOT_TOKEN,
        str(int(time.time())),
        {"first_name": "NoId"},
    )

    with pytest.raises(TelegramAuthError, match="invalid user id"):
        validate_init_data(init_data, TEST_BOT_TOKEN)


def test_bool_user_id_rejected():
    init_data = build_reference_init_data_signed_at(
        TEST_BOT_TOKEN,
        str(int(time.time())),
        {"id": True, "first_name": "Bool"},
    )

    with pytest.raises(TelegramAuthError, match="invalid user id"):
        validate_init_data(init_data, TEST_BOT_TOKEN)


def test_duplicate_hash_rejected(allow_reference_auth_date):
    base = build_reference_init_data()
    duplicated = f"{base}&hash=deadbeef"

    with pytest.raises(TelegramAuthError, match="duplicate critical field"):
        validate_init_data(duplicated, REFERENCE_BOT_TOKEN)


def test_duplicate_user_rejected(allow_reference_auth_date):
    base = build_reference_init_data()
    duplicated = f"{base}&user={REFERENCE_USER_JSON}"

    with pytest.raises(TelegramAuthError, match="duplicate critical field"):
        validate_init_data(duplicated, REFERENCE_BOT_TOKEN)


def test_duplicate_auth_date_rejected(allow_reference_auth_date):
    base = build_reference_init_data()
    duplicated = f"{base}&auth_date={REFERENCE_AUTH_DATE}"

    with pytest.raises(TelegramAuthError, match="duplicate critical field"):
        validate_init_data(duplicated, REFERENCE_BOT_TOKEN)


def test_missing_bot_token_raises_config_error(allow_reference_auth_date):
    init_data = build_reference_init_data()

    with pytest.raises(TelegramAuthError, match="bot token not configured"):
        validate_init_data(init_data, "")


def test_hmac_key_msg_order_in_production_code():
    from telegram_auth import _compute_hash, _compute_secret_key

    secret_key = _compute_secret_key(TEST_BOT_TOKEN)
    expected_secret_key = hmac.new(
        key=b"WebAppData",
        msg=TEST_BOT_TOKEN.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    assert secret_key == expected_secret_key

    data_check_string = "auth_date=1\nuser={}"
    calculated = _compute_hash(secret_key, data_check_string)
    expected = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    assert calculated == expected
