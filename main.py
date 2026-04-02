import os

from fastapi import FastAPI, Query

import sources


def _clear_proxy_env() -> None:
    for key in [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]:
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"


_clear_proxy_env()

app = FastAPI(title="Stock API", version="1.1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/quote")
def quote(symbol: str = Query(..., description="Stock symbol, for example 600519 or 00700.HK")):
    return sources.get_quote(symbol)


@app.get("/intraday")
def intraday(symbol: str = Query(..., description="Stock symbol")):
    return sources.get_intraday(symbol)


@app.get("/flow")
def flow(symbol: str = Query(..., description="Stock symbol")):
    return sources.get_flow(symbol)


@app.get("/news")
def news(symbol: str = Query(..., description="Stock symbol")):
    return sources.get_news(symbol)


@app.get("/announcement")
def announcement(symbol: str = Query(..., description="Stock symbol")):
    return sources.get_announcement(symbol)


@app.get("/get")
def get_announcement(symbol: str = Query(..., description="Stock symbol")):
    return sources.get_announcement(symbol)


@app.get("/market/summary")
def market_summary():
    return sources.get_market_summary()
