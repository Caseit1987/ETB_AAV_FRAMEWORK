import json
import time
import urllib.request
from etbv_client import ETBVClient

def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "ETBV-Scanner/1.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))

def scan_btc_spread(min_spread_pct: float = 0.01):
    # Fetch live spot quotes from Coinbase and Kraken public APIs
    cb = fetch_json("https://api.coinbase.com/v2/prices/BTC-USD/spot")
    kr = fetch_json("https://api.kraken.com/0/public/Ticker?pair=XBTUSD")

    cb_price = float(cb["data"]["amount"])
    kr_price = float(kr["result"]["XXBTZUSD"]["c"][0])

    ask_price = min(cb_price, kr_price)
    bid_price = max(cb_price, kr_price)
    source_market = "COINBASE" if cb_price <= kr_price else "KRAKEN"
    target_market = "KRAKEN" if cb_price <= kr_price else "COINBASE"
    spread_pct = round(((bid_price - ask_price) / ask_price) * 100.0, 4)

    print(f"[SCANNER] {source_market} (${ask_price:,.2f}) -> {target_market} (${bid_price:,.2f}) | Spread: {spread_pct}%")

    if spread_pct >= min_spread_pct:
        client = ETBVClient()
        status, resp = client.submit_arbitrage_signal(
            source_market=source_market,
            target_market=target_market,
            asset_pair="BTC/USD",
            spread_percentage=spread_pct,
            ask_price=ask_price,
            bid_price=bid_price
        )
        print(f"[GATE SUBMIT] HTTP {status} -> {resp}")
    else:
        print(f"[SCANNER] Spread {spread_pct}% below threshold ({min_spread_pct}%), skipping write.")

if __name__ == "__main__":
    scan_btc_spread(min_spread_pct=0.001)
