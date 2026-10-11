from collections import deque

from analysis.processor import analyze_all_symbols, compute_statistics


def test_compute_statistics_basic():
    trades = deque(
        [
            {"price": 100.0, "quantity": 1.0, "timestamp": 1},
            {"price": 110.0, "quantity": 2.0, "timestamp": 2},
            {"price": 105.0, "quantity": 1.5, "timestamp": 3},
        ]
    )
    assert compute_statistics(trades) == {
        "price_change_pct": 5.0,
        "avg_price": 105.0,
        "total_volume": 4.5,
        "trade_count": 3,
    }


def test_compute_statistics_empty():
    assert compute_statistics(deque()) == {"price_change_pct": 0, "avg_price": 0, "total_volume": 0, "trade_count": 0}


def test_negative_change_and_rounding():
    trades = deque(
        [{"price": 3.0, "quantity": 0.123456, "timestamp": 1}, {"price": 2.0, "quantity": 1, "timestamp": 2}]
    )
    stats = compute_statistics(trades)
    assert stats["price_change_pct"] == -33.33
    assert stats["total_volume"] == 1.1235


def test_zero_first_price_does_not_divide_by_zero():
    trades = deque([{"price": 0.0, "quantity": 1, "timestamp": 1}, {"price": 5.0, "quantity": 1, "timestamp": 2}])
    assert compute_statistics(trades)["price_change_pct"] == 0


def test_analyze_all_symbols():
    buffers = {"btcusdt": deque([{"price": 1.0, "quantity": 2.0, "timestamp": 1}]), "ethusdt": deque()}
    summary = analyze_all_symbols(buffers)
    assert summary["btcusdt"]["trade_count"] == 1
    assert summary["ethusdt"]["trade_count"] == 0
