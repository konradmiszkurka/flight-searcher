from datetime import date
from decimal import Decimal
from flight_searcher.models import SearchQuery, FlightOption, SearchResult


def test_round_trip_query_is_round_trip():
    q = SearchQuery("WAW", "DOH", date(2026, 2, 5), date(2026, 2, 21),
                    flex=3, flex_mode="grid", top=10, currency="PLN")
    assert q.is_round_trip is True


def test_one_way_query_is_not_round_trip():
    q = SearchQuery("WAW", "DOH", date(2026, 2, 5), None,
                    flex=0, flex_mode="grid", top=10, currency="PLN")
    assert q.is_round_trip is False


def test_flight_option_holds_values():
    o = FlightOption(price=Decimal("740"), currency="PLN", depart_date=date(2026, 2, 5),
                     return_date=date(2026, 2, 21), airlines=("Qatar Airways",),
                     stops=0, duration="6h 20m", booking_url="http://x")
    assert o.price == Decimal("740")
    assert o.airlines == ("Qatar Airways",)


def test_search_result_defaults():
    r = SearchResult(options=[], combos_total=49, combos_failed=2)
    assert r.combos_total == 49 and r.combos_failed == 2
