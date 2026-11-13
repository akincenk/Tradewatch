# Roadmap

Work I plan to do next, roughly in this order. Each item has an issue in the tracker.
Estimates are rough and include tests and docs.

## 1. Configurable symbols (about 3 h)

- Symbol list from an environment variable instead of the hardcoded list in `ingest/binance_ws.py`.
- `GET /symbols` endpoint; the dashboard builds its dropdown from it.

## 2. Alerts (about 5 h)

- Optional webhook URL: post flagged trades as they are detected, with a cooldown per symbol.
- Price threshold alerts per symbol (above / below a level).

## 3. Candles and longer history (about 6 h)

- Aggregate trades into 1-minute OHLCV candles kept for a few hours.
- Candle chart and volume bars in the dashboard; `GET /candles/{symbol}`.

## 4. Live push to the dashboard (about 4 h)

- Server-sent events or a WebSocket endpoint for new trades and anomalies, so the dashboard does not poll every 5 seconds.

## 5. Optional persistence (about 5 h)

- Snapshot candles to a local SQLite file so a restart does not lose history. Off by default.

## 6. Housekeeping (about 2 h)

- Health endpoint with stream status and last message time.
- Tag a first release (`v0.1.0`) with a changelog.
