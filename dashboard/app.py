import os

import plotly.graph_objs as go
import requests
from dash import Dash, Input, Output, dcc, html

from ingest.binance_ws import COINS

API_BASE = os.getenv("TRADEWATCH_API", "http://127.0.0.1:8000")

app = Dash(__name__)
app.title = "TradeWatch Dashboard"

app.layout = html.Div(
    [
        html.H1("TradeWatch - Live Market Monitor"),
        dcc.Dropdown(
            id="symbol-dropdown",
            options=[{"label": sym.upper(), "value": sym} for sym in COINS],
            value="btcusdt",
        ),
        html.Div(id="stats-output"),
        dcc.Graph(id="price-graph", config={"displayModeBar": False}),
        dcc.Interval(id="interval-component", interval=5000, n_intervals=0),
    ]
)


@app.callback(
    Output("stats-output", "children"),
    Output("price-graph", "figure"),
    Input("interval-component", "n_intervals"),
    Input("symbol-dropdown", "value"),
)
def update_dashboard(_n, symbol):
    try:
        summary = requests.get(f"{API_BASE}/summary/{symbol}", timeout=3)
        if summary.status_code == 404:
            return "Waiting for trade data...", go.Figure()
        summary.raise_for_status()
        trades = requests.get(f"{API_BASE}/trades/{symbol}", params={"limit": 200}, timeout=3)
        trades.raise_for_status()
    except requests.RequestException as exc:
        return f"Error fetching data: {exc}", go.Figure()

    data = summary.json()[symbol]
    recent = trades.json()[symbol]
    stats = html.Div(
        [
            html.H3(f"{symbol.upper()} summary (last {data['trade_count']} trades)"),
            html.P(f"Change: {data['price_change_pct']}%"),
            html.P(f"Average price: {data['avg_price']}"),
            html.P(f"Total volume: {data['total_volume']}"),
        ]
    )
    fig = go.Figure(go.Scatter(y=[t["price"] for t in recent], mode="lines", name="Price"))
    fig.update_layout(title=f"Recent trade prices - {symbol.upper()}", xaxis_title="Trade", yaxis_title="Price")
    return stats, fig


if __name__ == "__main__":
    app.run(debug=os.getenv("DASH_DEBUG") == "1")
