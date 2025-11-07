from __future__ import annotations

import atexit
import contextlib
import logging
import os
import time
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import numpy as np

from pqnstack.base.errors import DeviceNotStartedError
from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import log_operation
from pqnstack.base.instrument import log_parameter

if TYPE_CHECKING:
    from collections.abc import Callable

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

    def _query(self, cmd: str, *, max_bytes: int = 4096, read: bool = True) -> str:
        data = (cmd if cmd.endswith("\n") else cmd + "\n").encode("ascii", "ignore")
        total = 0
        while total < len(data):
            n = os.write(fd, data[total:])
            if n <= 0:
                msg = "usbtmc write failed"
                raise TimeoutError(msg)
            total += n
        if not read:
            return ""
        deadline = time.monotonic() + self._timeout_sec
        chunks: list[bytes] = []
        while True:
            if time.monotonic() > deadline:
                msg = "usbtmc read timeout"
                raise TimeoutError(msg)
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
        except (ValueError, IndexError, TimeoutError, OSError, DeviceNotStartedError):
            return float("nan")

    def start(self) -> None:
        if not Path(self.hw_address).exists():
            msg = f"USBTMC node not found: {self.hw_address}"
            raise FileNotFoundError(msg)
        if not os.access(self.hw_address, os.R_OK | os.W_OK):
            msg = f"No rw access to {self.hw_address}"
            raise PermissionError(msg)
        if self.file_descriptor is None:
            self.file_descriptor = os.open(self.hw_address, os.O_RDWR)
        with contextlib.suppress(Exception):
            self._query("*CLS", read=False)
        if np.isfinite(self._wavelength_nm_cache):
            try:
                self._query(f"SENSE:CORR:WAV {self._wavelength_nm_cache}NM", read=False)
            except (TimeoutError, OSError, DeviceNotStartedError) as exc:
                logger.warning("failed to set wavelength to %s nm: %s", self._wavelength_nm_cache, exc)
        self._wavelength_nm_cache = self._read_float("SENSE:CORR:WAV?")
        self.operations.update(
            {
                "read": self.read,
            }
        )
        atexit.register(self.close)

    def close(self) -> None:
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
            except (TimeoutError, OSError, DeviceNotStartedError) as exc:
                logger.warning("failed to set wavelength to %s nm: %s", self._wavelength_nm_cache, exc)

    @property
    @log_parameter
    def power_w(self) -> float:
        raw = self._read_float("MEAS:POW?")
        if not np.isfinite(raw):
            msg = "unexpected PM100D power response"
            raise ValueError(msg)
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
    def read(self) -> dict[str, float]:
        raw = self.power_w
        ref = self.ref_w()
        total = raw - ref if np.isfinite(ref) else raw
        return {"pm1_w": raw, "pm1_ref_w": ref, "pm1_total_w": total, "pax_wavelength_nm": self._wavelength_nm_cache}
