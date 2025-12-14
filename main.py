from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re
import time

app = Flask(__name__)
CORS(app)  # разрешаем запросы с любых сайтов

# CS:GO
APP_ID = 730
CONTEXT_ID = 2
CURRENCY = 5  # 5 = RUB
USER_AGENT = "Mozilla/5.0"

def get_steamid64(link: str) -> str:
    """Извлекаем steamid64 из ссылки"""
    m = re.search(r"/profiles/(\d+)", link)
    if m:
        return m.group(1)
    resp = requests.get(link, headers={"User-Agent": USER_AGENT}, timeout=10)
    resp.raise_for_status()
    m = re.search(r'"steamid":"(\d+)"', resp.text)
    if not m:
        raise RuntimeError("Не удалось найти steamid")
    return m.group(1)

def get_inventory_items(steamid: str):
    """Получаем предметы инвентаря CS:GO"""
    url = f"https://steamcommunity.com/inventory/{steamid}/{APP_ID}/{CONTEXT_ID}?l=english&count=2000"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError("Steam вернул ошибку")
    descriptions = {f"{d['classid']}_{d.get('instanceid', '0')}": d for d in data.get("descriptions", [])}
    items = []
    for asset in data.get("assets", []):
        key = f"{asset['classid']}_{asset.get('instanceid', '0')}"
        desc = descriptions.get(key, {})
        if desc.get("market_hash_name"):
            items.append(desc["market_hash_name"])
    return items

def get_item_price(market_hash_name: str) -> float | None:
    """Цена предмета в рублях через Steam Market API"""
    url = f"https://steamcommunity.com/market/priceoverview/?appid={APP_ID}&currency={CURRENCY}&market_hash_name={market_hash_name}"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if not data.get("success"):
        return None
    price_str = data.get("lowest_price")
    if not price_str:
        return None
    # Убираем символы валюты, заменяем запятую на точку
    clean = re.sub(r"[^\d,]", "", price_str).replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return None

@app.route("/check", methods=["POST"])
def check():
    data = request.get_json()
    link = data.get("link")
    if not link:
        return jsonify({"error": "No link"}), 400

    try:
        steamid = get_steamid64(link)
        items = get_inventory_items(steamid)
        total = 0.0
        for name in items:
            price = get_item_price(name)
            if price:
                total += price
                time.sleep(0.1)  # не спамим Steam
        return jsonify({"total_value": round(total, 2)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
