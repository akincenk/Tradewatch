from unittest.mock import Mock

import requests

from dashboard import app as dashboard


def response(status, payload=None):
    r = Mock(status_code=status)
    r.json.return_value = payload
    r.raise_for_status.side_effect = None if status < 400 else requests.HTTPError(str(status))
    return r


def test_plots_real_recent_prices(monkeypatch):
    summary = {"btcusdt": {"price_change_pct": 1.5, "avg_price": 101.0, "total_volume": 3.0, "trade_count": 3}}
    trades = {"btcusdt": [{"price": p, "quantity": 1, "timestamp": i} for i, p in enumerate([100.0, 101.0, 102.0])]}
    monkeypatch.setattr(dashboard.requests, "get", Mock(side_effect=[response(200, summary), response(200, trades)]))

    stats, fig = dashboard.update_dashboard(0, "btcusdt")
    assert list(fig.data[0].y) == [100.0, 101.0, 102.0]
    assert "last 3 trades" in stats.children[0].children


def test_waiting_message_when_no_data(monkeypatch):
    monkeypatch.setattr(dashboard.requests, "get", Mock(return_value=response(404)))
    stats, fig = dashboard.update_dashboard(0, "btcusdt")
    assert stats == "Waiting for trade data..."
    assert not fig.data


def test_api_unreachable(monkeypatch):
    monkeypatch.setattr(dashboard.requests, "get", Mock(side_effect=requests.ConnectionError("refused")))
    stats, _ = dashboard.update_dashboard(0, "btcusdt")
    assert stats.startswith("Error fetching data")
