import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cache import Cache


def test_miss_returns_none():
    cache = Cache()
    assert cache.get("missing") is None


def test_hit_returns_value():
    cache = Cache()
    cache.set("k", "v", ttl=10)
    assert cache.get("k") == "v"


def test_expired_returns_none():
    cache = Cache()
    cache.set("k", "v", ttl=1)
    time.sleep(1.1)
    assert cache.get("k") is None


def test_clear_removes_entry():
    cache = Cache()
    cache.set("k", "v", ttl=10)
    cache.clear("k")
    assert cache.get("k") is None


def test_stores_dataframe():
    import pandas as pd

    cache = Cache()
    df = pd.DataFrame({"a": [1, 2]})
    cache.set("df", df, ttl=10)
    result = cache.get("df")
    assert result is not None
    assert list(result["a"]) == [1, 2]
