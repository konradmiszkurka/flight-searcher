# Flight Searcher — Design v1

**Data:** 2026-07-05
**Status:** Zaakceptowany (v1)

## Cel

CLI w Pythonie, które dla podanej trasy i zakresu dat znajduje **najtańsze loty**
z elastycznością dat (±N dni), w stylu "lastminute". Wersja 1 działa **na żądanie**
(on-demand). Monitoring w tle + powiadomienia (cron) to osobna, późniejsza wersja 2.

Przykład docelowy:

```bash
flight-search WAW DOH --depart 2026-02-05 --return 2026-02-21 --flex 3 --flex-mode grid --top 10
```

## Zakres v1

**W zakresie:**
- Wyszukiwanie round-trip i one-way.
- Dwa tryby elastyczności dat: `grid` i `window`.
- Źródło danych: Google Flights przez bibliotekę `fast-flights` (darmowe, bez konta).
- Wynik: tabela top-N najtańszych kombinacji w terminalu.
- Waluta domyślnie PLN, zmienna flagą `--currency`.
- Minimalizm: 1 dorosły, klasa economy, bez limitu przesiadek (filtry później).
- Opcjonalny cache na dysku (TTL), żeby nie uderzać w Google w kółko.
- Interfejs `Provider` (wtyczkowy), żeby dołożyć kolejne źródła bez zmian w rdzeniu.

**Poza zakresem v1 (na później):**
- Monitoring w tle / cron / powiadomienia (e-mail, Telegram) — wersja 2.
- Providery RapidAPI i Amadeus (interfejs gotowy, implementacja później).
- Filtry: `--max-stops`, `--cabin`, `--adults`, godziny, linie.
- Web UI.

## Architektura

```
CLI  →  Orchestrator (search)  →  Providers (wtyczki)  →  źródła danych
 │              │                        │
 │              ├─ flex (generator dat)  └─ google_flights (fast-flights)
 │              └─ cache (opcjonalny)        [rapidapi, amadeus — później]
 └─ formatting (tabela rich)
```

Rdzeń (`flex`, `search`, `models`) nie zna szczegółów Google — komunikuje się wyłącznie
z abstrakcją `Provider`. Dołożenie kolejnego źródła = jeden nowy plik w `providers/`,
zero zmian w rdzeniu.

## Struktura projektu

```
flight_searcher/
  cli.py            # wejście: parsuje flagi, drukuje tabelę
  models.py         # SearchQuery, FlightOption, SearchResult (dataclasses)
  flex.py           # generuje kombinacje dat (tryb grid / window / one-way)
  search.py         # orkiestrator: fan-out po kombinacjach, agregacja, sort
  cache.py          # prosty cache TTL na dysku
  formatting.py     # render tabeli (rich)
  providers/
    base.py         # interfejs Provider.search_one(...) -> list[FlightOption]
    google_flights.py  # adapter fast-flights
tests/              # pytest: flex, agregacja, parsowanie providera (fixtures)
pyproject.toml      # zależności; zarządzane przez uv
.env.example        # miejsce na przyszłe klucze (RapidAPI/Amadeus)
README.md
```

**Stack:** Python 3.11+, `typer` (CLI), `rich` (tabela), `fast-flights` (dane),
`pytest` (testy), zarządzanie zależnościami przez **uv**.

## Model danych

- **SearchQuery** — znormalizowane wejście: `origin`, `dest`, `depart_date`,
  `return_date | None`, `flex`, `flex_mode`, `top`, `currency`.
- **FlightOption** — pojedyncza oferta: `price`, `currency`, `depart_date`,
  `return_date | None`, `airlines`, `stops`, `duration`, `booking_url`.
- **SearchResult** — agregat: posortowana lista `FlightOption` + metadane przebiegu
  (ile kombinacji sprawdzono, ile się nie powiodło).

## Interfejs providera

```
class Provider:
    def search_one(origin, dest, depart_date, return_date, currency) -> list[FlightOption]: ...
```

Provider odpowiada za **jedną konkretną parę dat** i zwraca listę ofert.
Orkiestrator odpowiada za pętlę po kombinacjach dat i agregację. Rozdzielenie
odpowiedzialności pozwala testować każdą warstwę niezależnie.

## Przepływ danych

1. CLI parsuje flagi i buduje `SearchQuery`. Brak `--return` ⇒ one-way.
2. `flex.py` generuje listę kombinacji dat:
   - **grid**: wylot ±N × powrót ±N (round-trip); dla ±3 → 49 kombinacji.
   - **window**: stała długość pobytu (z oryginalnych dat), przesuwane okno ±N;
     dla ±3 → 7 kombinacji.
   - **one-way**: tylko wylot ±N.
   - Uwaga na końce miesiąca / poprawne przesunięcia dat (arytmetyka na `date`).
3. `search.py` dla każdej kombinacji woła `provider.search_one(...)` z **ograniczoną
   współbieżnością** (domyślnie 4) i drobnymi opóźnieniami (ochrona przed rate-limitem
   Google). Jeśli w cache jest świeży wynik — używa go zamiast zapytania.
4. Z każdej kombinacji brana jest najtańsza oferta; wszystkie zbierane do wspólnej
   listy, sortowane rosnąco po cenie, cięte do `--top N`.
5. `formatting.py` drukuje tabelę: cena | daty | linie | przesiadki | czas | link.

## Obsługa błędów i rate-limiting

- Awaria pojedynczej kombinacji (timeout / brak lotów / blokada Google) **nie przerywa
  całości** — ostrzeżenie do logu, kontynuacja; na końcu podsumowanie
  "X z Y kombinacji się nie powiodło".
- **Cache TTL** (domyślnie ~6h), klucz = znormalizowane zapytanie. Ponowne odpalenie
  tej samej trasy jest natychmiastowe i nie obciąża Google.
- Limity: współbieżność 4, timeout na pojedyncze zapytanie, przyjazny komunikat, gdy
  `fast-flights` całkiem nie działa (np. zmiana po stronie Google).

## Testy (best practices)

- `test_flex.py` — logika generowania dat: grid / window / one-way, poprawne
  przesunięcia i końce miesiąca. Czysta logika, podejście TDD.
- `test_search.py` — agregacja i sortowanie z **fake providerem** (bez sieci).
- `test_google_flights.py` — parsowanie odpowiedzi z **zapisanego fixture'a**
  (bez uderzania w Google).
- Zasada: testy nie chodzą do sieci → szybkie, deterministyczne.

## Otwarte kwestie / założenia

- `fast-flights` jest nieoficjalne — akceptujemy ryzyko, że zmiana po stronie Google
  może wymagać aktualizacji adaptera. Izolacja w jednym pliku minimalizuje koszt.
- Konwersja walut: `fast-flights` przyjmuje walutę zapytania; zakładamy, że zwraca
  ceny w żądanej walucie (do weryfikacji w implementacji).

## Kolejne kroki (poza v1)

- Wersja 2: monitoring (cron), progi cenowe, powiadomienia.
- Dodatkowe providery: RapidAPI, Amadeus (konto/instrukcja już rozpoznane).
- Filtry i web UI.
