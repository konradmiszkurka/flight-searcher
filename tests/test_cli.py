from datetime import date
import pytest

from flight_searcher.cli import build_query


def test_build_query_round_trip_uppercases_and_parses():
    q = build_query("waw", "doh", "2026-08-05", "2026-08-21", 3, "grid", 10, "PLN")
    assert q.origin == "WAW" and q.dest == "DOH"
    assert q.depart_date == date(2026, 8, 5)
    assert q.return_date == date(2026, 8, 21)
    assert q.is_round_trip is True


def test_build_query_one_way_when_return_empty():
    q = build_query("WAW", "DOH", "2026-08-05", None, 2, "grid", 10, "PLN")
    assert q.return_date is None
    assert q.is_round_trip is False


def test_build_query_rejects_bad_flex_mode():
    with pytest.raises(ValueError):
        build_query("WAW", "DOH", "2026-08-05", None, 2, "spiral", 10, "PLN")


def test_build_query_rejects_return_before_depart():
    with pytest.raises(ValueError):
        build_query("WAW", "DOH", "2026-08-21", "2026-08-05", 0, "grid", 10, "PLN")


def test_build_query_rejects_negative_flex():
    with pytest.raises(ValueError):
        build_query("WAW", "DOH", "2026-08-05", None, -1, "grid", 10, "PLN")
