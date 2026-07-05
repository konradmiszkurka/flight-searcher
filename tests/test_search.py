from datetime import date
from decimal import Decimal

from flight_searcher.models import SearchQuery, FlightOption
from flight_searcher.search import run_search


def _q(**kw):
    base = dict(origin="WAW", dest="DOH", depart_date=date(2026, 2, 5),
                return_date=date(2026, 2, 21), flex=1, flex_mode="window",
                top=10, currency="PLN")
    base.update(kw)
    return SearchQuery(**base)


def _opt(price, dep, ret):
    return FlightOption(price=Decimal(price), currency="PLN", depart_date=dep,
                        return_date=ret, airlines=("X",), stops=0,
                        duration="6h", booking_url="http://x")


class FakeProvider:
    """Zwraca oferty zależne od daty wylotu; opcjonalnie failuje dla wskazanych dni."""
    def __init__(self, fail_on=(), calls=None):
        self.fail_on = set(fail_on)
        self.calls = calls if calls is not None else []

    def search_one(self, origin, dest, depart_date, return_date, currency):
        self.calls.append((depart_date, return_date))
        if depart_date in self.fail_on:
            raise RuntimeError("boom")
        base = 1000 + depart_date.day  # różne ceny per dzień
        return [_opt(base + 50, depart_date, return_date),
                _opt(base, depart_date, return_date)]  # tańsza druga


def test_takes_cheapest_per_combo_and_sorts():
    provider = FakeProvider()
    result = run_search(_q(flex=1, flex_mode="window"), provider, max_workers=2)
    # window flex=1 -> 3 kombinacje (4,5,6 lut). Bierze tańszą per kombinacja (base).
    prices = [o.price for o in result.options]
    assert prices == sorted(prices)
    assert len(result.options) == 3
    assert result.combos_total == 3
    assert result.combos_failed == 0
    # najtańszy = najniższy dzień wylotu (4 lut -> base 1004)
    assert result.options[0].price == Decimal("1004")


def test_top_truncates():
    provider = FakeProvider()
    result = run_search(_q(flex=3, flex_mode="window", top=2), provider, max_workers=2)
    assert len(result.options) == 2


def test_failed_combo_counted_not_fatal():
    provider = FakeProvider(fail_on=[date(2026, 2, 5)])
    result = run_search(_q(flex=1, flex_mode="window"), provider, max_workers=2)
    assert result.combos_failed == 1
    assert result.combos_total == 3
    assert len(result.options) == 2  # 3 kombinacje - 1 padła


def test_uses_cache_when_present():
    class CountingProvider(FakeProvider):
        pass
    provider = CountingProvider()

    class MemCache:
        def __init__(self):
            self.store = {}
        def get(self, key):
            return self.store.get(key)
        def set(self, key, value):
            self.store[key] = value

    cache = MemCache()
    q = _q(flex=1, flex_mode="window")
    run_search(q, provider, cache=cache, max_workers=1)
    first_calls = len(provider.calls)
    run_search(q, provider, cache=cache, max_workers=1)
    # drugi przebieg w całości z cache — brak nowych wywołań providera
    assert len(provider.calls) == first_calls
