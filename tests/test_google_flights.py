from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from flight_searcher.providers.google_flights import (
    coerce_price,
    booking_url,
    _format_duration,
    _map_flights,
)


def test_coerce_price_from_int():
    assert coerce_price(740) == Decimal("740")


def test_coerce_price_from_string_with_symbols():
    assert coerce_price("$1,234") == Decimal("1234")
    assert coerce_price("1 234 zł") == Decimal("1234")


def test_coerce_price_zero_or_garbage_returns_none():
    assert coerce_price(0) is None
    assert coerce_price(None) is None
    assert coerce_price("brak") is None
    assert coerce_price("") is None


def test_format_duration():
    assert _format_duration(380) == "6h 20m"
    assert _format_duration(120) == "2h"
    assert _format_duration(45) == "45m"
    assert _format_duration(0) == ""


def test_booking_url_round_trip_contains_airports_and_dates():
    url = booking_url("WAW", "DOH", date(2026, 2, 5), date(2026, 2, 21))
    assert url.startswith("https://www.google.com/travel/flights")
    assert "WAW" in url and "DOH" in url
    assert "2026-02-05" in url and "2026-02-21" in url


def test_booking_url_one_way_omits_return():
    url = booking_url("WAW", "DOH", date(2026, 2, 5), None)
    assert "returning" not in url


def test_map_flights_builds_options_and_skips_unpriced():
    raw = [
        SimpleNamespace(price=740, airlines=["Qatar Airways"],
                        flights=[SimpleNamespace(duration=380)]),
        SimpleNamespace(price=900, airlines=["LOT", "Lufthansa"],
                        flights=[SimpleNamespace(duration=200), SimpleNamespace(duration=340)]),
        SimpleNamespace(price=0, airlines=["Broken"],
                        flights=[SimpleNamespace(duration=300)]),
    ]
    opts = _map_flights(raw, date(2026, 2, 5), date(2026, 2, 21), "PLN", "WAW", "DOH")

    assert len(opts) == 2  # oferta z ceną 0 pominięta
    assert opts[0].price == Decimal("740")
    assert opts[0].currency == "PLN"
    assert opts[0].airlines == ("Qatar Airways",)
    assert opts[0].stops == 0
    assert opts[0].duration == "6h 20m"
    assert opts[0].depart_date == date(2026, 2, 5)
    assert opts[0].return_date == date(2026, 2, 21)
    # dwa odcinki -> jedna przesiadka, łączny czas 200+340=540 min = 9h
    assert opts[1].stops == 1
    assert opts[1].airlines == ("LOT", "Lufthansa")
    assert opts[1].duration == "9h"
