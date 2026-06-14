import requests
from datetime import datetime

# Адрес API Hyperliquid — бесплатно, без ключей
URL = "https://api.hyperliquid.xyz/info"

# --- Пороги стратегии (можно крутить) ---
MIN_FUNDING_PCT = 0.05    # ставка в час, %: ниже — неинтересно (комиссии съедят)
MIN_VOLUME_USD = 1_000_000  # объём за 24ч, $: ниже — слишком тонко, большой слиппедж


def get_spot_bases():
    """Возвращает множество монет, у которых есть нативный спот против USDC на Hyperliquid.
    Спот нужен для нейтрального хеджа: держим спот + противоположный перп."""
    data = requests.post(URL, json={"type": "spotMetaAndAssetCtxs"}, timeout=10).json()
    tokens = data[0]["tokens"]
    name_by_index = {t["index"]: t["name"] for t in tokens}

    bases = set()
    for pair in data[0]["universe"]:
        base_i, quote_i = pair["tokens"]
        if name_by_index.get(quote_i) == "USDC":
            bases.add(name_by_index.get(base_i))
    return bases


def get_funding_rates(spot_bases):
    """Запрашиваем фандинг + ликвидность по всем перпам и помечаем наличие спота."""
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


def fmt_volume(v):
    """Объём в читаемый вид: $12.3M / $456K."""
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:.0f}"


def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Запрашиваем данные...\n")

    spot_bases = get_spot_bases()
    rates = get_funding_rates(spot_bases)

    # --- Блок 1: топ-20 по силе фандинга (общая картина) ---
    rates.sort(key=lambda x: abs(x["hourly_%"]), reverse=True)

    print("ТОП-20 ПО ФАНДИНГУ")
    print(f"{'Монета':<12}{'% в час':>10}{'% годовых':>12}{'объём 24ч':>12}{'спот':>7}")
    print("-" * 53)
    for r in rates[:20]:
        spot = "есть" if r["has_spot"] else "—"
        print(f"{r['coin']:<12}{r['hourly_%']:>10.4f}{r['annual_%']:>11.1f}%"
              f"{fmt_volume(r['volume_usd']):>12}{spot:>7}")

    # --- Блок 2: реальные кандидаты (прошли все три фильтра) ---
    candidates = [
        r for r in rates
        if abs(r["hourly_%"]) >= MIN_FUNDING_PCT
        and r["volume_usd"] >= MIN_VOLUME_USD
        and r["has_spot"]
    ]

    print(f"\nРЕАЛЬНЫЕ КАНДИДАТЫ "
          f"(фандинг ≥ {MIN_FUNDING_PCT}%/ч, объём ≥ {fmt_volume(MIN_VOLUME_USD)}, есть спот)")
    print("-" * 53)
    if not candidates:
        print("Сейчас таких нет — рынок спокойный. Это нормально, ждём волну.")
    else:
        for r in candidates:
            side = "шорт перп" if r["hourly_%"] > 0 else "лонг перп"
            print(f"{r['coin']:<12}{r['hourly_%']:>10.4f}%/ч  "
                  f"объём {fmt_volume(r['volume_usd'])}  → собираем: {side} + спот")

    print(f"\nВсего перпов: {len(rates)} | со спотом на HL: {sum(r['has_spot'] for r in rates)}")


if __name__ == "__main__":
    main()
