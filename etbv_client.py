import os
import json
import urllib.request
import urllib.error

class ETBVClient:
    def __init__(self, base_url: str = "http://localhost:8000", api_token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token or os.environ["ETB_MASTER_TOKEN"]

    def _post_raw(self, path: str, raw_bytes: bytes, extra_headers: dict | None = None) -> tuple[int, dict]:
        headers = {
            "X-API-Token": self.api_token,
            "Content-Type": "application/json"
        }
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(f"{self.base_url}{path}", data=raw_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def submit_arbitrage_signal(
        self,
        source_market: str,
        target_market: str,
        asset_pair: str,
        spread_percentage: float,
        ask_price: float,
        bid_price: float
    ) -> tuple[int, dict]:
        # Serialize once to guarantee identical wire bytes across approval and ingestion
        raw_bytes = json.dumps({
            "source_market": source_market,
            "target_market": target_market,
            "asset_pair": asset_pair,
            "spread_percentage": spread_percentage,
            "ask_price": ask_price,
            "bid_price": bid_price
        }, separators=(",", ":")).encode("utf-8")

        gate_status, gate_resp = self._post_raw("/api/v1/gate/approve", raw_bytes)
        if gate_status != 200:
            return gate_status, gate_resp

        return self._post_raw(
            "/api/v1/ingest/arbitrage",
            raw_bytes,
            extra_headers={
                "X-ETBV-Nonce": gate_resp["nonce"],
                "X-ETBV-HMAC": gate_resp["approval_hmac"]
            }
        )

if __name__ == "__main__":
    client = ETBVClient()
    status, result = client.submit_arbitrage_signal(
        source_market="KRAKEN",
        target_market="GEMINI",
        asset_pair="ETH/USD",
        spread_percentage=0.32,
        ask_price=3120.0,
        bid_price=3130.0
    )
    print(f"[CLIENT SUBMIT] HTTP {status} -> {result}")
