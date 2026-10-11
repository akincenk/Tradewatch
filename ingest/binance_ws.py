import asyncio
import json
import logging
from collections import defaultdict, deque

import websockets

log = logging.getLogger(__name__)

COINS = ["btcusdt", "ethusdt", "bnbusdt", "solusdt", "xrpusdt", "lrcusdt"]
STREAM_URL = "wss://stream.binance.com:9443/stream?streams=" + "/".join(f"{coin}@trade" for coin in COINS)
BUFFER_SIZE = 1000
TRADE_BUFFERS: defaultdict[str, deque] = defaultdict(lambda: deque(maxlen=BUFFER_SIZE))


def get_trade_buffers():
    return TRADE_BUFFERS


def handle_trade_message(msg: dict) -> None:
    """Parse one combined-stream trade event and append it to its symbol buffer."""
    data = msg.get("data") or {}
    try:
        symbol = data["s"].lower()
        trade = {"price": float(data["p"]), "quantity": float(data["q"]), "timestamp": data.get("T")}
    except (KeyError, TypeError, ValueError, AttributeError):
        log.warning("Skipping malformed message: %r", msg)
        return
    TRADE_BUFFERS[symbol].append(trade)


async def binance_ws_listener(url: str = STREAM_URL, max_backoff: float = 30.0) -> None:
    """Consume the Binance trade stream forever, reconnecting with exponential backoff."""
    backoff = 1.0
    while True:
        try:
            async with websockets.connect(url) as ws:
                log.info("Connected to Binance WebSocket")
                backoff = 1.0
                async for message in ws:
                    try:
                        handle_trade_message(json.loads(message))
                    except json.JSONDecodeError:
                        log.warning("Skipping non-JSON message")
        except (OSError, websockets.exceptions.WebSocketException) as exc:
            log.warning("WebSocket disconnected (%s); reconnecting in %.0fs", exc, backoff)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(binance_ws_listener())
    except KeyboardInterrupt:
        pass
