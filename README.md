# Funding Watcher

Наблюдатель за ставками фандинга на Hyperliquid.
Тянет данные по перпам и подсвечивает интересные перекосы для market-neutral стратегии.

**Статус:** работает 24/7 (шаг 5/6 — запущен на VPS по cron)

## Стек
- Python 3.10
- requests, python-dotenv

## Запуск
Разово (вручную):

    python3 watcher.py

24/7 через cron (каждые 15 минут):

    */15 * * * * cd /root/projects/funding-watcher && /usr/bin/python3 watcher.py >> logs/watcher.log 2>&1

## Настройки
- `.env` — токен Telegram-бота и chat_id (не в git)
- пороги в начале `watcher.py`: `MIN_FUNDING_PCT`, `MIN_VOLUME_USD`

