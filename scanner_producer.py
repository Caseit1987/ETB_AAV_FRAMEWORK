import json
import urllib.request
from etbv_client import ETBVClient

PAIRS = [
    ("BTC/USD", "BTC-USD", "XBTUSD"),
    ("ETH/USD", "ETH-USD", "ETHUSD"),
    ("SOL/USD", "SOL-USD", "SOLUSD"),
]

def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "ETBV-Scanner/1.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))

def scan_all_pairs(min_spread_pct: float = 0.001):
    client = ETBVClient()
    for pair_label, cb_symbol, kr_symbol in PAIRS:
        try:
            cb_url = "https://" + "api." + "coinbase.com" + f"/v2/prices/{cb_symbol}/spot"
            kr_url = "https://" + "api." + "kraken.com" + f"/0/public/Ticker?pair={kr_symbol}"

            cb = fetch_json(cb_url)
            kr = fetch_json(kr_url)

            cb_price = float(cb["data"]["amount"])
            kr_result = next(iter(kr["result"].values()))
            kr_price = float(next(iter(kr_result["c"])))

            ask_price = min(cb_price, kr_price)
            bid_price = max(cb_price, kr_price)
            source_market = "COINBASE" if cb_price <= kr_price else "KRAKEN"
            target_market = "KRAKEN" if cb_price <= kr_price else "COINBASE"
            spread_pct = round(((bid_price - ask_price) / ask_price) * 100.0, 4)

            print(f"[SCANNER] {pair_label} | {source_market} (${ask_price:,.2f}) -> {target_market} (${bid_price:,.2f}) | Spread: {spread_pct}%", flush=True)

            if spread_pct >= min_spread_pct:
                status, resp = client.submit_arbitrage_signal(
                    source_market=source_market,
                    target_market=target_market,
                    asset_pair=pair_label,
                    spread_percentage=spread_pct,
                    ask_price=ask_price,
                    bid_price=bid_price
                )
                print(f"[GATE SUBMIT] {pair_label} -> HTTP {status} | {resp}", flush=True)
        except Exception as exc:
            print(f"[SCANNER ERROR] {pair_label}: {exc}", flush=True)

if __name__ == "__main__":
    scan_all_pairs(min_spread_pct=0.001)
