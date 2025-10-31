# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

from __future__ import annotations

import atexit
import datetime as _dt
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import pyvisa
from ThorlabsPM100 import ThorlabsPM100
import numpy as np
import pandas as pd

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

    _device: Any = field(default=None, init=False, repr=False)
    _visa: Any = field(default=None, init=False, repr=False)

    _wavelength_nm: float = field(default=np.nan, init=False)
    _last_power_w: float = field(default=np.nan, init=False)

    _df: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(
            {
                "elapsed_sec": [],
                "iso_timestamp": [],
                "pm1_w": [],
                "interval_sec": [],
                "pax_wavelength_nm": [],
            }
        ),
        init=False,
        repr=False,
    )
    _t0: float | None = field(default=None, init=False, repr=False)
    _poll_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _poll_stop: threading.Event = field(default_factory=threading.Event, init=False, repr=False)

    def start(self) -> None:

        rm = pyvisa.ResourceManager()
        inst = rm.open_resource(self.hw_address)
        inst.timeout = 5000  # ms
        inst.read_termination = "\n"
        inst.write_termination = "\n"

        self._visa = rm
        self._device = ThorlabsPM100(inst=inst)

        if np.isfinite(self._wavelength_nm):
            self._apply_wavelength(self._wavelength_nm)

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
        try:
            if self._device is not None and hasattr(self._device, "inst"):
                self._device.inst.close()
        finally:
            self._device = None
            self._visa = None

    @property
    def info(self) -> PM100DInfo:
        return PM100DInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            hw_status={"connected": self._device is not None},
            wavelength_nm=self._wavelength_nm,
            last_power_w=self._last_power_w,
            logging_rows=int(len(self._df)),
        )

    @property
    @log_parameter
    def wavelength_nm(self) -> float:
        return self._wavelength_nm

    @wavelength_nm.setter
    @log_parameter
    def wavelength_nm(self, nm: float) -> None:
        self._wavelength_nm = float(nm)
        if self._device is not None:
            self._apply_wavelength(self._wavelength_nm)

    def _apply_wavelength(self, nm: float) -> None:
        try:
            self._device.sense.correction.wavelength = float(nm)
        except Exception as exc:
            logger.warning("Failed to set PM100D wavelength to %s nm: %s", nm, exc)

    @property
    @log_parameter
    def power_w(self) -> float:
        if self._device is None:
            raise DeviceNotStartedError("Start the device before reading power.")
        val = float(self._device.read)
        self._last_power_w = val
        return val

    @log_operation
    def snapshot(self) -> dict[str, float]:
        return {"pm1_w": self.power_w, "pax_wavelength_nm": self._wavelength_nm}

    @log_operation
    def start_logging(self, interval_sec: float = 0.2) -> None:
        if self._device is None:
            raise DeviceNotStartedError("Start the device before logging.")
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._poll_stop.clear()
        self._t0 = time.perf_counter()

        def loop() -> None:
            while not self._poll_stop.is_set():
                t_now = time.perf_counter()
                row = self.snapshot()
                self._append_row(
                    {
                        "elapsed_sec": 0.0 if self._t0 is None else t_now - self._t0,
                        "iso_timestamp": _dt.datetime.now(tz=_dt.UTC).isoformat(),
                        "pm1_w": row["pm1_w"],
                        "pax_wavelength_nm": row["pax_wavelength_nm"],
                        "interval_sec": interval_sec,
                    }
                )
                time.sleep(interval_sec)

        self._poll_thread = threading.Thread(target=loop, name=f"{self.name}-poll", daemon=True)
        self._poll_thread.start()

    @log_operation
    def stop_logging(self) -> None:
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_stop.set()
            self._poll_thread.join(timeout=2.0)

    @log_operation
    def clear_log(self) -> None:
        self._df = self._df.iloc[0:0]

    @log_operation
    def save_csv(self, path: str) -> None:
        self._df.to_csv(path, index=False)

    def _append_row(self, row: dict[str, Any]) -> None:
        self._df = pd.concat([self._df, pd.DataFrame([row])], ignore_index=True)

