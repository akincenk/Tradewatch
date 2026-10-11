import math
from collections import deque

DEFAULT_WINDOW_SECONDS = 60
EMPTY_STATS = {"price_change_pct": 0, "avg_price": 0, "total_volume": 0, "trade_count": 0}


def trades_in_window(trades: list[dict], window_seconds: float) -> list[dict]:
    """Trades within `window_seconds` of the most recent trade (Binance trade time, ms).

    The window is anchored on the newest trade rather than the local clock, so results
    do not depend on clock skew between this machine and Binance.
    """
    if not trades:
        return []
    start = trades[-1]["timestamp"] - window_seconds * 1000
    return [t for t in trades if t["timestamp"] >= start]


def compute_statistics(trades: deque, window_seconds: float = DEFAULT_WINDOW_SECONDS) -> dict:
    # Snapshot first: the ingest loop appends to the deque while API threads read it.
    snapshot = list(trades)
    window = trades_in_window(snapshot, window_seconds)
    if not window:
        return {**EMPTY_STATS, "window_seconds": window_seconds, "truncated": False}
    # A full bounded buffer whose oldest trade is still inside the window means older
    # trades in the window were already discarded, so the stats cover less than asked.
    truncated = len(snapshot) == getattr(trades, "maxlen", None) and window[0] is snapshot[0]

    prices = [trade["price"] for trade in window]
    first_price, last_price = prices[0], prices[-1]
    price_change_pct = ((last_price - first_price) / first_price) * 100 if first_price > 0 else 0

    return {
        "price_change_pct": round(price_change_pct, 2),
        "avg_price": round(sum(prices) / len(prices), 4),
        "total_volume": round(sum(trade["quantity"] for trade in window), 4),
        "trade_count": len(window),
        "window_seconds": window_seconds,
        "truncated": truncated,
    }


def analyze_all_symbols(buffers: dict[str, deque], window_seconds: float = DEFAULT_WINDOW_SECONDS) -> dict[str, dict]:
    return {symbol: compute_statistics(trades, window_seconds) for symbol, trades in list(buffers.items())}


def _rolling_zscores(values: list[float], baseline: int, min_baseline: int) -> list[float | None]:
    """z-score of each value against the `baseline` values before it (the value itself excluded).

    None when there is not enough history yet or the history has zero variance.
    Uses running sums, so the whole series is scored in O(n).
    """
    scores: list[float | None] = []
    total = total_sq = 0.0
    for i, value in enumerate(values):
        n = min(i, baseline)
        score = None
        if n >= min_baseline:
            mean = total / n
            var = total_sq / n - mean * mean
            if var > 1e-12:
                score = (value - mean) / math.sqrt(var)
        scores.append(score)
        total += value
        total_sq += value * value
        if i >= baseline:
            old = values[i - baseline]
            total -= old
            total_sq -= old * old
    return scores


def detect_anomalies(
    trades: deque,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
    z_threshold: float = 4.0,
    baseline: int = 200,
    min_baseline: int = 30,
) -> list[dict]:
    """Flag trades in the window whose size or price move is unusual for the symbol.

    Each trade is compared with the `baseline` trades immediately before it:
    - "size": trade quantity has z-score >= z_threshold (unusually large trade).
    - "price_move": price return from the previous trade has |z-score| >= z_threshold.
    """
    trades = list(trades)
    if len(trades) < 2:
        return []
    window_start = trades[-1]["timestamp"] - window_seconds * 1000

    size_z = _rolling_zscores([t["quantity"] for t in trades], baseline, min_baseline)
    # Returns in basis points keep the running sums well away from float precision limits.
    returns = [
        (cur["price"] - prev["price"]) / prev["price"] * 10_000 if prev["price"] > 0 else 0.0
        for prev, cur in zip(trades, trades[1:], strict=False)
    ]
    move_z = [None, *_rolling_zscores(returns, baseline, min_baseline)]  # aligned with trades

    flagged = []
    for trade, sz, mz in zip(trades, size_z, move_z, strict=True):
        if trade["timestamp"] < window_start:
            continue
        if sz is not None and sz >= z_threshold:
            flagged.append({**trade, "kind": "size", "zscore": round(sz, 2)})
        if mz is not None and abs(mz) >= z_threshold:
            flagged.append({**trade, "kind": "price_move", "zscore": round(mz, 2)})
    return flagged
