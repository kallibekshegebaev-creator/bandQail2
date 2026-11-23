"""Adminga Telegram orqali xabar yuborish. BOT_TOKEN va ADMIN_IDS .env'da bo'lmasa, faqat logga yozadi."""
import json
import logging
import urllib.request

import config

log = logging.getLogger("bandqil")


def notify_admins(text: str) -> None:
    if not config.BOT_TOKEN or not config.ADMIN_IDS:
        log.info("Admin xabari (Telegram sozlanmagan): %s", text)
        return
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendMessage"
    for admin_id in config.ADMIN_IDS:
        try:
            data = json.dumps({"chat_id": admin_id, "text": text}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:  # xabar yetmasa ham bron buzilmasin
            log.warning("Adminga xabar yuborilmadi (id=%s): %s", admin_id, type(e).__name__)
