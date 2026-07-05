"""Adapter źródła Google Flights oparty o bibliotekę `fast-flights` (3.x).

Cała wiedza o nieoficjalnym API `fast-flights` jest zamknięta w tym pliku —
reszta aplikacji zna tylko interfejs `Provider.search_one`.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import quote

from ..models import FlightOption


def coerce_price(value) -> Optional[Decimal]:
    """Zamień cenę z fast-flights na Decimal.

    `fast-flights` 3.x zwraca cenę jako `int`; dopuszczamy też napisy
    ("$1,234", "1 234 zł") na wypadek zmian po stronie biblioteki.
    Zwraca None dla braku ceny, zera lub wartości niepoprawnej.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value)) if value else None
    cleaned = re.sub(r"[^0-9.,]", "", str(value))
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")  # przecinek = separator tysięcy
    elif "," in cleaned:
        cleaned = cleaned.replace(",", "")  # ceny lotów bez groszy -> przecinek to tysiące
    try:
        result = Decimal(cleaned)
    except InvalidOperation:
        return None
    return result if result else None


def _format_duration(minutes: int) -> str:
    """Sformatuj łączny czas w minutach jako "6h 20m" / "2h" / "45m"."""
    minutes = int(minutes or 0)
    if minutes <= 0:
        return ""
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def booking_url(origin: str, dest: str, depart_date: date, return_date: Optional[date]) -> str:
    """Zbuduj deep-link wyszukiwania Google Flights (best-effort)."""
    parts = [f"Flights from {origin} to {dest}", f"on {depart_date.isoformat()}"]
    if return_date is not None:
        parts.append(f"returning {return_date.isoformat()}")
    query = " ".join(parts)
    return f"https://www.google.com/travel/flights?q={quote(query)}"


def _map_flights(raw_flights, depart_date, return_date, currency, origin, dest) -> list[FlightOption]:
    """Zmapuj obiekty `Flights` z fast-flights na nasze `FlightOption`.

    Każdy `Flights` ma: `price:int`, `airlines:list[str]`, `flights:list[<leg>]`
    (kolejne odcinki lotu; `<leg>.duration` to minuty). Liczba przesiadek =
    liczba odcinków - 1. Oferty bez ceny są pomijane.
    """
    url = booking_url(origin, dest, depart_date, return_date)
    options: list[FlightOption] = []
    for flight in raw_flights:
        price = coerce_price(getattr(flight, "price", None))
        if price is None:
            continue
        legs = getattr(flight, "flights", None) or []
        stops = max(len(legs) - 1, 0)
        duration = _format_duration(sum(getattr(leg, "duration", 0) or 0 for leg in legs))
        airlines = tuple(getattr(flight, "airlines", None) or ())
        options.append(FlightOption(
            price=price,
            currency=currency,
            depart_date=depart_date,
            return_date=return_date,
            airlines=airlines,
            stops=stops,
            duration=duration,
            booking_url=url,
        ))
    return options


# Cookie zgody (SOCS) pozwalający pominąć unijną ścianę zgody Google
# (consent.google.com), która blokuje domyślny fetcher fast-flights na
# europejskich IP. Bez niego Google zwraca stronę zgody zamiast wyników.
CONSENT_COOKIE = "SOCS=CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg"


class GoogleFlightsProvider:
    """Provider odpytujący Google Flights przez `fast-flights` (3.x).

    Używa własnego wywołania fetchera z cookie zgody, bo domyślne
    `get_flights()` trafia na unijną ścianę zgody i nie zwraca wyników.
    """

    def __init__(
        self,
        seat: str = "economy",
        adults: int = 1,
        consent_cookie: str = CONSENT_COOKIE,
        timeout: float = 30.0,
    ):
        self.seat = seat
        self.adults = adults
        self.consent_cookie = consent_cookie
        self.timeout = timeout

    def search_one(self, origin, dest, depart_date, return_date, currency) -> list[FlightOption]:
        from fast_flights import FlightQuery, Passengers, create_query
        from fast_flights.fetcher import Client, URL, parse

        flights = [FlightQuery(date=depart_date.isoformat(), from_airport=origin, to_airport=dest)]
        trip = "one-way"
        if return_date is not None:
            flights.append(FlightQuery(date=return_date.isoformat(), from_airport=dest, to_airport=origin))
            trip = "round-trip"

        query = create_query(
            flights=flights,
            seat=self.seat,
            trip=trip,
            passengers=Passengers(adults=self.adults),
            currency=currency,
        )

        client = Client(impersonate="chrome_145", impersonate_os="macos", referer=True, cookie_store=True)
        response = client.get(
            URL,
            params=query.params(),
            headers={"Cookie": self.consent_cookie},
            timeout=self.timeout,
        )
        result = parse(response.text)
        return _map_flights(result, depart_date, return_date, currency, origin, dest)
