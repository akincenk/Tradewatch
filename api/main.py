import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from analysis.processor import DEFAULT_WINDOW_SECONDS, analyze_all_symbols, compute_statistics, detect_anomalies
from ingest.binance_ws import RETENTION_SECONDS, binance_ws_listener, get_trade_buffers


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Run ingestion inside the API process so the endpoints serve live data.
    task = asyncio.create_task(binance_ws_listener())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="TradeWatch API", lifespan=lifespan)


def _buffer(symbol: str):
    buffers = get_trade_buffers()
    symbol = symbol.lower()
    if symbol not in buffers:  # membership check only; never create empty buffers here
        raise HTTPException(status_code=404, detail="Symbol not found or no data yet.")
    return symbol, buffers[symbol]


WindowQuery = Query(DEFAULT_WINDOW_SECONDS, ge=1, le=RETENTION_SECONDS, description="Window length in seconds")


@app.get("/summary")
def get_all_summaries(window: int = WindowQuery):
    return analyze_all_symbols(get_trade_buffers(), window)


@app.get("/summary/{symbol}")
def get_summary_for_symbol(symbol: str, window: int = WindowQuery):
    symbol, trades = _buffer(symbol)
    return {symbol: compute_statistics(trades, window)}


@app.get("/trades/{symbol}")
def get_recent_trades(symbol: str, limit: int = Query(100, ge=1, le=1000)):
    symbol, trades = _buffer(symbol)
    return {symbol: list(trades)[-limit:]}


@app.get("/anomalies/{symbol}")
def get_anomalies(symbol: str, window: int = WindowQuery, z: float = Query(4.0, ge=2.0, le=20.0)):
    symbol, trades = _buffer(symbol)
    return {symbol: detect_anomalies(trades, window_seconds=window, z_threshold=z)}
