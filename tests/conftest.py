import pytest

from ingest import binance_ws


@pytest.fixture(autouse=True)
def clean_buffers():
    binance_ws.TRADE_BUFFERS.clear()
    yield
    binance_ws.TRADE_BUFFERS.clear()


def trade_msg(symbol="BTCUSDT", price="100.5", qty="0.2", ts=1):
    return {"stream": f"{symbol.lower()}@trade", "data": {"s": symbol, "p": price, "q": qty, "T": ts}}
