# TradeWatch

[![CI](https://github.com/akincenk/Tradewatch/actions/workflows/ci.yml/badge.svg)](https://github.com/akincenk/Tradewatch/actions/workflows/ci.yml)

Live crypto trade monitor: streams trades from the Binance public WebSocket, keeps a rolling window per symbol in memory, and serves summary stats through a FastAPI API and a Plotly Dash dashboard.

## What it does

- Subscribes to the Binance combined trade stream for BTC, ETH, BNB, SOL, XRP and LRC (USDT pairs). No API key needed.
- Keeps the last 1,000 trades per symbol in a bounded `deque`.
- Computes per-symbol stats over that window: price change %, average price, total volume, trade count.
- Exposes the stats and recent trades over HTTP, and the dashboard plots recent trade prices with a 5-second refresh.
- Reconnects with exponential backoff (1s up to 30s) if the stream drops, and skips malformed messages.

## Architecture

```
Binance WS ──> ingest/binance_ws.py ──> in-memory buffers ──> api/main.py (FastAPI) ──HTTP──> dashboard/app.py (Dash)
                                              │
                                   analysis/processor.py (stats)
```

- `ingest/binance_ws.py`: WebSocket client, message parsing, trade buffers.
- `analysis/processor.py`: pure functions that compute the stats.
- `api/main.py`: FastAPI app. Its lifespan starts the ingest listener as a background task, so the API process owns the live data.
- `dashboard/app.py`: Dash UI that polls the API.
- `monolith.py`: convenience entrypoint that runs the API (with ingestion) and the dashboard in one process. It only wires up the modules above and has no logic of its own.

Stack: Python 3.11+, FastAPI, Uvicorn, websockets, Dash/Plotly, requests. The stats use plain Python; there is no Pandas or NumPy.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python monolith.py
```

Then open the dashboard at http://127.0.0.1:8050 and the API docs at http://127.0.0.1:8000/docs. Data appears within a few seconds of startup.

To run the parts separately:

```bash
uvicorn api.main:app --port 8000      # API + live ingestion
python -m dashboard.app               # dashboard on :8050
```

## Configuration

Nothing is required. Optional environment variables:

- `TRADEWATCH_API` (default `http://127.0.0.1:8000`): the API base URL the dashboard polls.
- `DASH_DEBUG=1`: turns on Dash debug mode for `python -m dashboard.app`.

## API

- `GET /summary`: stats for every symbol that has received trades.
- `GET /summary/{symbol}`: stats for one symbol (case-insensitive). Returns `404` until trades arrive.
- `GET /trades/{symbol}?limit=100`: the most recent trades, `limit` from 1 to 1000.

```json
{"btcusdt": {"price_change_pct": 0.12, "avg_price": 82988.95, "total_volume": 0.0767, "trade_count": 12}}
```

## Tests

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

The tests never touch the network. `websockets.connect` is replaced with a scripted fake to cover message parsing, reconnects and bad input, the API is tested with FastAPI's `TestClient` without starting the lifespan, and the dashboard callback runs against a mocked `requests.get`. CI runs on Python 3.11 and 3.12.

## Limitations and next steps

- All state is in memory in one process: it resets on restart, and the API cannot run with multiple workers. A shared store such as Redis would fix both.
- Stats cover only the rolling 1,000-trade window, not time-based windows (for example the last 5 minutes).
- There is no alerting or anomaly detection yet. Threshold alerts on `price_change_pct` would be a natural next step.
- The symbol list is hardcoded in `ingest/binance_ws.py`.
- Binance's public stream is not available in every region.

## License

MIT
