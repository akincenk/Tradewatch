from fastapi.testclient import TestClient

from api.main import app
from ingest import binance_ws
from tests.conftest import trade_msg

# Not used as a context manager, so the lifespan (live Binance ingestion) never starts.
client = TestClient(app)


def feed(*msgs):
    for m in msgs:
        binance_ws.handle_trade_message(m)


def test_summary_empty():
    assert client.get("/summary").json() == {}


def test_summary_all_and_single_symbol():
    feed(trade_msg("BTCUSDT", "100", "1"), trade_msg("BTCUSDT", "110", "1"), trade_msg("ETHUSDT", "10", "3"))
    all_ = client.get("/summary").json()
    assert set(all_) == {"btcusdt", "ethusdt"}
    assert all_["btcusdt"]["price_change_pct"] == 10.0

    resp = client.get("/summary/BTCUSDT")  # case-insensitive
    assert resp.status_code == 200
    assert resp.json()["btcusdt"]["trade_count"] == 2


def test_unknown_symbol_404_and_does_not_create_buffer():
    assert client.get("/summary/dogeusdt").status_code == 404
    assert client.get("/trades/dogeusdt").status_code == 404
    assert "dogeusdt" not in binance_ws.TRADE_BUFFERS


def test_recent_trades_respects_limit():
    feed(*(trade_msg(price=str(p), ts=p) for p in range(1, 6)))
    resp = client.get("/trades/btcusdt", params={"limit": 2})
    assert [t["price"] for t in resp.json()["btcusdt"]] == [4.0, 5.0]


def test_recent_trades_limit_validation():
    feed(trade_msg())
    assert client.get("/trades/btcusdt", params={"limit": 0}).status_code == 422
    assert client.get("/trades/btcusdt", params={"limit": 1001}).status_code == 422


def test_summary_window_parameter():
    feed(trade_msg(price="100", ts=0), trade_msg(price="200", ts=100_000), trade_msg(price="220", ts=150_000))
    assert client.get("/summary/btcusdt").json()["btcusdt"]["price_change_pct"] == 10.0  # default 60 s
    wide = client.get("/summary/btcusdt", params={"window": 300}).json()["btcusdt"]
    assert wide["price_change_pct"] == 120.0
    assert wide["window_seconds"] == 300
    assert client.get("/summary", params={"window": 0}).status_code == 422
    assert client.get("/summary", params={"window": 301}).status_code == 422


def test_anomalies_endpoint_flags_large_trade():
    feed(*(trade_msg(price="100", qty=str(1 + (i % 5) * 0.1), ts=i * 100) for i in range(100)))
    feed(trade_msg(price="100", qty="40", ts=10_000))
    body = client.get("/anomalies/BTCUSDT").json()["btcusdt"]
    assert [(a["kind"], a["quantity"]) for a in body] == [("size", 40.0)]


def test_anomalies_validation_and_unknown_symbol():
    feed(trade_msg())
    assert client.get("/anomalies/btcusdt", params={"z": 1}).status_code == 422
    assert client.get("/anomalies/dogeusdt").status_code == 404
