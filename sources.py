import json
from datetime import datetime, timedelta
from typing import Any

import akshare as ak
import pandas as pd
import pytz
from curl_cffi import requests as curl_requests

from cache import Cache

_cache = Cache()


def is_hk(symbol: str) -> bool:
    value = normalize_symbol(symbol)
    return len(value) == 5 and value.isdigit()


def normalize_symbol(symbol: str) -> str:
    return symbol.upper().removesuffix(".HK")


def _a_market(symbol: str) -> str:
    return "sh" if symbol.startswith(("6", "9")) else "sz"


def _xq_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if is_hk(symbol):
        return normalized
    prefix = "SH" if normalized.startswith(("6", "9")) else "SZ"
    return f"{prefix}{normalized}"


def _safe_item(df: pd.DataFrame, item: str) -> Any | None:
    row = df[df["item"] == item]
    if row.empty:
        return None
    value = row.iloc[0]["value"]
    if pd.isna(value):
        return None
    return value


def get_quote(symbol: str) -> dict[str, Any]:
    normalized = normalize_symbol(symbol)
    cache_key = f"quote:{normalized}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = ak.stock_individual_spot_xq(symbol=_xq_symbol(symbol))
    except Exception as exc:
        return {"error": "data_unavailable", "message": str(exc), "symbol": symbol}

    if df.empty:
        return {"error": "invalid_symbol", "symbol": symbol}

    actual_code = str(_safe_item(df, "代码") or "")
    if normalized not in actual_code:
        return {"error": "invalid_symbol", "symbol": symbol}

    result = {
        "symbol": symbol,
        "name": _safe_item(df, "名称") or "",
        "price": _safe_number(_safe_item(df, "现价")),
        "change_pct": _safe_number(_safe_item(df, "涨幅")),
        "volume": _safe_number(_safe_item(df, "成交额")),
        "pe": _safe_number(_safe_item(df, "市盈率(动)")),
        "pb": _safe_number(_safe_item(df, "市净率")),
        "trading": _is_trading_now(),
    }
    _cache.set(cache_key, result, ttl=60)
    return result


def get_intraday(symbol: str) -> dict[str, Any]:
    normalized = normalize_symbol(symbol)
    cache_key = f"intraday:{normalized}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        if is_hk(symbol):
            df = ak.stock_hk_hist_min_em(symbol=normalized, period="1", adjust="")
        else:
            df = ak.stock_zh_a_minute(symbol=_xq_symbol(symbol).lower())
    except Exception as exc:
        return {"error": "data_unavailable", "message": str(exc), "symbol": symbol}

    result = {"symbol": symbol, "data": df.to_dict(orient="records")}
    _cache.set(cache_key, result, ttl=30)
    return result


def get_flow(symbol: str) -> dict[str, Any]:
    if is_hk(symbol):
        return {
            "error": "unsupported_market",
            "message": "港股暂不支持资金流向查询",
            "symbol": symbol,
        }

    normalized = normalize_symbol(symbol)
    cache_key = f"flow:{normalized}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = ak.stock_individual_fund_flow(stock=normalized, market=_a_market(normalized))
    except Exception as exc:
        return {"error": "data_unavailable", "message": str(exc), "symbol": symbol}

    if df.empty:
        return {"error": "data_unavailable", "message": "无资金流数据", "symbol": symbol}

    row = df.iloc[-1]
    result = {
        "symbol": symbol,
        "date": str(row.get("日期", "")),
        "main_net": _safe_number(row.get("主力净流入-净额")),
        "main_net_pct": _safe_number(row.get("主力净流入-净占比")),
        "super_large_net": _safe_number(row.get("超大单净流入-净额")),
        "large_net": _safe_number(row.get("大单净流入-净额")),
        "retail_net": _safe_number(row.get("小单净流入-净额")),
    }
    _cache.set(cache_key, result, ttl=60)
    return result


def get_news(symbol: str) -> dict[str, Any]:
    normalized = normalize_symbol(symbol)
    cache_key = f"news:{normalized}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        infer_string = pd.options.future.infer_string
        pd.options.future.infer_string = False
        try:
            df = ak.stock_news_em(symbol=normalized)
        finally:
            pd.options.future.infer_string = infer_string
    except Exception:
        try:
            df = _fallback_news(normalized)
        except Exception as exc:
            return {"error": "data_unavailable", "message": str(exc), "symbol": symbol}

    result = {"symbol": symbol, "news": df.head(10).to_dict(orient="records")}
    _cache.set(cache_key, result, ttl=300)
    return result


def get_announcement(symbol: str) -> dict[str, Any]:
    if is_hk(symbol):
        return {
            "error": "unsupported_market",
            "message": "港股暂不支持公告查询",
            "symbol": symbol,
        }

    normalized = normalize_symbol(symbol)
    cache_key = f"announcement:{normalized}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    end = datetime.today().strftime("%Y%m%d")
    start = (datetime.today() - timedelta(days=30)).strftime("%Y%m%d")
    try:
        df = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=normalized,
            market="\u6caa\u6df1\u4eac",
            start_date=start,
            end_date=end,
        )
    except Exception as exc:
        return {"error": "data_unavailable", "message": str(exc), "symbol": symbol}

    result = {"symbol": symbol, "announcements": df.head(5).to_dict(orient="records")}
    _cache.set(cache_key, result, ttl=300)
    return result


def _fallback_news(symbol: str) -> pd.DataFrame:
    url = "https://search-api-web.eastmoney.com/search/jsonp"
    inner_param = {
        "uid": "",
        "keyword": symbol,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": 1,
                "pageSize": 10,
                "preTag": "<em>",
                "postTag": "</em>",
            }
        },
    }
    params = {
        "cb": "jQuery35101792940631092459_1764599530165",
        "param": json.dumps(inner_param, ensure_ascii=False),
        "_": "1764599530176",
    }
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "referer": f"https://so.eastmoney.com/news/s?keyword={symbol}",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/142.0.0.0 Safari/537.36"
        ),
    }
    response = curl_requests.get(url, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    data = json.loads(response.text.split("(", 1)[1].rsplit(")", 1)[0])
    df = pd.DataFrame(data["result"]["cmsArticleWebOld"])
    if df.empty:
        return pd.DataFrame(columns=["关键词", "新闻标题", "新闻内容", "发布时间", "文章来源", "新闻链接"])

    df["新闻链接"] = "http://finance.eastmoney.com/a/" + df["code"] + ".html"
    df = df.rename(
        columns={
            "title": "新闻标题",
            "content": "新闻内容",
            "date": "发布时间",
            "mediaName": "文章来源",
        }
    )
    df["关键词"] = symbol
    for col in ["新闻标题", "新闻内容"]:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace("<em>", "", regex=False)
            .str.replace("</em>", "", regex=False)
            .str.replace("\\u3000", "", regex=False)
            .str.replace("\\r\\n", " ", regex=False)
        )
    return df[["关键词", "新闻标题", "新闻内容", "发布时间", "文章来源", "新闻链接"]]


def _safe_number(value: Any) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return number


def _is_trading_now() -> bool:
    now = datetime.now(pytz.timezone("Asia/Shanghai"))
    if now.weekday() >= 5:
        return False

    hhmm = now.hour * 100 + now.minute
    if 930 <= hhmm <= 1130:
        return True
    if 1300 <= hhmm <= 1600:
        return True
    return False
