from datetime import date
from typing import Optional, Protocol

from ..models import FlightOption


class Provider(Protocol):
    def search_one(
        self,
        origin: str,
        dest: str,
        depart_date: date,
        return_date: Optional[date],
        currency: str,
    ) -> list[FlightOption]:
        ...
