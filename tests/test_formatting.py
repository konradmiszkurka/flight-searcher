from datetime import date
from decimal import Decimal

from flight_searcher.models import SearchQuery, SearchResult, FlightOption
from flight_searcher.formatting import build_table


def _q(**kw):
    base = dict(origin="WAW", dest="DOH", depart_date=date(2026, 2, 5),
                return_date=date(2026, 2, 21), flex=0, flex_mode="grid",
                top=10, currency="PLN")
    base.update(kw)
    return SearchQuery(**base)


def _opt(ret):
    return FlightOption(price=Decimal("740"), currency="PLN", depart_date=date(2026, 2, 5),
                        return_date=ret, airlines=("Qatar Airways",), stops=0,
                        duration="6h", booking_url="http://x")


def test_table_has_seven_columns():
    table = build_table(SearchResult([_opt(date(2026, 2, 21))], 1, 0), _q())
    assert len(table.columns) == 7


def test_table_row_count_matches_options():
    result = SearchResult([_opt(date(2026, 2, 21)), _opt(date(2026, 2, 22))], 2, 0)
    table = build_table(result, _q())
    assert table.row_count == 2


def test_one_way_shows_dash_for_return():
    result = SearchResult([_opt(None)], 1, 0)
    table = build_table(result, _q(return_date=None))
    # kolumna Powrót (indeks 2) ma "—" w pierwszym wierszu
    assert list(table.columns[2].cells) == ["—"]
