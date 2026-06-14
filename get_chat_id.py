"""Помощник: находит твой chat_id.
Перед запуском: 1) вставь токен в .env, 2) напиши своему боту любое сообщение в Telegram.
Запуск: python3 get_chat_id.py
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN or "сюда" in TOKEN:
    print("Сначала вставь токен от @BotFather в файл .env (поле TELEGRAM_BOT_TOKEN).")
    raise SystemExit

url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
data = requests.get(url, timeout=10).json()

if not data.get("ok"):
    print("Telegram вернул ошибку — проверь токен:", data)
    raise SystemExit

results = data.get("result", [])
if not results:
    print("Сообщений пока нет. Напиши своему боту любое сообщение в Telegram и запусти снова.")
    raise SystemExit

# Берём chat_id из последнего сообщения
chat = results[-1]["message"]["chat"]
print(f"Твой chat_id: {chat['id']}")
print(f"(имя в Telegram: {chat.get('first_name', '?')} {chat.get('username', '')})")
print("\nВставь это число в .env → TELEGRAM_CHAT_ID")
