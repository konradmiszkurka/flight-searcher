from datetime import date, timedelta
from typing import Optional

from .models import SearchQuery


def _date_range(center: date, flex: int) -> list[date]:
    return [center + timedelta(days=d) for d in range(-flex, flex + 1)]


def generate_date_combos(query: SearchQuery) -> list[tuple[date, Optional[date]]]:
    departs = _date_range(query.depart_date, query.flex)

    if query.return_date is None:
        return [(d, None) for d in departs]

    if query.flex_mode == "grid":
        returns = _date_range(query.return_date, query.flex)
        return [(d, r) for d in departs for r in returns if r > d]

    if query.flex_mode == "window":
        stay = (query.return_date - query.depart_date).days
        return [(d, d + timedelta(days=stay)) for d in departs]

    raise ValueError(f"nieznany flex_mode: {query.flex_mode!r}")
