import os
import json
import requests
from datetime import datetime

import telegram_notify

# Файл, где помним, о каких монетах уже уведомили (защита от спама)
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "notified_state.json")

# Адрес API Hyperliquid — бесплатно, без ключей
URL = "https://api.hyperliquid.xyz/info"

# --- Пороги стратегии (можно крутить) ---
MIN_FUNDING_PCT = 0.05      # ставка в час, %: ниже — неинтересно (комиссии съедят)
MIN_ACTIONABLE_PCT = 0.10   # ставка в час, %: выше этого — отбивает комиссии, можно входить
MIN_VOLUME_USD = 1_000_000  # объём за 24ч, $: ниже — слишком тонко, большой слиппедж

# Файл с историей (CSV) — по строке на монету за каждый запуск
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "history.csv")


def get_spot_bases():
    """Возвращает множество монет, у которых есть нативный спот против USDC на Hyperliquid.
    Спот нужен для нейтрального хеджа: держим спот + противоположный перп."""
    try:
        data = requests.post(URL, json={"type": "spotMetaAndAssetCtxs"}, timeout=10).json()
        tokens = data[0]["tokens"]
        name_by_index = {t["index"]: t["name"] for t in tokens}

        bases = set()
        for pair in data[0]["universe"]:
            base_i, quote_i = pair["tokens"]
            if name_by_index.get(quote_i) == "USDC":
                bases.add(name_by_index.get(base_i))
        return bases
    except Exception as e:
        log(f"ОШИБКА get_spot_bases: {e}")
        print(f"[!] Ошибка при запросе спотов: {e}")
        return set()


def get_funding_rates(spot_bases):
    """Запрашиваем фандинг + ликвидность по всем перпам и помечаем наличие спота."""
    try:
        data = requests.post(URL, json={"type": "metaAndAssetCtxs"}, timeout=10).json()
        coins = data[0]["universe"]
        contexts = data[1]

        results = []
        for i, coin in enumerate(coins):
            name = coin["name"]
            ctx = contexts[i]

            # fundingRate — ставка за час (в долях). dayNtlVlm — объём за 24ч в $.
            funding_rate = float(ctx["funding"])
            day_volume = float(ctx["dayNtlVlm"])

            hourly_pct = funding_rate * 100        # % в час
            annual_pct = hourly_pct * 24 * 365     # % годовых (грубо)

            results.append({
                "coin": name,
                "hourly_%": round(hourly_pct, 4),
                "annual_%": round(annual_pct, 1),
                "volume_usd": day_volume,
                "has_spot": name in spot_bases,
            })
        return results
    except Exception as e:
        log(f"ОШИБКА get_funding_rates: {e}")
        print(f"[!] Ошибка при запросе фандинга: {e}")
        return []


def fmt_volume(v):
    """Объём в читаемый вид: $12.3M / $456K."""
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:.0f}"


def log(msg):
    """Пишет строку с меткой времени в лог-файл."""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "watcher.log")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a") as f:
        f.write(f"[{stamp}] {msg}\n")


def save_history(rates):
    """Добавляет строки в CSV с историей по всем монетам за этот запуск."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = os.path.exists(HISTORY_FILE)
    with open(HISTORY_FILE, "a") as f:
        if not file_exists:
            f.write("timestamp,coin,hourly_pct,annual_pct,volume_usd,has_spot\n")
        for r in rates:
            f.write(f"{stamp},{r['coin']},{r['hourly_%']},{r['annual_%']},{r['volume_usd']},{r['has_spot']}\n")


def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Запрашиваем данные...\n")

    spot_bases = get_spot_bases()
    rates = get_funding_rates(spot_bases)

    if not rates:
        print("Данные не получены (API не ответил). Проверь логи.")
        log("Запуск прерван: API не вернул данные")
        return

    # --- Сохраняем историю по всем монетам в CSV ---
    save_history(rates)

    # --- Блок 1: топ-20 по силе фандинга (общая картина) ---
    rates.sort(key=lambda x: abs(x["hourly_%"]), reverse=True)

    print("ТОП-20 ПО ФАНДИНГУ")
    print(f"{'Монета':<12}{'% в час':>10}{'% годовых':>12}{'объём 24ч':>12}{'спот':>7}")
    print("-" * 53)
    for r in rates[:20]:
        spot = "есть" if r["has_spot"] else "—"
        print(f"{r['coin']:<12}{r['hourly_%']:>10.4f}{r['annual_%']:>11.1f}%"
              f"{fmt_volume(r['volume_usd']):>12}{spot:>7}")

    # --- Блок 2: кандидаты (прошли все три фильтра) с разделением по порогам ---
    candidates = [
        r for r in rates
        if abs(r["hourly_%"]) >= MIN_FUNDING_PCT
        and r["volume_usd"] >= MIN_VOLUME_USD
        and r["has_spot"]
    ]

    # Три группы: отбивает комиссии / наблюдаем / недоступен (нужен шорт спота)
    actionable = [r for r in candidates if r["hourly_%"] >= MIN_ACTIONABLE_PCT]
    watchlist = [r for r in candidates if MIN_FUNDING_PCT <= r["hourly_%"] < MIN_ACTIONABLE_PCT]
    skip_negative = [r for r in candidates if r["hourly_%"] <= 0]

    print(f"\nКАНДИДАТЫ "
          f"(фандинг ≥ {MIN_FUNDING_PCT}%/ч, объём ≥ {fmt_volume(MIN_VOLUME_USD)}, есть спот)")
    print("-" * 53)
    if not candidates:
        print("Сейчас таких нет — рынок спокойный. Это нормально, ждём волну.")
    else:
        if actionable:
            print(f"  ✅ Доступны для сделки (≥{MIN_ACTIONABLE_PCT}%/ч — отбивает комиссии):")
            for r in actionable:
                print(f"  {r['coin']:<12}{r['hourly_%']:>10.4f}%/ч  "
                      f"объём {fmt_volume(r['volume_usd'])}  → шорт перп + спот")
        if watchlist:
            print(f"  👀 Наблюдаем ({MIN_FUNDING_PCT}–{MIN_ACTIONABLE_PCT}%/ч — близко, но мало):")
            for r in watchlist:
                print(f"  {r['coin']:<12}{r['hourly_%']:>10.4f}%/ч  "
                      f"объём {fmt_volume(r['volume_usd'])}  → следим, ждём роста")
        if skip_negative:
            print("  ✗ Пропускаем (−, нужен шорт спота — на HL недоступен):")
            for r in skip_negative:
                print(f"  {r['coin']:<12}{r['hourly_%']:>10.4f}%/ч  "
                      f"объём {fmt_volume(r['volume_usd'])}  → недоступен")

    print(f"\nВсего перпов: {len(rates)} | со спотом на HL: {sum(r['has_spot'] for r in rates)}")

    # --- Уведомление в Telegram: только actionable (≥0.10%), с сигналом на вход и на выход ---
    current_actionable = {r["coin"]: r for r in actionable}
    already_notified = load_notified()

    new_coins = [c for c in current_actionable if c not in already_notified]
    exited_coins = [c for c in already_notified if c not in current_actionable]

    if new_coins:
        print(f"Новых кандидатов: {len(new_coins)} → шлю в Telegram")
        notify_candidates([current_actionable[c] for c in new_coins])
        for c in new_coins:
            log(f"НОВЫЙ КАНДИДАТ: {c} ({current_actionable[c]['hourly_%']:.4f}%/ч, объём {fmt_volume(current_actionable[c]['volume_usd'])})")
    else:
        print("Новых кандидатов нет — Telegram не беспокою.")

    if exited_coins:
        print(f"Вышли из кандидатов: {len(exited_coins)} → шлю в Telegram")
        notify_exited(exited_coins)
        for c in exited_coins:
            log(f"ВЫШЕЛ: {c} (ставка вернулась к норме)")

    # Запоминаем текущий список доступных: ушедшие забываются и при возврате снова дадут сигнал
    save_notified(list(current_actionable.keys()))


def load_notified():
    """Читает множество монет, о которых уже уведомили."""
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_notified(coins):
    """Сохраняет текущий список уведомлённых монет."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(coins, f)


def notify_candidates(candidates):
    """Собирает сообщение по кандидатам и шлёт в Telegram."""
    lines = ["🔔 <b>Funding Watcher: есть кандидаты!</b>", ""]
    for r in candidates:
        side = "шорт перп" if r["hourly_%"] > 0 else "лонг перп"
        url = f"https://app.hyperliquid.xyz/trade/{r['coin']}"
        lines.append(
            f'<a href="{url}"><b>{r["coin"]}</b></a>: {r["hourly_%"]:.4f}%/ч '
            f"({r['annual_%']:.0f}%/год), объём {fmt_volume(r['volume_usd'])}\n"
            f"→ {side} + спот"
        )
    telegram_notify.send_message("\n".join(lines))


def notify_exited(coins):
    """Шлёт в Telegram предупреждение: кандидат ушёл, пора закрывать."""
    lines = ["🔕 <b>Funding Watcher: кандидаты ушли</b>", ""]
    for coin in coins:
        url = f"https://app.hyperliquid.xyz/trade/{coin}"
        lines.append(
            f'<a href="{url}"><b>{coin}</b></a>: ставка вернулась к норме '
            f"→ пора закрывать позицию (обе ноги)"
        )
    telegram_notify.send_message("\n".join(lines))


if __name__ == "__main__":
    main()
