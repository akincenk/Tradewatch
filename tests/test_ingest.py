import asyncio
import json

import pytest
import websockets

from ingest import binance_ws
from tests.conftest import trade_msg


def test_handle_trade_message_appends_parsed_trade():
    binance_ws.handle_trade_message(trade_msg("ETHUSDT", "2500.1", "0.5", 42))
    assert list(binance_ws.TRADE_BUFFERS["ethusdt"]) == [{"price": 2500.1, "quantity": 0.5, "timestamp": 42}]


@pytest.mark.parametrize(
    "msg",
    [{}, {"data": None}, {"data": {"s": "BTCUSDT"}}, {"data": {"s": "BTCUSDT", "p": "abc", "q": "1"}}, {"data": "x"}],
)
def test_handle_trade_message_skips_malformed(msg):
    binance_ws.handle_trade_message(msg)
    assert not binance_ws.TRADE_BUFFERS


def test_buffer_is_bounded():
    for i in range(binance_ws.BUFFER_SIZE + 5):
        binance_ws.handle_trade_message(trade_msg(ts=i))
    buf = binance_ws.TRADE_BUFFERS["btcusdt"]
    assert len(buf) == binance_ws.BUFFER_SIZE
    assert buf[0]["timestamp"] == 5


def test_stream_url_subscribes_to_all_coins():
    for coin in binance_ws.COINS:
        assert f"{coin}@trade" in binance_ws.STREAM_URL


class FakeSocket:
    def __init__(self, messages):
        self.messages = messages

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for m in self.messages:
            yield m


def test_listener_consumes_messages_and_reconnects(monkeypatch):
    """No network: websockets.connect is replaced by a scripted fake."""
    attempts = []

    def fake_connect(url):
        attempts.append(url)
        if len(attempts) == 1:
            raise OSError("connection refused")
        if len(attempts) == 2:
            return FakeSocket([json.dumps(trade_msg(price="1")), "not json", json.dumps(trade_msg(price="2"))])
        raise asyncio.CancelledError  # stop the infinite loop

    async def no_sleep(_):
        pass

    monkeypatch.setattr(websockets, "connect", fake_connect)
    monkeypatch.setattr(binance_ws.asyncio, "sleep", no_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(binance_ws.binance_ws_listener("wss://example.invalid"))

    assert attempts == ["wss://example.invalid"] * 3
    assert [t["price"] for t in binance_ws.TRADE_BUFFERS["btcusdt"]] == [1.0, 2.0]
