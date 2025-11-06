from __future__ import annotations

import csv
import datetime as _dt
import threading
import time
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import ClassVar


@dataclass(slots=True)
class DataLogger:
    _shared_csv_file_lock: ClassVar[threading.Lock] = threading.Lock()

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
    _auto_flush_row_count: int = field(default=0, init=False, repr=False)
    _instruments: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def add_instrument(self, instrument: Any) -> None:
        name = getattr(instrument, "name", None)
        if not isinstance(name, str) or not name:
            msg = "Instrument must have a non-empty string 'name' attribute"
            raise TypeError(msg)
        with self._log_lock:
            self._instruments[name] = instrument

    def remove_instrument(self, instrument: Any) -> None:
        name = getattr(instrument, "name", None)
        if not isinstance(name, str) or not name:
            return
        with self._log_lock:
            self._instruments.pop(name, None)

    def _read_instrument_with_optional_duration(
        self,
        instrument: Any,
        duration_sec: float | None,
    ) -> dict[str, Any]:
        read_method = getattr(instrument, "read", None)
        if not callable(read_method):
            msg = "Instrument requires a read() method"
            raise TypeError(msg)
        if duration_sec is None:
            try:
                result = read_method()
            except TypeError:
                result = read_method(0.0)
        else:
            try:
                result = read_method(duration_sec)
            except TypeError:
                result = read_method()
        return dict(result)

    def _prepare_logging(
        self,
        extra_fields: dict[str, Any] | None,
        auto_csv_path: str | None,
        auto_flush_row_count: int,
    ) -> None:
        with self._log_lock:
            self._extra_values.clear()
            if extra_fields:
                for key, value in extra_fields.items():
                    self._extra_values[str(key)] = value
            if auto_csv_path is not None:
                self._auto_csv_path = Path(auto_csv_path)
                self._auto_flush_row_count = max(1, int(auto_flush_row_count))
            else:
                self._auto_csv_path = None
                self._auto_flush_row_count = 0

    def _logging_loop(self, interval_sec: float) -> None:
        while not self._log_stop_event.is_set():
            perf_now = time.perf_counter()
            iso_timestamp = _dt.datetime.now(tz=_dt.UTC).isoformat()
            with self._log_lock:
                instruments_snapshot = list(self._instruments.items())
                extra_values_snapshot = dict(self._extra_values)
            payload: dict[str, Any] = {}
            for instrument_name, instrument in instruments_snapshot:
                instrument_data = self._read_instrument_with_optional_duration(
                    instrument,
                    interval_sec,
                )
                for key, value in instrument_data.items():
                    column_name = f"{instrument_name}.{key!s}"
                    payload[column_name] = value
            with self._log_lock:
                row: dict[str, Any] = {**payload, **extra_values_snapshot}
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

    def start_logging(
        self,
        extra_fields: dict[str, Any] | None = None,
        interval_sec: float = 1,
        auto_csv_path: str | None = None,
        auto_flush_row_count: int = 256,
    ) -> None:
        if self._log_thread and self._log_thread.is_alive():
            return

        self._prepare_logging(extra_fields, auto_csv_path, auto_flush_row_count)

        self._log_stop_event.clear()
        self._log_start_perf_counter = time.perf_counter()

        self._log_thread = threading.Thread(
            target=self._logging_loop,
            args=(interval_sec,),
            name="DataLogger-log",
            daemon=True,
        )
        self._log_thread.start()

    def _flush_log_rows_to_csv(self) -> None:
        with self._log_lock:
            if self._auto_csv_path is None or not self._log_rows:
                return
            rows = self._log_rows
            self._log_rows = []
            csv_path = self._auto_csv_path
        self._append_rows_to_csv(csv_path, rows)

    def _append_rows_to_csv(self, csv_path: Path, rows: list[dict[str, Any]]) -> None:
        self._append_rows_to_shared_csv(csv_path, rows)

    @staticmethod
    def _get_existing_header(csv_path: Path) -> tuple[bool, list[str]]:
        file_exists = csv_path.exists() and csv_path.stat().st_size > 0
        existing_header: list[str] = []
        if file_exists:
            with csv_path.open("r", newline="", encoding="utf-8") as file:
                reader = csv.reader(file)
                try:
                    existing_header = next(reader)
                except StopIteration:
                    file_exists = False
                    existing_header = []
        return file_exists, existing_header

    @staticmethod
    def _build_csv_columns(
        existing_header: list[str],
        rows: list[dict[str, Any]],
    ) -> list[str]:
        fixed = ["elapsed_sec", "iso_timestamp", "interval_sec"]
        row_keys = {key for row in rows for key in row}
        header_candidates = set(existing_header) | set(fixed) | row_keys
        new_keys = sorted(header_candidates - set(existing_header) - set(fixed))
        columns: list[str] = [name for name in fixed if name in header_candidates]
        for name in existing_header:
            if name not in columns and name in header_candidates:
                columns.append(name)
        for name in new_keys:
            if name not in columns:
                columns.append(name)
        return columns

    @classmethod
    def _append_rows_to_shared_csv(
        cls,
        csv_path: Path,
        rows: list[dict[str, Any]],
    ) -> None:
        if not rows:
            return
        with cls._shared_csv_file_lock:
            file_exists, existing_header = cls._get_existing_header(csv_path)
            columns = cls._build_csv_columns(existing_header, rows)
            if not file_exists:
                with csv_path.open("w", newline="", encoding="utf-8") as file:
                    writer: csv.DictWriter[Any] = csv.DictWriter(
                        file,
                        fieldnames=columns,
                        extrasaction="ignore",
                    )
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(row)
                return
            if columns == existing_header:
                with csv_path.open("a", newline="", encoding="utf-8") as file:
                    writer = csv.DictWriter(
                        file,
                        fieldnames=columns,
                        extrasaction="ignore",
                    )
                    for row in rows:
                        writer.writerow(row)
                return
            temp_path = csv_path.with_suffix(csv_path.suffix + ".tmp")
            with (
                csv_path.open("r", newline="", encoding="utf-8") as in_file,
                temp_path.open(
                    "w",
                    newline="",
                    encoding="utf-8",
                ) as out_file,
            ):
                reader_dict = csv.DictReader(in_file)
                writer_all: csv.DictWriter[Any] = csv.DictWriter(
                    out_file,
                    fieldnames=columns,
                    extrasaction="ignore",
                )
                writer_all.writeheader()
                for old_row in reader_dict:
                    writer_all.writerow(old_row)
                for row in rows:
                    writer_all.writerow(row)
            temp_path.replace(csv_path)

    def update_log(self, extra_updates: dict[str, Any]) -> None:
        with self._log_lock:
            for key, value in extra_updates.items():
                self._extra_values[str(key)] = value

    def stop_logging(self) -> None:
        if self._log_thread and self._log_thread.is_alive():
            self._log_stop_event.set()
            self._log_thread.join(timeout=2.0)
        if self._auto_csv_path is not None:
            self._flush_log_rows_to_csv()

    def clear_log(self) -> None:
        with self._log_lock:
            self._log_rows.clear()
            self._extra_values.clear()

    def save_csv(self, path: str, append: bool = False) -> None:  # noqa: FBT001, FBT002
        rows = self._copy_log_rows()
        csv_path = Path(path)
        if append:
            self._append_rows_to_csv(csv_path, rows)
            return
        columns = self._infer_columns_from_rows(rows)
        with csv_path.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _infer_columns_from_rows(self, rows: list[dict[str, Any]]) -> list[str]:
        fixed = ["elapsed_sec", "iso_timestamp", "interval_sec"]
        if not rows:
            return fixed
        dynamic = sorted({key for row in rows for key in row} - set(fixed))
        return [c for c in fixed if any(c in r for r in rows)] + dynamic

    @property
    def log_row_count(self) -> int:
        with self._log_lock:
            return len(self._log_rows)

    @property
    def log_data(self) -> list[dict[str, Any]]:
        with self._log_lock:
            return [dict(row) for row in self._log_rows]

    def _copy_log_rows(self) -> list[dict[str, Any]]:
        with self._log_lock:
            return [dict(row) for row in self._log_rows]
