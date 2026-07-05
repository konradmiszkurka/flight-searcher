from datetime import date
from pathlib import Path
from typing import Optional

import typer

from .cache import DiskCache
from .formatting import print_results
from .models import SearchQuery
from .providers.google_flights import GoogleFlightsProvider
from .search import run_search

app = typer.Typer(add_completion=False, help="Wyszukiwarka najtańszych lotów z elastycznością dat.")

CACHE_TTL_SECONDS = 6 * 3600


def build_query(origin, dest, depart, return_, flex, flex_mode, top, currency) -> SearchQuery:
    if flex_mode not in ("grid", "window"):
        raise ValueError(f"flex_mode musi być 'grid' lub 'window', otrzymano {flex_mode!r}")
    if flex < 0:
        raise ValueError("flex musi być >= 0")
    depart_date = date.fromisoformat(depart)
    return_date = date.fromisoformat(return_) if return_ else None
    if return_date is not None and return_date <= depart_date:
        raise ValueError("data powrotu musi być późniejsza niż data wylotu")
    return SearchQuery(
        origin=origin.upper(),
        dest=dest.upper(),
        depart_date=depart_date,
        return_date=return_date,
        flex=flex,
        flex_mode=flex_mode,
        top=top,
        currency=currency,
    )


@app.command()
def search(
    origin: str = typer.Argument(..., help="Kod lotniska wylotu, np. WAW"),
    dest: str = typer.Argument(..., help="Kod lotniska docelowego, np. DOH"),
    depart: str = typer.Option(..., "--depart", help="Data wylotu YYYY-MM-DD, np. 2026-08-05"),
    return_: Optional[str] = typer.Option(
        None, "--return", help="Data powrotu YYYY-MM-DD, np. 2026-08-21 (brak = one-way)"
    ),
    flex: int = typer.Option(0, "--flex", help="Elastyczność ±N dni"),
    flex_mode: str = typer.Option("grid", "--flex-mode", help="grid | window"),
    top: int = typer.Option(10, "--top", help="Ile najtańszych wyników pokazać"),
    currency: str = typer.Option("PLN", "--currency", help="Waluta zwracana przez Google Flights, np. PLN"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Pomiń cache"),
):
    try:
        query = build_query(origin, dest, depart, return_, flex, flex_mode, top, currency)
    except ValueError as exc:
        raise typer.BadParameter(str(exc))

    cache = None if no_cache else DiskCache(
        Path.home() / ".cache" / "flight-searcher", ttl_seconds=CACHE_TTL_SECONDS
    )
    provider = GoogleFlightsProvider()

    typer.echo(f"Szukam {query.origin} → {query.dest} (tryb {query.flex_mode}, ±{query.flex} dni)...")
    result = run_search(query, provider, cache=cache)
    print_results(result, query)


def main():
    app()


if __name__ == "__main__":
    main()
