import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from analysis.processor import analyze_all_symbols, compute_statistics
from ingest.binance_ws import binance_ws_listener, get_trade_buffers


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


@app.get("/summary")
def get_all_summaries():
    return analyze_all_symbols(get_trade_buffers())


@app.get("/summary/{symbol}")
def get_summary_for_symbol(symbol: str):
    symbol, trades = _buffer(symbol)
    return {symbol: compute_statistics(trades)}


@app.get("/trades/{symbol}")
def get_recent_trades(symbol: str, limit: int = Query(100, ge=1, le=1000)):
    symbol, trades = _buffer(symbol)
    return {symbol: list(trades)[-limit:]}
