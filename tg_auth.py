"""Telegram Mini App 'initData' ni tekshirish.

Telegram har bir Mini App ochilishida brauzerga 'initData' degan qator beradi — unda
foydalanuvchi ma'lumoti va botning maxfiy kaliti bilan hisoblangan HMAC imzo ('hash') bor.
Agar buni serverda tekshirmasak, brauzer konsolidan istalgan odam o'zini boshqa
foydalanuvchi qilib ko'rsatishi (va uning bronlarini ko'rish/bekor qilishi) mumkin bo'lib qoladi.

Hujjat: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import time
from typing import Optional
from urllib.parse import parse_qsl

MAX_AGE_SEC = 24 * 60 * 60  # initData shu muddatdan eski bo'lsa, eskirgan deb hisoblanadi


def verify_init_data(init_data: str, bot_token: str, max_age_sec: int = MAX_AGE_SEC) -> Optional[dict]:
    """To'g'ri va eskirmagan bo'lsa, Telegram foydalanuvchisi (dict) qaytaradi. Aks holda None."""
    if not init_data or not bot_token:
        return None
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = parsed.get("auth_date")
    if auth_date:
        try:
            if time.time() - int(auth_date) > max_age_sec:
                return None
        except ValueError:
            return None

    user_json = parsed.get("user")
    if not user_json:
        return None
    try:
        user = json.loads(user_json)
    except json.JSONDecodeError:
        return None
    if "id" not in user:
        return None
    return user
