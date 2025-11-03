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
    _log_stop_event: threading.Event = field(
        default_factory=threading.Event,
        init=False,
        repr=False,
    )
    _log_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    _extra_values: dict[str, Any] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    _auto_csv_path: Path | None = field(default=None, init=False, repr=False)
    _auto_csv_header_written: bool = field(default=False, init=False, repr=False)
    _auto_flush_row_count: int = field(default=0, init=False, repr=False)

    @property
    def log_row_count(self) -> int:
        with self._log_lock:
            return len(self._log_rows)

    @property
    def log_data(self) -> list[dict[str, Any]]:
        with self._log_lock:
            return [dict(row) for row in self._log_rows]

    def start_logging(
        self,
        extra_fields: dict[str, Any] | None = None,
        interval_sec: float = 0.2,
        auto_csv_path: str | None = None,
        auto_flush_row_count: int = 256,
    ) -> None:
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
            if auto_csv_path is not None:
                self._auto_csv_path = Path(auto_csv_path)
                self._auto_csv_header_written = False
                self._auto_flush_row_count = max(1, int(auto_flush_row_count))
            else:
                self._auto_csv_path = None
                self._auto_csv_header_written = False
                self._auto_flush_row_count = 0

        self._log_stop_event.clear()
        self._log_start_perf_counter = time.perf_counter()

        def logging_loop() -> None:
            while not self._log_stop_event.is_set():
                perf_now = time.perf_counter()
                iso_timestamp = _dt.datetime.now(tz=_dt.UTC).isoformat()
                payload = self._read_with_optional_duration(interval_sec)
                with self._log_lock:
                    row: dict[str, Any] = {**payload, **self._extra_values}
                    row["elapsed_sec"] = (
                        0.0 if self._log_start_perf_counter is None else perf_now - self._log_start_perf_counter
                    )
                    row["iso_timestamp"] = iso_timestamp
                    row.setdefault("interval_sec", interval_sec)
                    self._log_rows.append(row)
                    should_flush_to_csv = (
                        self._auto_csv_path is not None
                        and self._auto_flush_row_count > 0
                        and len(self._log_rows) >= self._auto_flush_row_count
                    )
                if should_flush_to_csv:
                    self._flush_log_rows_to_csv()
                time.sleep(interval_sec)
            if self._auto_csv_path is not None:
                self._flush_log_rows_to_csv()

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
        self._flush_log_rows_to_csv()

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

    def _flush_log_rows_to_csv(self) -> None:
        with self._log_lock:
            if self._auto_csv_path is None or not self._log_rows:
                return
            rows = self._log_rows
            self._log_rows = []
            csv_path = self._auto_csv_path
            header_written = self._auto_csv_header_written
        assert csv_path is not None
        columns = list(self._csv_columns())
        if not columns:
            fixed = ["elapsed_sec", "iso_timestamp", "interval_sec"]
            dynamic = sorted({key for row in rows for key in row} - set(fixed))
            columns = [c for c in fixed if any(c in r for r in rows)] + dynamic
        mode = "a" if header_written else "w"
        with csv_path.open(mode, newline="", encoding="utf-8") as file:
            writer: csv.DictWriter[Any] = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
            if not header_written:
                writer.writeheader()
            for row in rows:
                writer.writerow(row)
        if not header_written:
            with self._log_lock:
                self._auto_csv_header_written = True

    def _csv_columns(self) -> Iterable[str]:
        return []

    def _copy_log_rows(self) -> list[dict[str, Any]]:
        with self._log_lock:
            return [dict(row) for row in self._log_rows]
