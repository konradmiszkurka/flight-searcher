# Flight Searcher v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CLI w Pythonie, które dla trasy + zakresu dat znajduje najtańsze loty z elastycznością ±N dni (round-trip i one-way), źródło: Google Flights przez `fast-flights`.

**Architecture:** Warstwy z rozdzielonymi odpowiedzialnościami: `cli` (wejście/wyjście) → `search` (orkiestracja fan-out po kombinacjach dat) → `Provider` (wtyczka źródła) → `fast-flights`. Rdzeń (`flex`, `search`, `models`) nie zna szczegółów Google; gada tylko z abstrakcją `Provider`. Cache TTL na dysku chroni przed rate-limitem.

**Tech Stack:** Python 3.11+, `typer` (CLI), `rich` (tabela), `fast-flights` (dane), `pytest` (testy), `uv` (zależności).

## Global Constraints

- Python **3.11+**.
- Zależności zarządzane przez **uv**; wszystkie polecenia przez `uv run ...`.
- Waluta domyślnie **PLN**, zmienna flagą `--currency`. (Implementacja: `fast-flights` 3.x honoruje walutę natywnie w `create_query`, więc ceny są w żądanej walucie — nie jest to już „best-effort".)
- Minimalizm v1: **1 dorosły, economy, bez limitu przesiadek** (żadnych flag `--adults/--cabin/--max-stops`).
- Testy **nie chodzą do sieci** — deterministyczne, na fixture'ach/fake'ach.
- Kwota pieniężna jako `decimal.Decimal`.
- **Commity: zwykłe komunikaty, BEZ żadnej wzmianki o AI/Claude, bez trailera `Co-Authored-By`.**
- Prefiks commitów: `feat:` / `test:` / `chore:` (Conventional Commits).

## File Structure

```
flight_searcher/
  __init__.py
  models.py         # SearchQuery, FlightOption, SearchResult (dataclasses)
  flex.py           # generate_date_combos: kombinacje dat (grid / window / one-way)
  cache.py          # DiskCache: prosty cache TTL na dysku (pickle)
  search.py         # run_search: fan-out po kombinacjach, agregacja, sort, top-N
  formatting.py     # build_table: render tabeli rich
  cli.py            # build_query + komenda typer, spina całość
  providers/
    __init__.py
    base.py         # Provider (Protocol) + FakeProvider? nie — fake żyje w testach
    google_flights.py  # parse_price, booking_url, _map_flights, GoogleFlightsProvider
tests/
  test_models.py
  test_flex.py
  test_cache.py
  test_search.py
  test_google_flights.py
  test_formatting.py
  test_cli.py
pyproject.toml
.env.example
README.md
```

---

## Task 1: Scaffold projektu (uv + pakiet + pytest)

**Files:**
- Create: `pyproject.toml`
- Create: `flight_searcher/__init__.py`
- Create: `flight_searcher/providers/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`
- Create: `.env.example`

**Interfaces:**
- Consumes: nic.
- Produces: importowalny pakiet `flight_searcher`; działające `uv run pytest`.

- [ ] **Step 1: Utwórz `pyproject.toml`**

```toml
[project]
name = "flight-searcher"
version = "0.1.0"
description = "CLI do wyszukiwania najtańszych lotów z elastycznością dat"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "rich>=13.0",
    "fast-flights>=2.2",
]

[project.scripts]
flight-search = "flight_searcher.cli:main"

[dependency-groups]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Utwórz puste pliki pakietu**

`flight_searcher/__init__.py`:
```python
```
`flight_searcher/providers/__init__.py`:
```python
```
`tests/__init__.py`:
```python
```
`.env.example`:
```
# Miejsce na przyszłe klucze providerów (RapidAPI / Amadeus). W v1 nieużywane.
# RAPIDAPI_KEY=
# AMADEUS_CLIENT_ID=
# AMADEUS_CLIENT_SECRET=
```

- [ ] **Step 3: Napisz smoke test**

`tests/test_smoke.py`:
```python
def test_package_imports():
    import flight_searcher
    assert flight_searcher is not None
```

- [ ] **Step 4: Zsynchronizuj zależności i uruchom testy**

Run: `uv sync && uv run pytest -q`
Expected: 1 passed. (Jeśli `uv sync` pobiera `fast-flights` — OK, potrzebne w Task 7.)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml flight_searcher tests .env.example uv.lock
git commit -m "chore: scaffold python package with uv and pytest"
```

---

## Task 2: Model danych (`models.py`)

**Files:**
- Create: `flight_searcher/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nic.
- Produces:
  - `SearchQuery(origin:str, dest:str, depart_date:date, return_date:date|None, flex:int, flex_mode:str, top:int, currency:str)` z property `is_round_trip -> bool`.
  - `FlightOption(price:Decimal, currency:str, depart_date:date, return_date:date|None, airlines:tuple[str,...], stops:int, duration:str, booking_url:str)`.
  - `SearchResult(options:list[FlightOption], combos_total:int, combos_failed:int)`.

- [ ] **Step 1: Napisz failujący test**

`tests/test_models.py`:
```python
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
```

- [ ] **Step 2: Uruchom test — ma failować**

Run: `uv run pytest tests/test_models.py -q`
Expected: FAIL (`ModuleNotFoundError: flight_searcher.models`).

- [ ] **Step 3: Zaimplementuj `models.py`**

```python
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
```

- [ ] **Step 4: Uruchom testy — mają przejść**

Run: `uv run pytest tests/test_models.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add flight_searcher/models.py tests/test_models.py
git commit -m "feat: add core data models"
```

---

## Task 3: Generator kombinacji dat (`flex.py`)

**Files:**
- Create: `flight_searcher/flex.py`
- Test: `tests/test_flex.py`

**Interfaces:**
- Consumes: `SearchQuery` z `models`.
- Produces: `generate_date_combos(query: SearchQuery) -> list[tuple[date, date | None]]`.

**Logika:**
- one-way (`return_date is None`): wylot ±flex → `[(d, None), ...]`.
- round-trip `grid`: wylot ±flex × powrót ±flex, tylko pary gdzie `powrót > wylot`.
- round-trip `window`: stała długość pobytu (`return_date - depart_date`), przesuwane okno ±flex.

- [ ] **Step 1: Napisz failujące testy**

`tests/test_flex.py`:
```python
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
```

- [ ] **Step 2: Uruchom testy — mają failować**

Run: `uv run pytest tests/test_flex.py -q`
Expected: FAIL (`ModuleNotFoundError: flight_searcher.flex`).

- [ ] **Step 3: Zaimplementuj `flex.py`**

```python
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
```

- [ ] **Step 4: Uruchom testy — mają przejść**

Run: `uv run pytest tests/test_flex.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add flight_searcher/flex.py tests/test_flex.py
git commit -m "feat: add date combination generator for flex modes"
```

---

## Task 4: Cache na dysku (`cache.py`)

**Files:**
- Create: `flight_searcher/cache.py`
- Test: `tests/test_cache.py`

**Interfaces:**
- Consumes: nic (przechowuje dowolne obiekty picklowalne).
- Produces: `DiskCache(directory, ttl_seconds:int, time_fn=time.time)` z metodami `get(key) -> value | None` i `set(key, value) -> None`. `time_fn` wstrzykiwalny do testów TTL.

- [ ] **Step 1: Napisz failujące testy**

`tests/test_cache.py`:
```python
from flight_searcher.cache import DiskCache


def test_set_then_get_returns_value(tmp_path):
    cache = DiskCache(tmp_path, ttl_seconds=100, time_fn=lambda: 0.0)
    cache.set(("WAW", "DOH"), [1, 2, 3])
    assert cache.get(("WAW", "DOH")) == [1, 2, 3]


def test_get_missing_returns_none(tmp_path):
    cache = DiskCache(tmp_path, ttl_seconds=100, time_fn=lambda: 0.0)
    assert cache.get(("NOPE",)) is None


def test_expired_entry_returns_none(tmp_path):
    clock = {"t": 0.0}
    cache = DiskCache(tmp_path, ttl_seconds=100, time_fn=lambda: clock["t"])
    cache.set(("WAW", "DOH"), "x")
    clock["t"] = 101.0
    assert cache.get(("WAW", "DOH")) is None


def test_fresh_entry_within_ttl(tmp_path):
    clock = {"t": 0.0}
    cache = DiskCache(tmp_path, ttl_seconds=100, time_fn=lambda: clock["t"])
    cache.set(("WAW", "DOH"), "x")
    clock["t"] = 99.0
    assert cache.get(("WAW", "DOH")) == "x"
```

- [ ] **Step 2: Uruchom testy — mają failować**

Run: `uv run pytest tests/test_cache.py -q`
Expected: FAIL (`ModuleNotFoundError: flight_searcher.cache`).

- [ ] **Step 3: Zaimplementuj `cache.py`**

```python
import hashlib
import pickle
import time
from pathlib import Path
from typing import Any, Callable, Optional


class DiskCache:
    def __init__(self, directory, ttl_seconds: int, time_fn: Callable[[], float] = time.time):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds
        self.time_fn = time_fn

    def _path(self, key) -> Path:
        digest = hashlib.sha256(repr(key).encode("utf-8")).hexdigest()
        return self.dir / f"{digest}.pkl"

    def get(self, key) -> Optional[Any]:
        path = self._path(key)
        if not path.exists():
            return None
        with path.open("rb") as fh:
            stamped_at, value = pickle.load(fh)
        if self.time_fn() - stamped_at > self.ttl:
            return None
        return value

    def set(self, key, value: Any) -> None:
        path = self._path(key)
        with path.open("wb") as fh:
            pickle.dump((self.time_fn(), value), fh)
```

- [ ] **Step 4: Uruchom testy — mają przejść**

Run: `uv run pytest tests/test_cache.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add flight_searcher/cache.py tests/test_cache.py
git commit -m "feat: add TTL disk cache"
```

---

## Task 5: Orkiestrator wyszukiwania (`search.py` + `providers/base.py`)

**Files:**
- Create: `flight_searcher/providers/base.py`
- Create: `flight_searcher/search.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Consumes: `SearchQuery`, `FlightOption`, `SearchResult` z `models`; `generate_date_combos` z `flex`; `DiskCache` z `cache` (opcjonalnie).
- Produces:
  - `Provider` (Protocol) z metodą `search_one(origin:str, dest:str, depart_date:date, return_date:date|None, currency:str) -> list[FlightOption]`.
  - `run_search(query, provider, cache=None, max_workers=4) -> SearchResult` — dla każdej kombinacji dat woła `provider.search_one`, bierze najtańszą ofertę z kombinacji, agreguje, sortuje rosnąco po cenie, tnie do `query.top`. Awaria pojedynczej kombinacji zwiększa `combos_failed`, nie przerywa całości. Jeśli `cache` podany: odczyt/zapis listy ofert per kombinacja.

- [ ] **Step 1: Napisz failujące testy**

`tests/test_search.py`:
```python
from datetime import date
from decimal import Decimal

from flight_searcher.models import SearchQuery, FlightOption
from flight_searcher.search import run_search


def _q(**kw):
    base = dict(origin="WAW", dest="DOH", depart_date=date(2026, 2, 5),
                return_date=date(2026, 2, 21), flex=1, flex_mode="window",
                top=10, currency="PLN")
    base.update(kw)
    return SearchQuery(**base)


def _opt(price, dep, ret):
    return FlightOption(price=Decimal(price), currency="PLN", depart_date=dep,
                        return_date=ret, airlines=("X",), stops=0,
                        duration="6h", booking_url="http://x")


class FakeProvider:
    """Zwraca oferty zależne od daty wylotu; opcjonalnie failuje dla wskazanych dni."""
    def __init__(self, fail_on=(), calls=None):
        self.fail_on = set(fail_on)
        self.calls = calls if calls is not None else []

    def search_one(self, origin, dest, depart_date, return_date, currency):
        self.calls.append((depart_date, return_date))
        if depart_date in self.fail_on:
            raise RuntimeError("boom")
        base = 1000 + depart_date.day  # różne ceny per dzień
        return [_opt(base + 50, depart_date, return_date),
                _opt(base, depart_date, return_date)]  # tańsza druga


def test_takes_cheapest_per_combo_and_sorts():
    provider = FakeProvider()
    result = run_search(_q(flex=1, flex_mode="window"), provider, max_workers=2)
    # window flex=1 -> 3 kombinacje (4,5,6 lut). Bierze tańszą per kombinacja (base).
    prices = [o.price for o in result.options]
    assert prices == sorted(prices)
    assert len(result.options) == 3
    assert result.combos_total == 3
    assert result.combos_failed == 0
    # najtańszy = najniższy dzień wylotu (4 lut -> base 1004)
    assert result.options[0].price == Decimal("1004")


def test_top_truncates():
    provider = FakeProvider()
    result = run_search(_q(flex=3, flex_mode="window", top=2), provider, max_workers=2)
    assert len(result.options) == 2


def test_failed_combo_counted_not_fatal():
    provider = FakeProvider(fail_on=[date(2026, 2, 5)])
    result = run_search(_q(flex=1, flex_mode="window"), provider, max_workers=2)
    assert result.combos_failed == 1
    assert result.combos_total == 3
    assert len(result.options) == 2  # 3 kombinacje - 1 padła


def test_uses_cache_when_present():
    class CountingProvider(FakeProvider):
        pass
    provider = CountingProvider()

    class MemCache:
        def __init__(self):
            self.store = {}
        def get(self, key):
            return self.store.get(key)
        def set(self, key, value):
            self.store[key] = value

    cache = MemCache()
    q = _q(flex=1, flex_mode="window")
    run_search(q, provider, cache=cache, max_workers=1)
    first_calls = len(provider.calls)
    run_search(q, provider, cache=cache, max_workers=1)
    # drugi przebieg w całości z cache — brak nowych wywołań providera
    assert len(provider.calls) == first_calls
```

- [ ] **Step 2: Uruchom testy — mają failować**

Run: `uv run pytest tests/test_search.py -q`
Expected: FAIL (`ModuleNotFoundError: flight_searcher.search`).

- [ ] **Step 3: Zaimplementuj `providers/base.py`**

```python
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
```

- [ ] **Step 4: Zaimplementuj `search.py`**

```python
import concurrent.futures
import logging
from typing import Optional

from .flex import generate_date_combos
from .models import FlightOption, SearchQuery, SearchResult

logger = logging.getLogger(__name__)


def _cheapest(options: list[FlightOption]) -> Optional[FlightOption]:
    return min(options, key=lambda o: o.price) if options else None


def run_search(query: SearchQuery, provider, cache=None, max_workers: int = 4) -> SearchResult:
    combos = generate_date_combos(query)

    def work(combo):
        depart, ret = combo
        key = (query.origin, query.dest, depart, ret, query.currency)
        if cache is not None:
            cached = cache.get(key)
            if cached is not None:
                return cached
        options = provider.search_one(query.origin, query.dest, depart, ret, query.currency)
        if cache is not None:
            cache.set(key, options)
        return options

    cheapest_per_combo: list[FlightOption] = []
    failed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(work, combo): combo for combo in combos}
        for future in concurrent.futures.as_completed(futures):
            try:
                options = future.result()
            except Exception as exc:  # pojedyncza kombinacja nie zabija całości
                logger.warning("kombinacja %s nie powiodła się: %s", futures[future], exc)
                failed += 1
                continue
            best = _cheapest(options)
            if best is not None:
                cheapest_per_combo.append(best)

    cheapest_per_combo.sort(key=lambda o: o.price)
    return SearchResult(
        options=cheapest_per_combo[: query.top],
        combos_total=len(combos),
        combos_failed=failed,
    )
```

- [ ] **Step 5: Uruchom testy — mają przejść**

Run: `uv run pytest tests/test_search.py -q`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add flight_searcher/providers/base.py flight_searcher/search.py tests/test_search.py
git commit -m "feat: add search orchestrator with provider protocol"
```

---

## Task 6: Adapter Google Flights (`providers/google_flights.py`)

> **Deviation (implementacja):** kod poniżej zakładał `fast-flights` 2.x; zainstalowana wersja to 3.0.2 z zupełnie innym API. Rzeczywista implementacja używa `FlightQuery`/`create_query`/`fetcher.parse` + cookie zgody (obejście unijnej ściany zgody Google) i `coerce_price` zamiast `parse_price`. Szczegóły: `.superpowers/sdd/task-6-brief.md` + `task-6-report.md`.

**Files:**
- Create: `flight_searcher/providers/google_flights.py`
- Test: `tests/test_google_flights.py`

**Interfaces:**
- Consumes: `FlightOption` z `models`; biblioteka `fast_flights`.
- Produces:
  - `parse_price(text: str | None) -> Decimal | None` — wyciąga kwotę z napisu ("$740", "PLN 1 234", "€99.50").
  - `booking_url(origin, dest, depart_date, return_date) -> str` — deep-link do Google Flights.
  - `_map_flights(raw_flights, depart_date, return_date, currency, origin, dest) -> list[FlightOption]` — czysta konwersja, testowana na fixture.
  - `GoogleFlightsProvider(seat="economy", adults=1, fetch_mode="fallback")` implementujący `Provider.search_one` (cienka integracja z `fast_flights`, weryfikowana ręcznie).

**Uwaga o walucie:** `fast-flights` nie gwarantuje wyboru waluty — `currency` jest etykietą przypisywaną do oferty, a realna waluta zależy od Google. To świadome ograniczenie v1 (patrz README). Prawdziwy wybór waluty = przyszłe ulepszenie.

- [ ] **Step 1: Napisz failujące testy (czysta logika, bez sieci)**

`tests/test_google_flights.py`:
```python
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from flight_searcher.providers.google_flights import (
    parse_price, booking_url, _map_flights,
)


def test_parse_price_dollar():
    assert parse_price("$740") == Decimal("740")


def test_parse_price_thousands_separator():
    assert parse_price("PLN 1,234") == Decimal("1234")


def test_parse_price_spaces_and_code():
    assert parse_price("1 234 zł") == Decimal("1234")


def test_parse_price_decimal():
    assert parse_price("€99.50") == Decimal("99.50")


def test_parse_price_empty_or_garbage_returns_none():
    assert parse_price("") is None
    assert parse_price(None) is None
    assert parse_price("brak") is None


def test_booking_url_round_trip_contains_airports_and_dates():
    url = booking_url("WAW", "DOH", date(2026, 2, 5), date(2026, 2, 21))
    assert url.startswith("https://www.google.com/travel/flights")
    assert "WAW" in url and "DOH" in url
    assert "2026-02-05" in url and "2026-02-21" in url


def test_map_flights_builds_options_and_skips_unpriced():
    raw = [
        SimpleNamespace(name="Qatar Airways", stops=0, duration="6h 20m", price="$740"),
        SimpleNamespace(name="LOT", stops=1, duration="9h", price="$900"),
        SimpleNamespace(name="Broken", stops=0, duration="5h", price="brak"),
    ]
    opts = _map_flights(raw, date(2026, 2, 5), date(2026, 2, 21), "PLN", "WAW", "DOH")
    assert len(opts) == 2  # oferta bez ceny pominięta
    assert opts[0].price == Decimal("740")
    assert opts[0].airlines == ("Qatar Airways",)
    assert opts[0].stops == 0
    assert opts[0].currency == "PLN"
    assert opts[0].depart_date == date(2026, 2, 5)
    assert opts[0].return_date == date(2026, 2, 21)
```

- [ ] **Step 2: Uruchom testy — mają failować**

Run: `uv run pytest tests/test_google_flights.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Zaimplementuj `providers/google_flights.py`**

```python
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import quote

from ..models import FlightOption


def parse_price(text: Optional[str]) -> Optional[Decimal]:
    if not text:
        return None
    cleaned = re.sub(r"[^0-9.,]", "", text)
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")   # przecinek = separator tysięcy
    elif "," in cleaned:
        cleaned = cleaned.replace(",", "")   # ceny lotów bez groszy -> przecinek to tysiące
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def booking_url(origin: str, dest: str, depart_date: date, return_date: Optional[date]) -> str:
    parts = [f"Flights from {origin} to {dest}", f"on {depart_date.isoformat()}"]
    if return_date is not None:
        parts.append(f"returning {return_date.isoformat()}")
    query = " ".join(parts)
    return f"https://www.google.com/travel/flights?q={quote(query)}"


def _map_flights(raw_flights, depart_date, return_date, currency, origin, dest) -> list[FlightOption]:
    url = booking_url(origin, dest, depart_date, return_date)
    options: list[FlightOption] = []
    for flight in raw_flights:
        price = parse_price(getattr(flight, "price", None))
        if price is None:
            continue
        name = getattr(flight, "name", None)
        options.append(FlightOption(
            price=price,
            currency=currency,
            depart_date=depart_date,
            return_date=return_date,
            airlines=(name,) if name else (),
            stops=int(getattr(flight, "stops", 0) or 0),
            duration=str(getattr(flight, "duration", "") or ""),
            booking_url=url,
        ))
    return options


class GoogleFlightsProvider:
    def __init__(self, seat: str = "economy", adults: int = 1, fetch_mode: str = "fallback"):
        self.seat = seat
        self.adults = adults
        self.fetch_mode = fetch_mode

    def search_one(self, origin, dest, depart_date, return_date, currency) -> list[FlightOption]:
        from fast_flights import FlightData, Passengers, get_flights

        flight_data = [FlightData(date=depart_date.isoformat(), from_airport=origin, to_airport=dest)]
        trip = "one-way"
        if return_date is not None:
            flight_data.append(FlightData(date=return_date.isoformat(), from_airport=dest, to_airport=origin))
            trip = "round-trip"

        result = get_flights(
            flight_data=flight_data,
            trip=trip,
            seat=self.seat,
            passengers=Passengers(adults=self.adults),
            fetch_mode=self.fetch_mode,
        )
        return _map_flights(result.flights, depart_date, return_date, currency, origin, dest)
```

- [ ] **Step 4: Uruchom testy jednostkowe — mają przejść**

Run: `uv run pytest tests/test_google_flights.py -q`
Expected: 7 passed.

- [ ] **Step 5: Ręczna weryfikacja integracji z `fast-flights`**

`fast-flights` jest nieoficjalne — API i kształt `Flight` (`.name/.stops/.duration/.price`) oraz parametry `get_flights` mogą różnić się między wersjami. Zweryfikuj na żywo:

Run:
```bash
uv run python -c "
from datetime import date
from flight_searcher.providers.google_flights import GoogleFlightsProvider
p = GoogleFlightsProvider()
opts = p.search_one('WAW', 'DOH', date(2026, 2, 5), date(2026, 2, 21), 'PLN')
print('otrzymano', len(opts), 'ofert')
for o in opts[:3]:
    print(o.price, o.currency, o.airlines, o.stops, o.duration)
"
```
Expected: wypisuje kilka ofert z cenami. Jeśli błąd atrybutu/parametru — dostosuj `search_one`/`_map_flights` do faktycznego API zainstalowanej wersji (`uv run python -c "import fast_flights, inspect; print(inspect.signature(fast_flights.get_flights))"`) i sprawdź realną walutę zwracanych cen (zaktualizuj notkę w README, jeśli to nie PLN).

- [ ] **Step 6: Commit**

```bash
git add flight_searcher/providers/google_flights.py tests/test_google_flights.py
git commit -m "feat: add google flights provider via fast-flights"
```

---

## Task 7: Render tabeli (`formatting.py`)

**Files:**
- Create: `flight_searcher/formatting.py`
- Test: `tests/test_formatting.py`

**Interfaces:**
- Consumes: `SearchResult`, `SearchQuery`, `FlightOption` z `models`; `rich.table.Table`.
- Produces:
  - `build_table(result: SearchResult, query: SearchQuery) -> rich.table.Table` — 7 kolumn (Cena, Wylot, Powrót, Linie, Przesiadki, Czas, Link); one-way pokazuje "—" w kolumnie Powrót.
  - `print_results(result, query, console=None) -> None` — cienki wrapper drukujący tabelę i ewentualne ostrzeżenie o nieudanych kombinacjach.

- [ ] **Step 1: Napisz failujące testy**

`tests/test_formatting.py`:
```python
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
```

- [ ] **Step 2: Uruchom testy — mają failować**

Run: `uv run pytest tests/test_formatting.py -q`
Expected: FAIL (`ModuleNotFoundError: flight_searcher.formatting`).

- [ ] **Step 3: Zaimplementuj `formatting.py`**

```python
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
```

- [ ] **Step 4: Uruchom testy — mają przejść**

Run: `uv run pytest tests/test_formatting.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add flight_searcher/formatting.py tests/test_formatting.py
git commit -m "feat: add rich table rendering"
```

---

## Task 8: CLI i spięcie całości (`cli.py` + README)

**Files:**
- Create: `flight_searcher/cli.py`
- Create: `README.md` (nadpisuje pusty)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `SearchQuery` z `models`; `run_search` z `search`; `GoogleFlightsProvider` z `providers.google_flights`; `DiskCache` z `cache`; `print_results` z `formatting`; `typer`.
- Produces:
  - `build_query(origin, dest, depart, return_, flex, flex_mode, top, currency) -> SearchQuery` — parsuje daty (ISO), waliduje (`flex_mode in {grid,window}`, `flex >= 0`, powrót > wylot), normalizuje kody lotnisk do uppercase, `return_` puste/None ⇒ one-way.
  - `search(...)` — komenda typer spinająca provider + cache + orkiestrator + render.
  - `main()` — entry point (`app()`), podpięty w `[project.scripts]`.

- [ ] **Step 1: Napisz failujące testy (czysta funkcja `build_query`)**

`tests/test_cli.py`:
```python
from datetime import date
import pytest

from flight_searcher.cli import build_query


def test_build_query_round_trip_uppercases_and_parses():
    q = build_query("waw", "doh", "2026-02-05", "2026-02-21", 3, "grid", 10, "PLN")
    assert q.origin == "WAW" and q.dest == "DOH"
    assert q.depart_date == date(2026, 2, 5)
    assert q.return_date == date(2026, 2, 21)
    assert q.is_round_trip is True


def test_build_query_one_way_when_return_empty():
    q = build_query("WAW", "DOH", "2026-02-05", None, 2, "grid", 10, "PLN")
    assert q.return_date is None
    assert q.is_round_trip is False


def test_build_query_rejects_bad_flex_mode():
    with pytest.raises(ValueError):
        build_query("WAW", "DOH", "2026-02-05", None, 2, "spiral", 10, "PLN")


def test_build_query_rejects_return_before_depart():
    with pytest.raises(ValueError):
        build_query("WAW", "DOH", "2026-02-21", "2026-02-05", 0, "grid", 10, "PLN")


def test_build_query_rejects_negative_flex():
    with pytest.raises(ValueError):
        build_query("WAW", "DOH", "2026-02-05", None, -1, "grid", 10, "PLN")
```

- [ ] **Step 2: Uruchom testy — mają failować**

Run: `uv run pytest tests/test_cli.py -q`
Expected: FAIL (`ModuleNotFoundError: flight_searcher.cli`).

- [ ] **Step 3: Zaimplementuj `cli.py`**

```python
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
    depart: str = typer.Option(..., "--depart", help="Data wylotu YYYY-MM-DD"),
    return_: Optional[str] = typer.Option(None, "--return", help="Data powrotu YYYY-MM-DD (brak = one-way)"),
    flex: int = typer.Option(0, "--flex", help="Elastyczność ±N dni"),
    flex_mode: str = typer.Option("grid", "--flex-mode", help="grid | window"),
    top: int = typer.Option(10, "--top", help="Ile najtańszych wyników pokazać"),
    currency: str = typer.Option("PLN", "--currency", help="Waluta (etykieta best-effort)"),
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
```

- [ ] **Step 4: Uruchom testy — mają przejść**

Run: `uv run pytest tests/test_cli.py -q`
Expected: 5 passed.

- [ ] **Step 5: Napisz `README.md`**

```markdown
# flight-searcher

CLI do wyszukiwania najtańszych lotów z elastycznością dat (round-trip i one-way),
oparte na Google Flights przez bibliotekę `fast-flights`.

## Instalacja

```bash
uv sync
```

## Użycie

```bash
# round-trip, siatka dat ±3
uv run flight-search WAW DOH --depart 2026-02-05 --return 2026-02-21 --flex 3 --flex-mode grid

# stała długość pobytu, przesuwane okno ±3
uv run flight-search WAW DOH --depart 2026-02-05 --return 2026-02-21 --flex 3 --flex-mode window

# one-way (bez --return)
uv run flight-search WAW DOH --depart 2026-02-05 --flex 2
```

Flagi: `--flex N`, `--flex-mode grid|window`, `--top N` (domyślnie 10),
`--currency PLN`, `--no-cache`.

## Ograniczenia v1

- Źródło `fast-flights` jest nieoficjalne — zmiana po stronie Google może wymagać
  aktualizacji adaptera (`providers/google_flights.py`).
- `--currency` to etykieta best-effort; realna waluta zależy od Google Flights.
- Minimalizm: 1 dorosły, klasa economy, bez limitu przesiadek.
- Tryb `grid` generuje dużo kombinacji (±3 = 49) — cache (TTL 6h) chroni przed
  ponownym obciążaniem Google.

## Testy

```bash
uv run pytest -q
```

## Roadmap

- v2: monitoring w tle (cron), progi cenowe, powiadomienia.
- Kolejne providery: RapidAPI, Amadeus.
- Filtry: `--max-stops`, `--cabin`, `--adults`.
```

- [ ] **Step 6: Smoke test end-to-end (na żywo)**

Run:
```bash
uv run flight-search WAW DOH --depart 2026-02-05 --return 2026-02-21 --flex 1 --flex-mode window --top 5
```
Expected: wypisuje tabelę do 5 najtańszych kombinacji (lub czytelne ostrzeżenie, jeśli część kombinacji padła). Brak stack trace.

- [ ] **Step 7: Pełny zestaw testów**

Run: `uv run pytest -q`
Expected: wszystkie testy przechodzą (models, flex, cache, search, google_flights, formatting, cli, smoke).

- [ ] **Step 8: Commit**

```bash
git add flight_searcher/cli.py tests/test_cli.py README.md
git commit -m "feat: add CLI entry point wiring the full search flow"
```

---

## Self-Review (wypełnione przy pisaniu planu)

- **Spec coverage:** round-trip/one-way (Task 3, 8), tryby grid/window (Task 3), źródło fast-flights (Task 6), tabela top-N (Task 7), waluta PLN + `--currency` (Task 8), minimalizm (Global Constraints + Task 6 defaults), cache TTL (Task 4), interfejs Provider wtyczkowy (Task 5), rate-limiting/współbieżność + niefatalne błędy (Task 5), testy offline (wszystkie taski). Provider interface pod przyszłe RapidAPI/Amadeus (Task 5, base.py). ✔
- **Placeholder scan:** brak TBD/TODO; każdy krok ma pełny kod. ✔
- **Type consistency:** `search_one(origin, dest, depart_date, return_date, currency)` spójne w base.py (Task 5), FakeProvider (Task 5), GoogleFlightsProvider (Task 6), search.py wywołaniu (Task 5). `run_search(query, provider, cache, max_workers)` spójne (Task 5, 8). `FlightOption` pola identyczne w models/_map_flights/formatting/testach. ✔
```
