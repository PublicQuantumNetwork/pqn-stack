from __future__ import annotations
import atexit, datetime as _dt, logging, os, threading, time
from dataclasses import dataclass, field
from typing import Any, Callable
import numpy as np, pandas as pd
from pqnstack.base.errors import DeviceNotStartedError
from pqnstack.base.instrument import Instrument, InstrumentInfo, log_operation, log_parameter

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class PM100DInfo(InstrumentInfo):
    wavelength_nm: float = np.nan
    last_power_w: float = np.nan
    logging_rows: int = 0

@dataclass(slots=True)
class PM100D(Instrument):
    name: str
    desc: str
    hw_address: str
    parameters: set[str] = field(default_factory=lambda: {"wavelength_nm"})
    operations: dict[str, Callable[..., Any]] = field(default_factory=dict)

    file_descriptor: int | None = field(default=None, init=False, repr=False)
    _timeout_sec: float = field(default=5.0, init=False, repr=False)
    _wavelength_nm_cache: float = field(default=np.nan, init=False)
    _last_power_w: float = field(default=np.nan, init=False)
    _last_ref_w: float = field(default=np.nan, init=False)

    data_log_dataframe: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            {"elapsed_sec": [], "iso_timestamp": [], "pm1_w": [], "pm1_ref_w": [], "pm1_total_w": [], "interval_sec": [], "pax_wavelength_nm": []}
        ),
        init=False,
        repr=False,
    )
    log_start_time_perf_counter: float | None = field(default=None, init=False, repr=False)
    logging_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    stop_logging_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)

    def _fd_required(self) -> int:
        if self.file_descriptor is None:
            raise DeviceNotStartedError("Start the device first.")
        return self.file_descriptor

    def _query(self, cmd: str, *, max_bytes: int = 4096, read: bool = True) -> str:
        fd = self._fd_required()
        data = (cmd if cmd.endswith("\n") else cmd + "\n").encode("ascii", "ignore")
        total = 0
        while total < len(data):
            n = os.write(fd, data[total:])
            if n <= 0:
                raise TimeoutError("usbtmc write failed")
            total += n
        if not read:
            return ""
        deadline = time.monotonic() + self._timeout_sec
        chunks: list[bytes] = []
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError("usbtmc read timeout")
            chunk = os.read(fd, max_bytes)
            if chunk:
                chunks.append(chunk)
                if chunks[-1].endswith(b"\n") or sum(map(len, chunks)) >= max_bytes:
                    break
            else:
                time.sleep(0.001)
        return b"".join(chunks).decode("ascii", "ignore").strip()

    def _read_float(self, cmd: str) -> float:
        try:
            return float(self._query(cmd).split()[0])
        except Exception:
            return float("nan")

    def start(self) -> None:
        if not os.path.exists(self.hw_address):
            raise FileNotFoundError(f"USBTMC node not found: {self.hw_address}")
        if not os.access(self.hw_address, os.R_OK | os.W_OK):
            raise PermissionError(f"No rw access to {self.hw_address}")
        if self.file_descriptor is None:
            self.file_descriptor = os.open(self.hw_address, os.O_RDWR)
        try:
            self._query("*CLS", read=False)
        except Exception:
            pass
        if np.isfinite(self._wavelength_nm_cache):
            try:
                self._query(f"SENSE:CORR:WAV {self._wavelength_nm_cache}NM", read=False)
            except Exception as exc:
                logger.warning("failed to set wavelength to %s nm: %s", self._wavelength_nm_cache, exc)
        wav_read = self._read_float("SENSE:CORR:WAV?")
        self._wavelength_nm_cache = (wav_read * 1e9 if np.isfinite(wav_read) and wav_read < 10.0 else wav_read)
        self.operations.update({"start_logging": self.start_logging, "stop_logging": self.stop_logging, "clear_log": self.clear_log, "save_csv": self.save_csv, "snapshot": self.snapshot})
        atexit.register(self.close)

    def close(self) -> None:
        self.stop_logging()
        if self.file_descriptor is not None:
            try:
                os.close(self.file_descriptor)
            finally:
                self.file_descriptor = None

    @property
    def info(self) -> PM100DInfo:
        return PM100DInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            hw_status={"connected": self.file_descriptor is not None},
            wavelength_nm=self._wavelength_nm_cache,
            last_power_w=self._last_power_w,
            logging_rows=int(len(self.data_log_dataframe)),
        )

    @property
    @log_parameter
    def wavelength_nm(self) -> float:
        return self._wavelength_nm_cache

    @wavelength_nm.setter
    @log_parameter
    def wavelength_nm(self, val_nm: float) -> None:
        self._wavelength_nm_cache = float(val_nm)
        if self.file_descriptor is not None:
            try:
                self._query(f"SENSE:CORR:WAV {self._wavelength_nm_cache}NM", read=False)
            except Exception as exc:
                logger.warning("failed to set wavelength to %s nm: %s", self._wavelength_nm_cache, exc)

    @property
    @log_parameter
    def power_w(self) -> float:
        raw = self._read_float("MEAS:POW?")
        if not np.isfinite(raw):
            raise ValueError("unexpected PM100D power response")
        self._last_power_w = raw
        return raw

    def ref_w(self) -> float:
        for q in ("SENS:POW:REF?", "SENS:POW:DC:REF?", "CALC:REL:REF?"):
            v = self._read_float(q)
            if np.isfinite(v):
                self._last_ref_w = v
                return v
        self._last_ref_w = float("nan")
        return self._last_ref_w

    @log_operation
    def snapshot(self) -> dict[str, float]:
        raw = self.power_w
        ref = self.ref_w()
        total = raw - ref if np.isfinite(ref) else raw
        return {"pm1_w": raw, "pm1_ref_w": ref, "pm1_total_w": total, "pax_wavelength_nm": self._wavelength_nm_cache}

    @log_operation
    def start_logging(self, interval_sec: float = 0.2) -> None:
        if self.file_descriptor is None:
            raise DeviceNotStartedError("Start the device before logging.")
        if self.logging_thread and self.logging_thread.is_alive():
            return
        self.stop_logging_event.clear()
        self.log_start_time_perf_counter = time.perf_counter()

        def loop() -> None:
            while not self.stop_logging_event.is_set():
                now = time.perf_counter()
                row = self.snapshot()
                self.data_log_dataframe = pd.concat(
                    [
                        self.data_log_dataframe,
                        pd.DataFrame(
                            [
                                {
                                    "elapsed_sec": 0.0 if self.log_start_time_perf_counter is None else now - self.log_start_time_perf_counter,
                                    "iso_timestamp": _dt.datetime.now(tz=_dt.UTC).isoformat(),
                                    "pm1_w": row["pm1_w"],
                                    "pm1_ref_w": row["pm1_ref_w"],
                                    "pm1_total_w": row["pm1_total_w"],
                                    "pax_wavelength_nm": row["pax_wavelength_nm"],
                                    "interval_sec": interval_sec,
                                }
                            ]
                        ),
                    ],
                    ignore_index=True,
                )
                time.sleep(interval_sec)

        self.logging_thread = threading.Thread(target=loop, name=f"{self.name}-poll", daemon=True)
        self.logging_thread.start()

    @log_operation
    def stop_logging(self) -> None:
        if self.logging_thread and self.logging_thread.is_alive():
            self.stop_logging_event.set()
            self.logging_thread.join(timeout=2.0)

    @log_operation
    def clear_log(self) -> None:
        self.data_log_dataframe = self.data_log_dataframe.iloc[0:0]

    @log_operation
    def save_csv(self, path: str) -> None:
        self.data_log_dataframe.to_csv(path, index=False)

