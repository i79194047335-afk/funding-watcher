import requests
import json
from datetime import datetime

# Адрес API Hyperliquid — бесплатно, без ключей
URL = "https://api.hyperliquid.xyz/info"

def get_funding_rates():
    """Запрашиваем текущие ставки фандинга по всем монетам"""
    payload = {"type": "metaAndAssetCtxs"}
    
    response = requests.post(URL, json=payload)
    data = response.json()
    
    # data[0] — список монет с названиями
    # data[1] — список данных по каждой монете
    coins = data[0]["universe"]
    contexts = data[1]
    
    results = []
    
    for i, coin in enumerate(coins):
        name = coin["name"]
        ctx = contexts[i]
        
        # fundingRate — текущая ставка за час (в долях, не в процентах)
        funding_rate = float(ctx["funding"])
        
        # Переводим в проценты и считаем годовых
        hourly_pct = funding_rate * 100        # % в час
        annual_pct = hourly_pct * 24 * 365    # % годовых (грубо)
        
        results.append({
            "coin": name,
            "hourly_%": round(hourly_pct, 4),
            "annual_%": round(annual_pct, 1)
        })
    
    return results

def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Запрашиваем данные...\n")
    
    rates = get_funding_rates()
    
    # Сортируем по модулю — самые большие отклонения наверху
    rates.sort(key=lambda x: abs(x["hourly_%"]), reverse=True)
    
    print(f"{'Монета':<12} {'% в час':>10} {'% годовых':>12}")
    print("-" * 36)
    
    # Показываем топ-20
    for r in rates[:20]:
        hourly = r["hourly_%"]
        annual = r["annual_%"]
        
        # Помечаем интересные (больше 0.1% в час)
        flag = " ★" if abs(hourly) > 0.1 else ""
        
        print(f"{r['coin']:<12} {hourly:>10.4f} {annual:>11.1f}%{flag}")
    
    print(f"\nВсего монет: {len(rates)}")
    print("★ = больше 0.1% в час (интересно для стратегии)")

if __name__ == "__main__":
    main()