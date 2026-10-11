"""Single-command demo: API (with live Binance ingestion) and dashboard in one process."""

import threading

import uvicorn

from api.main import app as api_app
from dashboard.app import app as dash_app

if __name__ == "__main__":
    threading.Thread(
        target=uvicorn.run, args=(api_app,), kwargs={"host": "127.0.0.1", "port": 8000}, daemon=True
    ).start()
    print("Dashboard: http://127.0.0.1:8050  API docs: http://127.0.0.1:8000/docs")
    dash_app.run(host="127.0.0.1", port=8050)
