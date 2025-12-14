import requests
import re
import os
import time
from urllib.parse import urlparse, quote
from dotenv import load_dotenv

PROFILE_URL = ("https://steamcommunity.com/profiles/76561198390944700")
APP_ID = 730
CONTEXT_ID = 2
CURRENCY = 5
REQUEST_TIMEOUT = 8
SLEEP_BETWEEN_PRICE_REQ = 0.1
load_dotenv("kod.env")

def get_steamid64_from_profile_url(profile_url: str, cookies: dict | None = None) -> str:
    parsed = urlparse(profile_url)
    path = parsed.path
    m = re.match(r"^/profiles/(\d+)/?$", path)
    if m:
        return m.group(1)
    resp = requests.get(profile_url, headers={"User-Agent": "Mozilla/5.0"}, cookies=cookies or None, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    html = resp.text
    m = re.search(r'"steamid"\s*:\s*"(\d+)"', html)
    if not m:
        raise RuntimeError("Не удалось извлечь steamid64")
    return m.group(1)

def build_inventory_url(profile_url: str, app_id: int = APP_ID, context_id: int = CONTEXT_ID, cookies: dict | None = None) -> str:
    steamid64 = get_steamid64_from_profile_url(profile_url, cookies=cookies)
    return f"https://steamcommunity.com/inventory/{steamid64}/{app_id}/{context_id}?l=english&count=2000"

def get_inventory(profile_url: str, cookies: dict | None = None, app_id: int = APP_ID, context_id: int = CONTEXT_ID):
    url = build_inventory_url(profile_url, app_id, context_id, cookies=cookies)
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, cookies=cookies or None, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Steam error: {data}")
    assets = data.get("assets", [])
    descriptions = data.get("descriptions", [])
    desc_index = {f"{d.get('classid')}_{d.get('instanceid', '0')}": d for d in descriptions}
    items = []
    for a in assets:
        key = f"{a.get('classid')}_{a.get('instanceid', '0')}"
        desc = desc_index.get(key, {})
        items.append({
            "assetid": a.get("assetid"),
            "classid": a.get("classid"),
            "instanceid": a.get("instanceid"),
            "name": desc.get("market_hash_name") or desc.get("name"),
            "type": desc.get("type"),
        })
    return items

def get_item_price(app_id: int, market_hash_name: str, currency: int = CURRENCY, retries: int = 3):
    url = f"https://steamcommunity.com/market/priceoverview/?appid={app_id}&currency={currency}&market_hash_name={quote(market_hash_name)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return {
                        "lowest_price": data.get("lowest_price"),
                        "median_price": data.get("median_price"),
                        "volume": data.get("volume"),
                    }
        except Exception as e:
            pass
        if attempt < retries:
            time.sleep(0.5 * attempt)
    return None

def add_prices_to_items(items, app_id: int = APP_ID, currency: int = CURRENCY):
    unique_names = list({item.get("name") for item in items if item.get("name")})
    price_cache = {}
    for name in unique_names:
        if SLEEP_BETWEEN_PRICE_REQ > 0:
            time.sleep(SLEEP_BETWEEN_PRICE_REQ)
        price = get_item_price(app_id, name, currency)
        price_cache[name] = price
    for item in items:
        name = item.get("name")
        if name:
            item["price"] = price_cache.get(name)
    return items

def parse_price_to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    clean = re.sub(r"[^0-9,\.]", "", raw).replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return None
