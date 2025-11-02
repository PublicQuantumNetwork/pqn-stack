from __future__ import annotations

import csv
import datetime as _dt
import threading
import time
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(slots=True)
class Sensor:
    """Logging and CSV mixin for classes that implement read() -> Mapping[str, Any].

    Adds: start_logging, stop_logging, clear_log, save_csv, logging_rows.
    """

    _sensor_log_rows: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False)
    _sensor_start_perf_counter: float | None = field(default=None, init=False, repr=False)
    _sensor_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _sensor_stop_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _sensor_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def start_logging(self, interval_sec: float = 0.2) -> None:
        if not callable(getattr(self, "read", None)):
            msg = "Sensor requires a read() method"
            raise TypeError(msg)
        if self._sensor_thread and self._sensor_thread.is_alive():
            return
        self._sensor_stop_event.clear()
        self._sensor_start_perf_counter = time.perf_counter()

        def _logging_loop() -> None:
            while not self._sensor_stop_event.is_set():
                perf_now = time.perf_counter()
                iso_timestamp = _dt.datetime.now(tz=_dt.UTC).isoformat()
                payload = dict(self.read())  # type: ignore[attr-defined]
                payload["elapsed_sec"] = (
                    0.0 if self._sensor_start_perf_counter is None else perf_now - self._sensor_start_perf_counter
                )
                payload["iso_timestamp"] = iso_timestamp
                payload.setdefault("interval_sec", interval_sec)
                with self._sensor_lock:
                    self._sensor_log_rows.append(payload)
                time.sleep(interval_sec)

        self._sensor_thread = threading.Thread(
            target=_logging_loop,
            name=f"{type(self).__name__}-sensor-log",
            daemon=True,
        )
        self._sensor_thread.start()

    def stop_logging(self) -> None:
        if self._sensor_thread and self._sensor_thread.is_alive():
            self._sensor_stop_event.set()
            self._sensor_thread.join(timeout=2.0)

    def clear_log(self) -> None:
        with self._sensor_lock:
            self._sensor_log_rows.clear()

    def save_csv(self, path: str) -> None:
        rows = self._copy_log_rows()
        columns = list(self._csv_columns())
        if not columns:
            fixed = ["elapsed_sec", "iso_timestamp", "interval_sec"]
            dynamic = sorted({key for row in rows for key in row} - set(fixed))
            columns = [c for c in fixed if any(c in r for r in rows)] + dynamic
        with Path(path).open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    @property
    def logging_rows(self) -> int:
        with self._sensor_lock:
            return len(self._sensor_log_rows)

    def _csv_columns(self) -> Iterable[str]:
        return []

    def _copy_log_rows(self) -> list[dict[str, Any]]:
        with self._sensor_lock:
            return [dict(row) for row in self._sensor_log_rows]
