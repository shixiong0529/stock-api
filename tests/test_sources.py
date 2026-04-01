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
            {"item": "市盈率(动)", "value": 28.5},
            {"item": "市净率", "value": 10.2},
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


def test_get_flow_hk_returns_unsupported():
    import sources

    result = sources.get_flow("00700.HK")
    assert result.get("error") == "unsupported_market"


def test_get_announcement_hk_returns_unsupported():
    import sources

    result = sources.get_announcement("00700.HK")
    assert result.get("error") == "unsupported_market"
