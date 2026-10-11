# TradeWatch

[![CI](https://github.com/akincenk/Tradewatch/actions/workflows/ci.yml/badge.svg)](https://github.com/akincenk/Tradewatch/actions/workflows/ci.yml)

Live crypto trade monitor: streams trades from the Binance public WebSocket, keeps the last few minutes of trades per symbol in memory, computes time-window stats, flags unusual activity with a rolling z-score, and serves it all through a FastAPI API and a Plotly Dash dashboard.

## What it does

- Subscribes to the Binance combined trade stream for BTC, ETH, BNB, SOL, XRP and LRC (USDT pairs). No API key needed.
- Keeps the last 5 minutes of trades per symbol in a `deque` (by Binance trade time), capped at 20,000 trades per symbol to bound memory.
- Computes per-symbol stats over a time window (default the last 60 seconds, configurable per request up to 300): price change %, average price, total volume, trade count.
- Flags unusual activity: a trade is flagged when its size, or its price move from the previous trade, is at least `z` standard deviations (default 4) away from the previous 200 trades of that symbol.
- Exposes the stats, anomalies and recent trades over HTTP, and the dashboard plots recent trade prices with a 5-second refresh.
- Reconnects with exponential backoff (1s up to 30s) if the stream drops, and skips malformed messages.

## Architecture

```
Binance WS ──> ingest/binance_ws.py ──> in-memory buffers ──> api/main.py (FastAPI) ──HTTP──> dashboard/app.py (Dash)
                                              │
                                   analysis/processor.py (stats)
```

- `ingest/binance_ws.py`: WebSocket client, message parsing, trade buffers.
- `analysis/processor.py`: pure functions for the time-window stats and anomaly detection.
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

### Docker

```bash
docker compose up --build
```

This runs the API (with ingestion) and the dashboard as two containers from one non-root image, published on `127.0.0.1:8000` and `127.0.0.1:8050` only. To run only the API: `docker build -t tradewatch . && docker run --rm -p 127.0.0.1:8000:8000 tradewatch`.

### Running the parts separately

```bash
uvicorn api.main:app --port 8000      # API + live ingestion
python -m dashboard.app               # dashboard on :8050
```

## Configuration

Nothing is required. Optional environment variables:

- `TRADEWATCH_API` (default `http://127.0.0.1:8000`): the API base URL the dashboard polls.
- `DASH_HOST` (default `127.0.0.1`): interface the dashboard binds to when run with `python -m dashboard.app` (Docker sets `0.0.0.0` inside the container).
- `DASH_DEBUG=1`: turns on Dash debug mode for `python -m dashboard.app`. Never enable it on a reachable host.

There is no `.env` file because the app needs no secrets: the Binance trade stream is public.

## API

All endpoints are read-only `GET`s.

- `GET /summary?window=60`: stats for every symbol that has received trades. `window` is in seconds, 1 to 300.
- `GET /summary/{symbol}?window=60`: stats for one symbol (case-insensitive). Returns `404` until trades arrive.
- `GET /anomalies/{symbol}?window=60&z=4`: flagged trades in the window, each with `kind` (`size` or `price_move`) and `zscore`. `z` from 2 to 20.
- `GET /trades/{symbol}?limit=100`: the most recent trades, `limit` from 1 to 1000.

```json
{"btcusdt": {"price_change_pct": 0.12, "avg_price": 82988.95, "total_volume": 0.0767, "trade_count": 12, "window_seconds": 60, "truncated": false}}
```

The window ends at the symbol's most recent trade. `truncated: true` means the 20,000-trade cap was reached before the window was covered, so the stats describe a shorter period than requested.

```json
{"ethusdt": [{"price": 2502.88, "quantity": 5.7603, "timestamp": 1791705062644, "kind": "size", "zscore": 6.43}]}
```

## Tests

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

The tests never touch the network, and any warning fails the run. The stats tests check that the % change follows the time window rather than the whole buffer, and the anomaly tests inject a large trade and a price jump into seeded random trade streams and check that exactly those trades are flagged. `websockets.connect` is replaced with a scripted fake to cover message parsing, reconnects and bad input, the API is tested with FastAPI's `TestClient` without starting the lifespan, and the dashboard callback runs against a mocked `requests.get`. CI runs ruff, `pip-audit` and pytest on Python 3.11 and 3.12, and builds the Docker image. Dependabot opens weekly update PRs for pip packages and GitHub Actions.

## Limitations and next steps

- All state is in memory in one process: it resets on restart, and the API cannot run with multiple workers. Fixing either would need an external shared store, which this project deliberately does not have.
- Windows are limited to the 5-minute retention, and very busy symbols can hit the 20,000-trade cap sooner (reported as `truncated`).
- Anomaly detection is a simple z-score against the previous 200 trades. Trade sizes and returns are heavy-tailed, so expect some false positives. Results are recomputed on each request and only available through the API; nothing sends notifications.
- The symbol list is hardcoded in `ingest/binance_ws.py`.
- Binance's public stream is not available in every region.

## Design decisions

- **Time windows anchored on trade time.** Windows end at the newest trade's Binance timestamp instead of the local clock, so results are deterministic and unaffected by clock skew.
- **O(n) anomaly scoring.** Rolling mean and variance come from running sums over the previous 200 trades, so scoring a 20,000-trade buffer per request stays cheap. Price returns are scored in basis points to keep the sums numerically stable.
- **No database or cache.** State is a few in-memory deques owned by the API process; that keeps the service to one process with no infrastructure, at the cost of the limitations above.
- **Sync handlers.** The endpoints are plain `def` and do only small in-memory computations, so they never block the event loop that runs ingestion.

## Security

- The API is read-only and serves public market data, so it has no authentication. Do not expose it to the internet as-is if that matters to you; the Docker setup publishes ports on `127.0.0.1` only.
- Query parameters are range-validated, and unknown symbols return `404` without allocating buffers, so requests cannot grow memory.
- Inbound stream messages are parsed defensively; malformed ones are logged and skipped.
- The Docker image runs as a non-root user. No secrets are needed or stored.

## License

MIT
