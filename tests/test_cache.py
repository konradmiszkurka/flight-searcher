from flight_searcher.cache import DiskCache


def test_set_then_get_returns_value(tmp_path):
    cache = DiskCache(tmp_path, ttl_seconds=100, time_fn=lambda: 0.0)
    cache.set(("WAW", "DOH"), [1, 2, 3])
    assert cache.get(("WAW", "DOH")) == [1, 2, 3]


def test_get_missing_returns_none(tmp_path):
    cache = DiskCache(tmp_path, ttl_seconds=100, time_fn=lambda: 0.0)
    assert cache.get(("NOPE",)) is None


def test_expired_entry_returns_none(tmp_path):
    clock = {"t": 0.0}
    cache = DiskCache(tmp_path, ttl_seconds=100, time_fn=lambda: clock["t"])
    cache.set(("WAW", "DOH"), "x")
    clock["t"] = 101.0
    assert cache.get(("WAW", "DOH")) is None


def test_fresh_entry_within_ttl(tmp_path):
    clock = {"t": 0.0}
    cache = DiskCache(tmp_path, ttl_seconds=100, time_fn=lambda: clock["t"])
    cache.set(("WAW", "DOH"), "x")
    clock["t"] = 99.0
    assert cache.get(("WAW", "DOH")) == "x"
