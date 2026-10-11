from collections import deque


def compute_statistics(trades: deque) -> dict:
    # Snapshot first: the ingest loop appends to the deque from another thread.
    trades = list(trades)
    if not trades:
        return {"price_change_pct": 0, "avg_price": 0, "total_volume": 0, "trade_count": 0}

    prices = [trade["price"] for trade in trades]
    first_price, last_price = prices[0], prices[-1]
    price_change_pct = ((last_price - first_price) / first_price) * 100 if first_price > 0 else 0

    return {
        "price_change_pct": round(price_change_pct, 2),
        "avg_price": round(sum(prices) / len(prices), 4),
        "total_volume": round(sum(trade["quantity"] for trade in trades), 4),
        "trade_count": len(trades),
    }


def analyze_all_symbols(buffers: dict[str, deque]) -> dict[str, dict]:
    return {symbol: compute_statistics(trades) for symbol, trades in list(buffers.items())}
