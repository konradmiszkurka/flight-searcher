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
