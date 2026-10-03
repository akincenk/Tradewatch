
import asyncio
import threading
from collections import defaultdict, deque
from fastapi import FastAPI, HTTPException
import uvicorn
import ssl
import websockets
import json
from dash import Dash, dcc, html, Input, Output
import plotly.graph_objs as go
import requests

# ==== SHARED STATE ====
TRADE_BUFFERS = defaultdict(lambda: deque(maxlen=1000))
SYMBOLS = ['btcusdt', 'ethusdt', 'bnbusdt', 'solusdt', 'xrpusdt', 'lrcusdt']

# ==== INGEST ====
async def handle_trade_message(msg):
    data = msg.get("data")
    if not data:
        return
    symbol = data.get("s", "").lower()
    trade = {
        "price": float(data.get("p", 0)),
        "quantity": float(data.get("q", 0)),
        "timestamp": data.get("T")
    }
    TRADE_BUFFERS[symbol].append(trade)
    print(f"[{symbol}] Price: {trade['price']}, Qty: {trade['quantity']}")

async def binance_ws_listener():
    stream_names = [f"{symbol}@trade" for symbol in SYMBOLS]
    url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(stream_names)}"
    ssl_context = ssl._create_unverified_context()

    async with websockets.connect(url, ssl=ssl_context) as ws:
        print("Connected to Binance WebSocket")
        while True:
            try:
                msg = await ws.recv()
                msg = json.loads(msg)
                await handle_trade_message(msg)
            except Exception as e:
                print(f"WebSocket error: {e}")

def start_ws():
    asyncio.run(binance_ws_listener())

# ==== API ====
app = FastAPI()

def compute_summary(trades):
    if not trades:
        return {}
    prices = [t["price"] for t in trades]
    volumes = [t["quantity"] for t in trades]
    avg_price = sum(prices) / len(prices)
    total_volume = sum(volumes)
    price_change = ((prices[-1] - prices[0]) / prices[0]) * 100 if prices[0] else 0
    return {
        "price_change_pct": round(price_change, 3),
        "avg_price": round(avg_price, 4),
        "total_volume": round(total_volume, 3),
        "trade_count": len(trades)
    }

@app.get("/summary")
def get_all_summaries():
    return {sym: compute_summary(trades) for sym, trades in TRADE_BUFFERS.items()}

@app.get("/summary/{symbol}")
def get_summary_for_symbol(symbol: str):
    symbol = symbol.lower()
    if symbol not in TRADE_BUFFERS:
        raise HTTPException(status_code=404, detail="Symbol not found or no data yet.")
    return {symbol: compute_summary(TRADE_BUFFERS[symbol])}

def run_api():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

# ==== DASH ====
def run_dash():
    dash_app = Dash(__name__)
    dash_app.title = "TradeWatch"

    dash_app.layout = html.Div([
        html.H1("📈 TradeWatch - Live Market Monitor"),
        dcc.Dropdown(
            id='symbol-dropdown',
            options=[{'label': sym.upper(), 'value': sym} for sym in SYMBOLS],
            value='btcusdt'
        ),
        html.Div(id='stats-output'),
        dcc.Graph(id='price-graph', config={'displayModeBar': False}),
        dcc.Interval(id='interval-component', interval=5000, n_intervals=0)
    ])

    @dash_app.callback(
        Output('stats-output', 'children'),
        Output('price-graph', 'figure'),
        Input('interval-component', 'n_intervals'),
        Input('symbol-dropdown', 'value')
    )
    def update_dashboard(n, symbol):
        try:
            response = requests.get(f"http://127.0.0.1:8000/summary/{symbol}")
            if response.status_code != 200:
                return html.P("⏳ Loading live trade data... Please wait."), go.Figure()

            data = response.json()[symbol]
            prices = [data['avg_price']] * 20

            stats = html.Div([
                html.H3(f"{symbol.upper()} Summary"),
                html.P(f"% Change: {data['price_change_pct']}%"),
                html.P(f"Avg Price: {data['avg_price']}$"),
                html.P(f"Total Volume: {data['total_volume']}")
            ])

            fig = go.Figure()
            fig.add_trace(go.Scatter(y=prices, mode='lines+markers', name='Price'))
            fig.update_layout(title=f"Live Avg Price - {symbol.upper()}", xaxis_title='Time', yaxis_title='Price')

            return stats, fig

        except Exception as e:
            return f"Error fetching data: {e}", go.Figure()

    dash_app.run(debug=True, use_reloader=False)

# ==== RUN ====
if __name__ == "__main__":
    threading.Thread(target=start_ws, daemon=True).start()
    threading.Thread(target=run_api, daemon=True).start()
    import webbrowser; webbrowser.open("http://127.0.0.1:8050")
    run_dash()
