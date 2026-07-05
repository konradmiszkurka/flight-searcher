from datetime import date
from flight_searcher.models import SearchQuery
from flight_searcher.flex import generate_date_combos


def _q(**kw):
    base = dict(origin="WAW", dest="DOH", depart_date=date(2026, 2, 5),
                return_date=date(2026, 2, 21), flex=0, flex_mode="grid",
                top=10, currency="PLN")
    base.update(kw)
    return SearchQuery(**base)


def test_one_way_produces_departs_only():
    combos = generate_date_combos(_q(return_date=None, flex=2))
    assert len(combos) == 5
    assert all(ret is None for _, ret in combos)
    assert (date(2026, 2, 3), None) in combos
    assert (date(2026, 2, 7), None) in combos


def test_grid_produces_product_filtered_by_return_after_depart():
    combos = generate_date_combos(_q(flex=3, flex_mode="grid"))
    # 7 departs x 7 returns = 49; wszystkie powroty (18-24 lut) > wyloty (2-8 lut)
    assert len(combos) == 49
    assert all(ret > dep for dep, ret in combos)


def test_grid_filters_out_return_not_after_depart():
    # depart 2026-02-20, return 2026-02-21, flex 3 -> część powrotów <= wylot
    combos = generate_date_combos(
        _q(depart_date=date(2026, 2, 20), return_date=date(2026, 2, 21), flex=3, flex_mode="grid")
    )
    assert all(ret > dep for dep, ret in combos)
    assert len(combos) < 49


def test_window_keeps_fixed_stay_length():
    combos = generate_date_combos(_q(flex=3, flex_mode="window"))
    assert len(combos) == 7
    stay = (date(2026, 2, 21) - date(2026, 2, 5)).days
    assert all((ret - dep).days == stay for dep, ret in combos)


def test_flex_zero_single_combo():
    combos = generate_date_combos(_q(flex=0, flex_mode="grid"))
    assert combos == [(date(2026, 2, 5), date(2026, 2, 21))]
