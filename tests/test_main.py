import os
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _get_client():
    from main import app

    return TestClient(app)


def test_health_returns_ok():
    response = _get_client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_quote_returns_data():
    mock = {"symbol": "600519", "name": "贵州茅台", "price": 1688.0, "change_pct": 1.23}
    with patch("main.sources.get_quote", return_value=mock):
        response = _get_client().get("/quote?symbol=600519")
    assert response.status_code == 200
    assert response.json()["price"] == 1688.0


def test_quote_missing_symbol_returns_422():
    response = _get_client().get("/quote")
    assert response.status_code == 422


def test_flow_returns_data():
    mock = {"symbol": "600519", "main_net": 320000000}
    with patch("main.sources.get_flow", return_value=mock):
        response = _get_client().get("/flow?symbol=600519")
    assert response.status_code == 200


def test_news_returns_data():
    mock = {"symbol": "600519", "news": [{"title": "茅台新闻"}]}
    with patch("main.sources.get_news", return_value=mock):
        response = _get_client().get("/news?symbol=600519")
    assert response.status_code == 200
    assert response.json()["news"][0]["title"] == "茅台新闻"


def test_intraday_returns_data():
    mock = {"symbol": "600519", "data": [{"day": "2026-04-01 09:30:00", "close": "1688.0"}]}
    with patch("main.sources.get_intraday", return_value=mock):
        response = _get_client().get("/intraday?symbol=600519")
    assert response.status_code == 200


def test_announcement_returns_data():
    mock = {"symbol": "600519", "announcements": [{"公告标题": "年报公告"}]}
    with patch("main.sources.get_announcement", return_value=mock):
        response = _get_client().get("/announcement?symbol=600519")
    assert response.status_code == 200


def test_market_summary_returns_data():
    mock = {
        "date": "2026-04-01",
        "breadth": {"up_count": 3200, "down_count": 1800, "flat_count": 50, "total": 5050},
        "turnover": {"amount": 1234567890.0, "volume": 987654321.0},
        "indices": [{"symbol": "sh000001", "name": "上证指数", "price": 3200.0, "change_pct": 0.86}],
    }
    with patch("main.sources.get_market_summary", return_value=mock):
        response = _get_client().get("/market/summary")
    assert response.status_code == 200
    assert response.json()["breadth"]["up_count"] == 3200
