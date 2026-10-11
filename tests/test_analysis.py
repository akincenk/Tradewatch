import random
from collections import deque

from analysis.processor import analyze_all_symbols, compute_statistics, detect_anomalies


def t(price, qty=1.0, ts_s=0.0):
    return {"price": price, "quantity": qty, "timestamp": int(ts_s * 1000)}


def test_compute_statistics_basic():
    trades = deque([t(100.0, 1.0, 1), t(110.0, 2.0, 2), t(105.0, 1.5, 3)])
    assert compute_statistics(trades) == {
        "price_change_pct": 5.0,
        "avg_price": 105.0,
        "total_volume": 4.5,
        "trade_count": 3,
        "window_seconds": 60,
        "truncated": False,
    }


def test_compute_statistics_empty():
    assert compute_statistics(deque()) == {
        "price_change_pct": 0,
        "avg_price": 0,
        "total_volume": 0,
        "trade_count": 0,
        "window_seconds": 60,
        "truncated": False,
    }


def test_change_uses_time_window_not_whole_buffer():
    # 100 -> 200 happened long ago; over the last 60 s the price went 200 -> 210.
    trades = deque([t(100.0, ts_s=0), t(200.0, ts_s=50), t(200.0, ts_s=100), t(210.0, ts_s=160)])
    stats = compute_statistics(trades, window_seconds=60)
    assert stats["price_change_pct"] == 5.0
    assert stats["trade_count"] == 2
    assert stats["avg_price"] == 205.0
    # A wider window includes the older trades.
    assert compute_statistics(trades, window_seconds=200)["price_change_pct"] == 110.0


def test_window_boundary_is_inclusive():
    trades = deque([t(100.0, ts_s=0), t(150.0, ts_s=60)])
    assert compute_statistics(trades, window_seconds=60)["trade_count"] == 2
    assert compute_statistics(trades, window_seconds=59)["trade_count"] == 1


def test_truncated_when_bounded_buffer_cannot_cover_window():
    full = deque([t(100.0, ts_s=s) for s in range(10, 13)], maxlen=3)
    assert compute_statistics(full, window_seconds=60)["truncated"] is True
    assert compute_statistics(full, window_seconds=1)["truncated"] is False
    not_full = deque([t(100.0, ts_s=s) for s in range(10, 13)], maxlen=5)
    assert compute_statistics(not_full, window_seconds=60)["truncated"] is False


def test_negative_change_and_rounding():
    trades = deque([t(3.0, 0.123456, 1), t(2.0, 1, 2)])
    stats = compute_statistics(trades)
    assert stats["price_change_pct"] == -33.33
    assert stats["total_volume"] == 1.1235


def test_zero_first_price_does_not_divide_by_zero():
    assert compute_statistics(deque([t(0.0, ts_s=1), t(5.0, ts_s=2)]))["price_change_pct"] == 0


def test_analyze_all_symbols():
    buffers = {"btcusdt": deque([t(1.0, 2.0)]), "ethusdt": deque()}
    summary = analyze_all_symbols(buffers)
    assert summary["btcusdt"]["trade_count"] == 1
    assert summary["ethusdt"]["trade_count"] == 0


def noisy_trades(n, seed=0):
    rng = random.Random(seed)
    trades, price = [], 100.0
    for i in range(n):
        price *= 1 + rng.gauss(0, 0.0001)
        trades.append(t(price, abs(rng.gauss(1.0, 0.2)), ts_s=i * 0.1))
    return trades


def test_normal_activity_is_not_flagged():
    assert detect_anomalies(deque(noisy_trades(500)), window_seconds=60, z_threshold=5) == []


def test_flags_unusually_large_trade():
    trades = noisy_trades(300)
    trades[-10] = {**trades[-10], "quantity": 50.0}
    flagged = detect_anomalies(deque(trades), window_seconds=60)
    assert [(a["kind"], a["timestamp"]) for a in flagged] == [("size", trades[-10]["timestamp"])]
    assert flagged[0]["zscore"] > 10


def test_flags_sudden_price_jump():
    trades = noisy_trades(300)
    jump = trades[-5]["price"] * 1.02
    trades[-5:] = [{**tr, "price": jump} for tr in trades[-5:]]
    flagged = detect_anomalies(deque(trades), window_seconds=60)
    assert [(a["kind"], a["timestamp"]) for a in flagged] == [("price_move", trades[-5]["timestamp"])]


def test_only_trades_inside_window_are_reported():
    trades = noisy_trades(1000)  # 100 s of data
    trades[400] = {**trades[400], "quantity": 50.0}  # at 40 s, outside the last 30 s
    assert detect_anomalies(deque(trades), window_seconds=30) == []
    assert len(detect_anomalies(deque(trades), window_seconds=90)) == 1


def test_needs_enough_history_and_variance():
    # Fewer trades than min_baseline: nothing can be judged unusual.
    assert detect_anomalies(deque([t(100.0, 1.0, 0), t(100.0, 99.0, 1)])) == []
    # Constant history has zero variance; no z-score, no flag.
    flat = [t(100.0, 1.0, i) for i in range(50)]
    assert detect_anomalies(deque(flat)) == []
