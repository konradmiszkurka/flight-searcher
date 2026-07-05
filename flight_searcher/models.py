from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class SearchQuery:
    origin: str
    dest: str
    depart_date: date
    return_date: Optional[date]
    flex: int
    flex_mode: str  # "grid" | "window"
    top: int
    currency: str

    @property
    def is_round_trip(self) -> bool:
        return self.return_date is not None


@dataclass(frozen=True)
class FlightOption:
    price: Decimal
    currency: str
    depart_date: date
    return_date: Optional[date]
    airlines: tuple[str, ...]
    stops: int
    duration: str
    booking_url: str


@dataclass
class SearchResult:
    options: list[FlightOption]
    combos_total: int
    combos_failed: int
