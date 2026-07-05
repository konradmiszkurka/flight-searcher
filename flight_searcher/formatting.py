from typing import Optional

from rich.console import Console
from rich.table import Table

from .models import SearchQuery, SearchResult


def build_table(result: SearchResult, query: SearchQuery) -> Table:
    table = Table(title=f"{query.origin} → {query.dest}  (najtańsze {len(result.options)})")
    for column in ("Cena", "Wylot", "Powrót", "Linie", "Przesiadki", "Czas", "Link"):
        table.add_column(column)
    for option in result.options:
        table.add_row(
            f"{option.price:.0f} {option.currency}",
            option.depart_date.isoformat(),
            option.return_date.isoformat() if option.return_date else "—",
            ", ".join(option.airlines),
            str(option.stops),
            option.duration,
            option.booking_url,
        )
    return table


def print_results(result: SearchResult, query: SearchQuery, console: Optional[Console] = None) -> None:
    console = console or Console()
    console.print(build_table(result, query))
    if result.combos_failed:
        console.print(
            f"[yellow]{result.combos_failed} z {result.combos_total} "
            f"kombinacji się nie powiodło[/yellow]"
        )
