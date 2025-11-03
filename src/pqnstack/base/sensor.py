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
    _log_rows: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False)
    _log_start_perf_counter: float | None = field(default=None, init=False, repr=False)
    _log_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _log_stop_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _log_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _extra_values: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def _read_with_optional_duration(self, duration_sec: float | None) -> dict[str, Any]:
        read_method = getattr(self, "read", None)
        if not callable(read_method):
            msg = "Sensor requires a read() method"
            raise TypeError(msg)
        if duration_sec is None:
            try:
                return dict(read_method())
            except TypeError:
                return dict(read_method(0.0))
        try:
            return dict(read_method(duration_sec))
        except TypeError:
            return dict(read_method())

    def start_logging(self, extra_fields: dict[str, Any] | None = None, *, interval_sec: float = 0.2) -> None:
        if not callable(getattr(self, "read", None)):
            msg = "Sensor requires a read() method"
            raise TypeError(msg)
        if self._log_thread and self._log_thread.is_alive():
            return

        with self._log_lock:
            self._extra_values.clear()
            if extra_fields:
                for key, value in extra_fields.items():
                    self._extra_values[str(key)] = value

        self._log_stop_event.clear()
        self._log_start_perf_counter = time.perf_counter()

        def logging_loop() -> None:
            while not self._log_stop_event.is_set():
                perf_now = time.perf_counter()
                iso_timestamp = _dt.datetime.now(tz=_dt.UTC).isoformat()
                payload = self._read_with_optional_duration(interval_sec)
                with self._log_lock:
                    row = {**payload, **self._extra_values}
                    row["elapsed_sec"] = (
                        0.0 if self._log_start_perf_counter is None else perf_now - self._log_start_perf_counter
                    )
                    row["iso_timestamp"] = iso_timestamp
                    row.setdefault("interval_sec", interval_sec)
                    self._log_rows.append(row)
                time.sleep(interval_sec)

        self._log_thread = threading.Thread(
            target=logging_loop,
            name=f"{type(self).__name__}-sensor-log",
            daemon=True,
        )
        self._log_thread.start()

    def update_log(self, extra_updates: dict[str, Any]) -> None:
        with self._log_lock:
            for key, value in extra_updates.items():
                self._extra_values[str(key)] = value

    def stop_logging(self) -> None:
        if self._log_thread and self._log_thread.is_alive():
            self._log_stop_event.set()
            self._log_thread.join(timeout=2.0)

    def clear_log(self) -> None:
        with self._log_lock:
            self._log_rows.clear()
            self._extra_values.clear()

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
    def log_row_count(self) -> int:
        with self._log_lock:
            return len(self._log_rows)

    @property
    def log_data(self) -> list[dict[str, Any]]:
        with self._log_lock:
            return [dict(row) for row in self._log_rows]

    def _csv_columns(self) -> Iterable[str]:
        return []

    def _copy_log_rows(self) -> list[dict[str, Any]]:
        with self._log_lock:
            return [dict(row) for row in self._log_rows]
