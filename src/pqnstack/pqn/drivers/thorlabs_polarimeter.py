from __future__ import annotations

import atexit
import contextlib as contextlib
import datetime as _dt
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

import numpy as np
import pandas as pd
import pyvisa

from pqnstack.base.errors import DeviceNotStartedError
from pqnstack.base.instrument import Instrument, InstrumentInfo, log_operation, log_parameter

logger = logging.getLogger(__name__)

USB_FILTER = "USB?*::INSTR"
CMD_ENABLE_CALC = "SENS:CALC 1"
CMD_ENABLE_ROTATION = "INP:ROT:STAT 1"
CMD_DISABLE_CALC = "SENS:CALC 0"
CMD_DISABLE_ROTATION = "INP:ROT:STAT 0"
QRY_IS_CALC_ENABLED = "SENS:CALC?"
QRY_IS_ROTATION_ENABLED = "INP:ROT:STAT?"
QRY_WAVELENGTH_METERS_OR_NM = "SENS:CORR:WAV?"
QRY_LATEST = "SENS:DATA:LAT?"
QRY_IDN = "*IDN?"


@dataclass(frozen=True, slots=True)
class PAX1000IR2Info(InstrumentInfo):
    wavelength_nm: float = np.nan
    last_theta_deg: float = np.nan
    last_eta_deg: float = np.nan
    last_dop: float = np.nan
    last_power_w: float = np.nan
    logging_rows: int = 0


@dataclass(slots=True)
class PAX1000IR2(Instrument):
    name: str
    desc: str
    hw_address: str  # VISA resource or empty for discovery
    parameters: set[str] = field(default_factory=set)
    operations: dict[str, Any] = field(default_factory=dict)

    pax_id_contains: Optional[str] = None
    pax_idn_contains: str = "PAX1000"

    _rm: Any | None = field(default=None, init=False, repr=False)
    _instr: Any | None = field(default=None, init=False, repr=False)
    _timeout_ms: int = field(default=3000, init=False, repr=False)

    _wavelength_nm_cache: float = field(default=np.nan, init=False)
    _last_theta_deg: float = field(default=np.nan, init=False)
    _last_eta_deg: float = field(default=np.nan, init=False)
    _last_dop: float = field(default=np.nan, init=False)
    _last_power_w: float = field(default=np.nan, init=False)

    data_log_dataframe: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            {
                "elapsed_sec": [],
                "iso_timestamp": [],
                "pax_theta_deg": [],
                "pax_eta_deg": [],
                "pax_power_w": [],
                "pax_dop": [],
                "pax_wavelength_nm": [],
                "interval_sec": [],
            }
        ),
        init=False,
        repr=False,
    )
    log_start_time_perf_counter: float | None = field(default=None, init=False, repr=False)
    logging_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    stop_logging_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)

    def _q(self, cmd: str) -> str:
        if self._instr is None:
            raise DeviceNotStartedError("Start the device first.")
        try:
            self._instr.write(f"{cmd}\n")
            return str(self._instr.read()).strip()
        except Exception:
            try:
                return str(self._instr.query(cmd)).strip()
            except Exception:
                return ""

    def _w(self, cmd: str) -> None:
        if self._instr is None:
            raise DeviceNotStartedError("Start the device first.")
        try:
            self._instr.write(f"{cmd}\n")
        except Exception:
            with contextlib.suppress(Exception):
                self._instr.write(cmd)

    def start(self) -> None:
        if self._instr is not None:
            return
        try:
            self._rm = pyvisa.ResourceManager("@py")
        except Exception as exc:
            raise RuntimeError(f"VISA backend not available: {exc}") from exc

        resource = self.hw_address
        if not resource:
            try:
                resources: Tuple[str, ...] = self._rm.list_resources(USB_FILTER)
            except Exception as exc:
                raise FileNotFoundError(f"VISA resource discovery failed: {exc}") from exc
            if self.pax_id_contains:
                resources = tuple(r for r in resources if self.pax_id_contains in r)
            if not resources:
                raise FileNotFoundError("No USB VISA resources matched filter.")
            if len(resources) == 1 and not self.pax_idn_contains:
                resource = resources[0]
            else:
                target = self.pax_idn_contains or ""
                matched = []
                for rname in resources:
                    try:
                        with self._rm.open_resource(rname) as tmp:
                            tmp.timeout = self._timeout_ms
                            try:
                                tmp.write(f"{QRY_IDN}\n")
                                idn = str(tmp.read()).strip()
                            except Exception:
                                try:
                                    idn = str(tmp.query(QRY_IDN)).strip()
                                except Exception:
                                    idn = ""
                            if not target or target in idn:
                                matched.append(rname)
                    except Exception:
                        continue
                if len(matched) != 1:
                    raise FileNotFoundError("PAX discovery ambiguous or no match.")
                resource = matched[0]

        try:
            self._instr = self._rm.open_resource(resource)
            self._instr.timeout = self._timeout_ms
        except Exception as exc:
            self._instr = None
            raise RuntimeError(f"Failed to open VISA resource {resource}: {exc}") from exc

        def write_and_confirm(set_cmd: str, qry_cmd: str, expect: str | int | float) -> bool:
            self._w(set_cmd)
            expected = str(expect)
            last = ""
            for _ in range(10):
                try:
                    last = self._q(qry_cmd)
                except Exception:
                    last = ""
                if last.startswith(expected):
                    return True
                time.sleep(0.05)
            return False

        ok1 = write_and_confirm(CMD_ENABLE_CALC, QRY_IS_CALC_ENABLED, 1)
        ok2 = write_and_confirm(CMD_ENABLE_ROTATION, QRY_IS_ROTATION_ENABLED, 1)
        if not (ok1 and ok2):
            with contextlib.suppress(Exception):
                write_and_confirm(CMD_DISABLE_CALC, QRY_IS_CALC_ENABLED, 0)
                write_and_confirm(CMD_DISABLE_ROTATION, QRY_IS_ROTATION_ENABLED, 0)
            raise RuntimeError("PAX setup failed to enable calc/rotation.")

        try:
            raw = self._q(QRY_WAVELENGTH_METERS_OR_NM)
            val = float(raw)
            self._wavelength_nm_cache = val * 1e9 if val < 10.0 else val
        except Exception:
            self._wavelength_nm_cache = float("nan")

        self.operations.update(
            {
                "start_logging": self.start_logging,
                "stop_logging": self.stop_logging,
                "clear_log": self.clear_log,
                "save_csv": self.save_csv,
                "snapshot": self.snapshot,
            }
        )
        atexit.register(self.close)

    def close(self) -> None:
        self.stop_logging()
        if self._instr is not None:
            with contextlib.suppress(Exception):
                self._w(CMD_DISABLE_CALC)
                self._w(CMD_DISABLE_ROTATION)
                _ = self._q(QRY_IS_CALC_ENABLED)
                _ = self._q(QRY_IS_ROTATION_ENABLED)
            with contextlib.suppress(Exception):
                self._instr.close()
            self._instr = None
        if self._rm is not None:
            with contextlib.suppress(Exception):
                self._rm.close()
            self._rm = None

    @property
    def info(self) -> PAX1000IR2Info:
        return PAX1000IR2Info(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            hw_status={"connected": self._instr is not None},
            wavelength_nm=self._wavelength_nm_cache,
            last_theta_deg=self._last_theta_deg,
            last_eta_deg=self._last_eta_deg,
            last_dop=self._last_dop,
            last_power_w=self._last_power_w,
            logging_rows=len(self.data_log_dataframe),
        )

    @property
    @log_parameter
    def wavelength_nm(self) -> float:
        return self._wavelength_nm_cache

    @log_operation
    def snapshot(self) -> dict[str, float]:
        if self._instr is None:
            raise DeviceNotStartedError("Start the device first.")
        raw = self._q(QRY_LATEST)

        tokens = [p for p in raw.replace(";", ",").split(",") if p]
        vals: list[float | str] = []
        for t in tokens:
            try:
                vals.append(float(t))
            except Exception:
                vals.append(t)

        def getf(i: int) -> float:
            try:
                v = vals[i]
                return float(v) if isinstance(v, (float, int)) else float(str(v))
            except Exception:
                return float("nan")

        self._last_theta_deg = getf(9)
        self._last_eta_deg = getf(10)
        self._last_dop = getf(11)
        self._last_power_w = getf(12)

        return {
            "pax_theta_deg": self._last_theta_deg,
            "pax_eta_deg": self._last_eta_deg,
            "pax_dop": self._last_dop,
            "pax_power_w": self._last_power_w,
            "pax_wavelength_nm": self._wavelength_nm_cache,
        }

    @log_operation
    def start_logging(self, interval_sec: float = 0.2) -> None:
        if self._instr is None:
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
                                    "elapsed_sec": 0.0
                                    if self.log_start_time_perf_counter is None
                                    else now - self.log_start_time_perf_counter,
                                    "iso_timestamp": _dt.datetime.now(tz=_dt.UTC).isoformat(),
                                    "pax_theta_deg": row["pax_theta_deg"],
                                    "pax_eta_deg": row["pax_eta_deg"],
                                    "pax_power_w": row["pax_power_w"],
                                    "pax_dop": row["pax_dop"],
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
