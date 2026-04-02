import os
import sys
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_is_hk_with_suffix():
    from sources import is_hk

    assert is_hk("00700.HK") is True


def test_is_hk_without_suffix():
    from sources import is_hk

    assert is_hk("00700") is True


def test_is_hk_rejects_a_share():
    from sources import is_hk

    assert is_hk("600519") is False
    assert is_hk("000001") is False


def test_normalize_strips_suffix():
    from sources import normalize_symbol

    assert normalize_symbol("00700.HK") == "00700"
    assert normalize_symbol("600519") == "600519"


def _make_xq_spot_df(symbol: str, name: str, price: float, change_pct: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"item": "代码", "value": symbol},
            {"item": "名称", "value": name},
            {"item": "现价", "value": price},
            {"item": "涨幅", "value": change_pct},
            {"item": "成交额", "value": 2840000000.0},
            {"item": "市盈率(TTM)", "value": 28.5},
            {"item": "市净率", "value": 10.2},
        ]
    )


def _make_market_spot_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "代码": "600000",
                "名称": "浦发银行",
                "最新价": 10.0,
                "涨跌幅": 1.2,
                "成交量": 1000,
                "成交额": 1000000.0,
            },
            {
                "代码": "600519",
                "名称": "贵州茅台",
                "最新价": 1688.0,
                "涨跌幅": -0.5,
                "成交量": 500,
                "成交额": 2000000.0,
            },
            {
                "代码": "000001",
                "名称": "平安银行",
                "最新价": 12.0,
                "涨跌幅": 0.0,
                "成交量": 800,
                "成交额": 1500000.0,
            },
        ]
    )


def _make_index_spot_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"代码": "sh000001", "名称": "上证指数", "最新价": 3200.0, "涨跌幅": 0.86, "涨跌额": 27.2, "成交额": 450000000000.0},
            {"代码": "sz399001", "名称": "深证成指", "最新价": 10200.0, "涨跌幅": -0.32, "涨跌额": -32.0, "成交额": 520000000000.0},
            {"代码": "sz399006", "名称": "创业板指", "最新价": 2050.0, "涨跌幅": 1.18, "涨跌额": 24.0, "成交额": 120000000000.0},
            {"代码": "sh000300", "名称": "沪深300", "最新价": 3900.0, "涨跌幅": 0.55, "涨跌额": 21.0, "成交额": 320000000000.0},
            {"代码": "sh000688", "名称": "科创50", "最新价": 980.0, "涨跌幅": 2.01, "涨跌额": 19.0, "成交额": 80000000000.0},
        ]
    )


@patch("sources.ak.stock_individual_spot_xq")
def test_get_quote_a_share(mock_spot):
    import sources

    sources._cache.clear("quote:600519")
    mock_spot.return_value = _make_xq_spot_df("SH600519", "贵州茅台", 1688.0, 1.23)

    result = sources.get_quote("600519")

    assert result["price"] == 1688.0
    assert result["name"] == "贵州茅台"
    assert result["change_pct"] == 1.23
    assert "error" not in result


@patch("sources.ak.stock_individual_spot_xq")
def test_get_quote_hk(mock_spot):
    import sources

    sources._cache.clear("quote:00700")
    mock_spot.return_value = _make_xq_spot_df("00700", "腾讯控股", 496.6, 2.6)

    result = sources.get_quote("00700.HK")

    assert result["price"] == 496.6
    assert result["name"] == "腾讯控股"
    assert result["change_pct"] == 2.6


@patch("sources.ak.stock_individual_spot_xq")
def test_get_quote_invalid_symbol(mock_spot):
    import sources

    sources._cache.clear("quote:600519")
    mock_spot.return_value = pd.DataFrame([{"item": "代码", "value": "SH000001"}])

    result = sources.get_quote("600519")

    assert result.get("error") == "invalid_symbol"


@patch("sources.ak.stock_individual_spot_xq")
def test_get_quote_uses_cache(mock_spot):
    import sources

    sources._cache.clear("quote:600519")
    mock_spot.return_value = _make_xq_spot_df("SH600519", "贵州茅台", 1688.0, 1.23)

    sources.get_quote("600519")
    sources.get_quote("600519")

    mock_spot.assert_called_once()


@patch("sources._fetch_sina_index_spot")
@patch("sources._fetch_sina_a_market_spot")
def test_get_market_summary_returns_overview(mock_market_spot, mock_index_spot):
    import sources

    sources._cache.clear("market:summary")
    mock_market_spot.return_value = _make_market_spot_df()
    mock_index_spot.return_value = _make_index_spot_df()

    result = sources.get_market_summary()

    assert result["breadth"] == {"up_count": 1, "down_count": 1, "flat_count": 1, "total": 3}
    assert result["turnover"]["amount"] == 4500000.0
    assert result["turnover"]["volume"] == 2300.0
    assert result["top_gainers"][0]["symbol"] == "600000"
    assert result["top_losers"][0]["symbol"] == "600519"
    assert len(result["indices"]) == 5
    assert result["indices"][0]["name"] == "上证指数"


@patch("sources._fetch_sina_index_spot")
@patch("sources._fetch_sina_a_market_spot")
def test_get_market_summary_uses_cache(mock_market_spot, mock_index_spot):
    import sources

    sources._cache.clear("market:summary")
    mock_market_spot.return_value = _make_market_spot_df()
    mock_index_spot.return_value = _make_index_spot_df()

    sources.get_market_summary()
    sources.get_market_summary()

    mock_market_spot.assert_called_once()
    mock_index_spot.assert_called_once()


@patch("sources._load_market_summary_snapshot")
@patch("sources._fetch_sina_index_spot")
@patch("sources._fetch_sina_a_market_spot")
def test_get_market_summary_falls_back_to_snapshot(mock_market_spot, mock_index_spot, mock_snapshot):
    import sources

    sources._cache.clear("market:summary")
    mock_market_spot.side_effect = RuntimeError("blocked")
    mock_snapshot.return_value = {
        "date": "2026-04-01",
        "breadth": {"up_count": 10, "down_count": 5, "flat_count": 1, "total": 16},
        "turnover": {"amount": 100.0, "volume": 20.0},
        "indices": [],
        "top_gainers": [],
        "top_losers": [],
    }

    result = sources.get_market_summary()

    assert result["stale"] is True
    assert result["stale_reason"] == "blocked"
    assert result["breadth"]["total"] == 16


def test_get_flow_hk_returns_unsupported():
    import sources

    result = sources.get_flow("00700.HK")
    assert result.get("error") == "unsupported_market"


def test_get_announcement_hk_returns_unsupported():
    import sources

    result = sources.get_announcement("00700.HK")
    assert result.get("error") == "unsupported_market"
