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
