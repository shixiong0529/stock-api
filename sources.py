import json
import math
import subprocess
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd
import pytz
from curl_cffi import requests as curl_requests

from cache import Cache

_cache = Cache()
_CN_TZ = pytz.timezone("Asia/Shanghai")
_KEY_INDEX_CODES = ["sh000001", "sz399001", "sz399006", "sh000300", "sh000688"]
_KEY_INDEX_NAMES = {
    "sh000001": "\u4e0a\u8bc1\u6307\u6570",
    "sz399001": "\u6df1\u8bc1\u6210\u6307",
    "sz399006": "\u521b\u4e1a\u677f\u6307",
    "sh000300": "\u6caa\u6df1300",
    "sh000688": "\u79d1\u521b50",
}
_SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
}
_SINA_A_COUNT_URL = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeStockCount?node=hs_a"
)
_SINA_A_PAGE_URL = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData"
)
_SINA_INDEX_URL = "https://hq.sinajs.cn/list=s_sh000001,s_sz399001,s_sz399006,s_sh000300,s_sh000688"
_MARKET_SUMMARY_SNAPSHOT = Path(__file__).with_name("market_summary_snapshot.json")


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


def _safe_item(df: pd.DataFrame, labels: list[str]) -> Any | None:
    for label in labels:
        row = df[df["item"] == label]
        if row.empty:
            continue
        value = row.iloc[0]["value"]
        if pd.isna(value):
            return None
        return value
    return None


def _safe_number(value: Any) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return number


def _series_number(series: pd.Series, labels: list[str]) -> float | int | None:
    for label in labels:
        if label in series:
            return _safe_number(series[label])
    return None


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

    actual_code = str(_safe_item(df, ["\u4ee3\u7801"]) or "")
    if normalized not in actual_code:
        return {"error": "invalid_symbol", "symbol": symbol}

    result = {
        "symbol": symbol,
        "name": _safe_item(df, ["\u540d\u79f0"]) or "",
        "price": _safe_number(_safe_item(df, ["\u73b0\u4ef7", "\u6700\u65b0\u4ef7"])),
        "change_pct": _safe_number(_safe_item(df, ["\u6da8\u5e45", "\u6da8\u8dcc\u5e45"])),
        "volume": _safe_number(_safe_item(df, ["\u6210\u4ea4\u989d"])),
        "pe": _safe_number(
            _safe_item(
                df,
                [
                    "\u5e02\u76c8\u7387(TTM)",
                    "\u5e02\u76c8\u7387(\u52a8)",
                    "\u5e02\u76c8\u7387",
                ],
            )
        ),
        "pb": _safe_number(_safe_item(df, ["\u5e02\u51c0\u7387"])),
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
        fallback = _fallback_intraday_snapshot(symbol)
        if fallback is None:
            return {"error": "data_unavailable", "message": str(exc), "symbol": symbol}
        result = {"symbol": symbol, "data": [fallback], "fallback": "snapshot"}
        _cache.set(cache_key, result, ttl=30)
        return result

    result = {"symbol": symbol, "data": df.to_dict(orient="records")}
    _cache.set(cache_key, result, ttl=30)
    return result


def get_flow(symbol: str) -> dict[str, Any]:
    if is_hk(symbol):
        return {
            "error": "unsupported_market",
            "message": "\u6e2f\u80a1\u6682\u4e0d\u652f\u6301\u8d44\u91d1\u6d41\u5411\u67e5\u8be2",
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
        return {"error": "data_unavailable", "message": "\u65e0\u8d44\u91d1\u6d41\u6570\u636e", "symbol": symbol}

    row = df.iloc[-1]
    result = {
        "symbol": symbol,
        "date": str(row.get("\u65e5\u671f", "")),
        "main_net": _safe_number(row.get("\u4e3b\u529b\u51c0\u6d41\u5165-\u51c0\u989d")),
        "main_net_pct": _safe_number(row.get("\u4e3b\u529b\u51c0\u6d41\u5165-\u51c0\u5360\u6bd4")),
        "super_large_net": _safe_number(row.get("\u8d85\u5927\u5355\u51c0\u6d41\u5165-\u51c0\u989d")),
        "large_net": _safe_number(row.get("\u5927\u5355\u51c0\u6d41\u5165-\u51c0\u989d")),
        "retail_net": _safe_number(row.get("\u5c0f\u5355\u51c0\u6d41\u5165-\u51c0\u989d")),
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
            "message": "\u6e2f\u80a1\u6682\u4e0d\u652f\u6301\u516c\u544a\u67e5\u8be2",
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


def get_market_summary() -> dict[str, Any]:
    cache_key = "market:summary"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        market_df = _fetch_sina_a_market_spot()
        index_df = _fetch_sina_index_spot()
    except Exception as exc:
        cached_snapshot = _load_market_summary_snapshot()
        if cached_snapshot is not None:
            cached_snapshot["stale"] = True
            cached_snapshot["stale_reason"] = str(exc)
            return cached_snapshot
        return {"error": "data_unavailable", "message": str(exc)}

    if market_df.empty:
        return {"error": "data_unavailable", "message": "\u5168\u5e02\u573a\u884c\u60c5\u4e3a\u7a7a"}

    summary = {
        "date": datetime.now(_CN_TZ).strftime("%Y-%m-%d"),
        "breadth": _build_breadth(market_df),
        "turnover": _build_turnover(market_df),
        "indices": _build_indices(index_df),
        "top_gainers": _build_ranked_list(market_df, ascending=False),
        "top_losers": _build_ranked_list(market_df, ascending=True),
    }
    _save_market_summary_snapshot(summary)
    _cache.set(cache_key, summary, ttl=60)
    return summary


def _fetch_sina_a_market_spot() -> pd.DataFrame:
    total = int(_curl_fetch(_SINA_A_COUNT_URL).strip().strip('"'))
    page_count = math.ceil(total / 100)

    rows: list[dict[str, Any]] = []

    def fetch_page(page: int) -> list[dict[str, Any]]:
        params = {
            "page": str(page),
            "num": "100",
            "sort": "symbol",
            "asc": "1",
            "node": "hs_a",
            "symbol": "",
            "_s_r_a": "page",
        }
        query = "&".join(f"{key}={value}" for key, value in params.items())
        return json.loads(_curl_fetch(f"{_SINA_A_PAGE_URL}?{query}"))

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_page, page) for page in range(1, page_count + 1)]
        for future in as_completed(futures):
            rows.extend(future.result())

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["代码", "名称", "最新价", "涨跌幅", "成交量", "成交额"])

    df = df.rename(
        columns={
            "code": "代码",
            "name": "名称",
            "trade": "最新价",
            "changepercent": "涨跌幅",
            "volume": "成交量",
            "amount": "成交额",
        }
    )
    for column in ["最新价", "涨跌幅", "成交量", "成交额"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df[["代码", "名称", "最新价", "涨跌幅", "成交量", "成交额"]]


def _fetch_sina_index_spot() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for line in _curl_fetch(_SINA_INDEX_URL).splitlines():
        if not line.startswith("var hq_str_") or "=" not in line:
            continue
        symbol = line.split("var hq_str_", 1)[1].split("=", 1)[0]
        payload = line.split('"', 1)[1].rsplit('"', 1)[0]
        parts = payload.split(",")
        if len(parts) < 6:
            continue
        rows.append(
            {
                "代码": symbol[2:],
                "名称": parts[0],
                "最新价": _safe_number(parts[1]),
                "涨跌额": _safe_number(parts[2]),
                "涨跌幅": _safe_number(parts[3]),
                "成交量": _safe_number(parts[4]),
                "成交额": _safe_number(parts[5]),
            }
        )

    return pd.DataFrame(rows)


def _curl_fetch(url: str) -> str:
    command = [
        r"C:\Windows\System32\curl.exe",
        "--silent",
        "--show-error",
        "--max-time",
        "10",
    ]
    for key, value in _SINA_HEADERS.items():
        command.extend(["-H", f"{key}: {value}"])
    command.append(url)

    result = subprocess.run(command, capture_output=True, timeout=15, check=False)
    if result.returncode != 0:
        stderr = _decode_bytes(result.stderr).strip() or "curl_failed"
        raise RuntimeError(stderr)
    return _decode_bytes(result.stdout)


def _decode_bytes(payload: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="ignore")


def _save_market_summary_snapshot(summary: dict[str, Any]) -> None:
    _MARKET_SUMMARY_SNAPSHOT.write_text(
        json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _load_market_summary_snapshot() -> dict[str, Any] | None:
    if not _MARKET_SUMMARY_SNAPSHOT.exists():
        return None
    return json.loads(_MARKET_SUMMARY_SNAPSHOT.read_text(encoding="utf-8"))


def _build_breadth(df: pd.DataFrame) -> dict[str, int]:
    change_pct = pd.to_numeric(df["\u6da8\u8dcc\u5e45"], errors="coerce").fillna(0)
    up_count = int((change_pct > 0).sum())
    down_count = int((change_pct < 0).sum())
    flat_count = int((change_pct == 0).sum())
    return {
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "total": int(len(df)),
    }


def _build_turnover(df: pd.DataFrame) -> dict[str, float | int]:
    amount = float(pd.to_numeric(df["\u6210\u4ea4\u989d"], errors="coerce").fillna(0).sum())
    volume = float(pd.to_numeric(df["\u6210\u4ea4\u91cf"], errors="coerce").fillna(0).sum())
    return {"amount": amount, "volume": volume}


def _build_indices(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []

    working = df.copy()
    working["\u4ee3\u7801"] = working["\u4ee3\u7801"].astype(str)
    result: list[dict[str, Any]] = []
    for code in _KEY_INDEX_CODES:
        row = working[working["\u4ee3\u7801"] == code]
        if row.empty:
            continue
        item = row.iloc[0]
        result.append(
            {
                "symbol": code,
                "name": str(item.get("\u540d\u79f0", _KEY_INDEX_NAMES[code])),
                "price": _series_number(item, ["\u6700\u65b0\u4ef7"]),
                "change_pct": _series_number(item, ["\u6da8\u8dcc\u5e45"]),
                "change_amount": _series_number(item, ["\u6da8\u8dcc\u989d"]),
                "amount": _series_number(item, ["\u6210\u4ea4\u989d"]),
            }
        )
    return result


def _build_ranked_list(df: pd.DataFrame, ascending: bool) -> list[dict[str, Any]]:
    ranked = df.copy()
    ranked["\u6da8\u8dcc\u5e45"] = pd.to_numeric(ranked["\u6da8\u8dcc\u5e45"], errors="coerce")
    ranked["\u6210\u4ea4\u989d"] = pd.to_numeric(ranked["\u6210\u4ea4\u989d"], errors="coerce")
    ranked = ranked.dropna(subset=["\u6da8\u8dcc\u5e45"]).sort_values(
        "\u6da8\u8dcc\u5e45", ascending=ascending
    ).head(5)
    return [
        {
            "symbol": str(row["\u4ee3\u7801"]),
            "name": str(row["\u540d\u79f0"]),
            "price": _safe_number(row.get("\u6700\u65b0\u4ef7")),
            "change_pct": _safe_number(row.get("\u6da8\u8dcc\u5e45")),
            "amount": _safe_number(row.get("\u6210\u4ea4\u989d")),
        }
        for _, row in ranked.iterrows()
    ]


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
        return pd.DataFrame(
            columns=[
                "\u5173\u952e\u8bcd",
                "\u65b0\u95fb\u6807\u9898",
                "\u65b0\u95fb\u5185\u5bb9",
                "\u53d1\u5e03\u65f6\u95f4",
                "\u6587\u7ae0\u6765\u6e90",
                "\u65b0\u95fb\u94fe\u63a5",
            ]
        )

    df["\u65b0\u95fb\u94fe\u63a5"] = "http://finance.eastmoney.com/a/" + df["code"] + ".html"
    df = df.rename(
        columns={
            "title": "\u65b0\u95fb\u6807\u9898",
            "content": "\u65b0\u95fb\u5185\u5bb9",
            "date": "\u53d1\u5e03\u65f6\u95f4",
            "mediaName": "\u6587\u7ae0\u6765\u6e90",
        }
    )
    df["\u5173\u952e\u8bcd"] = symbol
    for column in ["\u65b0\u95fb\u6807\u9898", "\u65b0\u95fb\u5185\u5bb9"]:
        df[column] = (
            df[column]
            .astype(str)
            .str.replace("<em>", "", regex=False)
            .str.replace("</em>", "", regex=False)
            .str.replace("\\u3000", "", regex=False)
            .str.replace("\\r\\n", " ", regex=False)
        )
    return df[
        [
            "\u5173\u952e\u8bcd",
            "\u65b0\u95fb\u6807\u9898",
            "\u65b0\u95fb\u5185\u5bb9",
            "\u53d1\u5e03\u65f6\u95f4",
            "\u6587\u7ae0\u6765\u6e90",
            "\u65b0\u95fb\u94fe\u63a5",
        ]
    ]


def _fallback_intraday_snapshot(symbol: str) -> dict[str, Any] | None:
    try:
        df = ak.stock_individual_spot_xq(symbol=_xq_symbol(symbol))
    except Exception:
        return None

    if df.empty:
        return None

    if is_hk(symbol):
        return {
            "\u65f6\u95f4": _safe_item(df, ["\u65f6\u95f4"]),
            "\u5f00\u76d8": _safe_number(_safe_item(df, ["\u4eca\u5f00"])),
            "\u6536\u76d8": _safe_number(_safe_item(df, ["\u73b0\u4ef7", "\u6700\u65b0\u4ef7"])),
            "\u6700\u9ad8": _safe_number(_safe_item(df, ["\u6700\u9ad8"])),
            "\u6700\u4f4e": _safe_number(_safe_item(df, ["\u6700\u4f4e"])),
            "\u6210\u4ea4\u91cf": _safe_number(_safe_item(df, ["\u6210\u4ea4\u91cf"])),
            "\u6210\u4ea4\u989d": _safe_number(_safe_item(df, ["\u6210\u4ea4\u989d"])),
            "\u6700\u65b0\u4ef7": _safe_number(_safe_item(df, ["\u73b0\u4ef7", "\u6700\u65b0\u4ef7"])),
        }

    return {
        "day": _safe_item(df, ["\u65f6\u95f4"]),
        "open": _safe_number(_safe_item(df, ["\u4eca\u5f00"])),
        "high": _safe_number(_safe_item(df, ["\u6700\u9ad8"])),
        "low": _safe_number(_safe_item(df, ["\u6700\u4f4e"])),
        "close": _safe_number(_safe_item(df, ["\u73b0\u4ef7", "\u6700\u65b0\u4ef7"])),
        "volume": _safe_number(_safe_item(df, ["\u6210\u4ea4\u91cf"])),
        "amount": _safe_number(_safe_item(df, ["\u6210\u4ea4\u989d"])),
    }


def _is_trading_now() -> bool:
    now = datetime.now(_CN_TZ)
    if now.weekday() >= 5:
        return False

    hhmm = now.hour * 100 + now.minute
    if 930 <= hhmm <= 1130:
        return True
    if 1300 <= hhmm <= 1600:
        return True
    return False
