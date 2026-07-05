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
uv run flight-search WAW DOH --depart 2026-08-05 --return 2026-08-21 --flex 3 --flex-mode grid

# stała długość pobytu, przesuwane okno ±3
uv run flight-search WAW DOH --depart 2026-08-05 --return 2026-08-21 --flex 3 --flex-mode window

# one-way (bez --return)
uv run flight-search WAW DOH --depart 2026-08-05 --flex 2
```

Flagi: `--flex N`, `--flex-mode grid|window`, `--top N` (domyślnie 10),
`--currency PLN`, `--no-cache`.

Ceny są zwracane w walucie podanej w `--currency` — biblioteka `fast-flights` 3.x
przekazuje tę wartość bezpośrednio do Google Flights.

## Ograniczenia v1

- Źródło `fast-flights` jest nieoficjalne — zmiana po stronie Google może wymagać
  aktualizacji adaptera (`providers/google_flights.py`).
- Dla wyszukiwań round-trip kolumny `Przesiadki` i `Czas` opisują wyłącznie lot
  w jedną stronę (wylot) — Google zwraca szczegóły lotu powrotnego w osobnym
  zapytaniu, więc cena jest pełnym szacowanym kosztem podróży w obie strony,
  ale przesiadki/czas dotyczą tylko odcinka w tamtą stronę.
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
