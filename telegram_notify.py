"""Отправка сообщений в Telegram через Bot API (только requests, без лишних библиотек)."""
import os
import requests
from dotenv import load_dotenv

# Грузим .env из папки этого файла — чтобы работало и при запуске из cron (другая cwd)
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_ENV_PATH)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def is_configured():
    """True, если токен и chat_id заданы в .env."""
    return bool(TOKEN) and bool(CHAT_ID) and "сюда" not in (TOKEN or "")


def send_message(text):
    """Шлёт текст тебе в Telegram. Возвращает True при успехе."""
    if not is_configured():
        print("Telegram не настроен (.env): пропускаю отправку.")
        return False

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        ok = r.json().get("ok", False)
        if not ok:
            print("Telegram ответил ошибкой:", r.text)
        return ok
    except Exception as e:
        print("Не смог отправить в Telegram:", e)
        return False


if __name__ == "__main__":
    # Быстрая проверка: python3 telegram_notify.py
    if send_message("✅ Funding Watcher на связи — Telegram работает."):
        print("Отправлено! Проверь чат с ботом.")
