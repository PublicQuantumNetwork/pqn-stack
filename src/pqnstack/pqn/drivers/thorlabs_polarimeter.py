from __future__ import annotations

import atexit
import contextlib
import logging
import time
from dataclasses import dataclass
from dataclasses import field
from typing import Any

import numpy as np
import pyvisa
from pyvisa.errors import Error as VisaError

from pqnstack.base.errors import DeviceNotStartedError
from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import log_operation
from pqnstack.base.instrument import log_parameter

logger = logging.getLogger(__name__)

USB_FILTER = "USB?*::INSTR"
CMD_ENABLE_CALC = "SENS:CALC 1"
CMD_ENABLE_ROTATION = "INP:ROT:STAT 1"
CMD_DISABLE_CALC = "SENS:CALC 0"
CMD_DISABLE_ROTATION = "INP:ROT:STAT 0"
CMD_SET_WAVELENGTH_METERS = "SENS:CORR:WAV"
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
    hw_address: str
    parameters: set[str] = field(default_factory=set)
    operations: dict[str, Any] = field(default_factory=dict)

    pax_id_contains: str | None = None
    pax_idn_contains: str = "PAX1000"

    _rm: Any | None = field(default=None, init=False, repr=False)
    _instr: Any | None = field(default=None, init=False, repr=False)
    _timeout_ms: int = field(default=3000, init=False, repr=False)

    _wavelength_nm_cache: float = field(default=np.nan, init=False)
    _last_theta_deg: float = field(default=np.nan, init=False)
    _last_eta_deg: float = field(default=np.nan, init=False)
    _last_dop: float = field(default=np.nan, init=False)
    _last_power_w: float = field(default=np.nan, init=False)

    def _write(self, cmd: str) -> None:
        if self._instr is None:
            msg = "Start the device first."
            raise DeviceNotStartedError(msg)
        instr: Any = self._instr
        try:
            instr.write(f"{cmd}\n")
        except (VisaError, OSError):
            with contextlib.suppress(VisaError, OSError):
                instr.write(cmd)

    def _query(self, cmd: str) -> str:
        if self._instr is None:
            msg = "Start the device first."
            raise DeviceNotStartedError(msg)
        instr: Any = self._instr
        try:
            instr.write(f"{cmd}\n")
            return str(instr.read()).strip()
        except (VisaError, OSError):
            try:
                return str(instr.query(cmd)).strip()
            except (VisaError, OSError):
                return ""

    def _list_usb_resources(self) -> tuple[str, ...]:
        assert self._rm is not None
        try:
            return self._rm.list_resources(USB_FILTER)  # type: ignore[no-any-return]
        except VisaError as exc:
            msg = f"VISA resource discovery failed: {exc}"
            raise FileNotFoundError(msg) from exc

    def _filter_candidates(self, resources: tuple[str, ...]) -> tuple[str, ...]:
        if self.pax_id_contains:
            return tuple(r for r in resources if self.pax_id_contains in r)
        return resources

    def _probe_idn(self, resource_name: str) -> str:
        assert self._rm is not None
        try:
            with self._rm.open_resource(resource_name) as resource_handle:
                visa_resource: Any = resource_handle  # vendor object lacks type stubs
                visa_resource.timeout = self._timeout_ms
                try:
                    visa_resource.write(f"{QRY_IDN}\n")
                    return str(visa_resource.read()).strip()
                except (VisaError, OSError):
                    try:
                        return str(visa_resource.query(QRY_IDN)).strip()
                    except (VisaError, OSError):
                        return ""
        except VisaError as exc:
            logger.debug("Resource probe failed for %s: %s", resource_name, exc)
            return ""

    def _discover_resource(self) -> str:
        resources = self._filter_candidates(self._list_usb_resources())

        if not resources:
            msg = "No USB VISA resources matched filter."
            raise FileNotFoundError(msg)

        if len(resources) == 1 and not self.pax_idn_contains:
            return resources[0]

        idn_substring = self.pax_idn_contains or ""
        matched = [r for r in resources if (not idn_substring) or (idn_substring in self._probe_idn(r))]

        if len(matched) != 1:
            msg = "PAX discovery ambiguous or no match."
            raise FileNotFoundError(msg)
        return matched[0]

    def _open_resource(self, resource_name: str) -> None:
        assert self._rm is not None
        try:
            self._instr = self._rm.open_resource(resource_name)
            self._instr.timeout = self._timeout_ms
        except VisaError as exc:
            self._instr = None
            msg = f"Failed to open VISA resource {resource_name}: {exc}"
            raise RuntimeError(msg) from exc

    def _write_and_confirm(self, set_cmd: str, qry_cmd: str, expect: str | float) -> bool:
        try:
            self._write(set_cmd)
        except DeviceNotStartedError:
            return False
        expected_prefix = str(expect)
        last_response = ""
        for _ in range(10):
            try:
                last_response = self._query(qry_cmd)
            except DeviceNotStartedError:
                last_response = ""
            if last_response.startswith(expected_prefix):
                return True
            time.sleep(0.05)
        return False

    def _init_settings(self) -> None:
        calc_ok = self._write_and_confirm(CMD_ENABLE_CALC, QRY_IS_CALC_ENABLED, 1)
        rot_ok = self._write_and_confirm(CMD_ENABLE_ROTATION, QRY_IS_ROTATION_ENABLED, 1)
        if not (calc_ok and rot_ok):
            with contextlib.suppress(Exception):
                self._write_and_confirm(CMD_DISABLE_CALC, QRY_IS_CALC_ENABLED, 0)
                self._write_and_confirm(CMD_DISABLE_ROTATION, QRY_IS_ROTATION_ENABLED, 0)
            msg = "PAX setup failed to enable calc/rotation."
            raise RuntimeError(msg)

    def _read_wavelength_cache(self) -> None:
        try:
            raw_value = self._query(QRY_WAVELENGTH_METERS)
            value_m = float(raw_value)
            self._wavelength_nm_cache = value_m * 1e9
        except (ValueError, TypeError):
            self._wavelength_nm_cache = float("nan")

    @log_operation
    def set_wavelength_nm(self, wavelength_nm: float) -> None:
        try:
            value_m = float(wavelength_nm) * 1e-9
        except (TypeError, ValueError) as exc:
            msg = f"Invalid wavelength: {wavelength_nm}"
            raise ValueError(msg) from exc
        self._write(f"{CMD_SET_WAVELENGTH_METERS} {value_m}")
        self._read_wavelength_cache()

    def start(self) -> None:
        if self._instr is not None:
            return
        try:
            self._rm = pyvisa.ResourceManager("@py")
        except Exception as exc:
            msg = f"VISA backend not available: {exc}"
            raise RuntimeError(msg) from exc

        resource_name = self.hw_address or self._discover_resource()
        self._open_resource(resource_name)
        self._init_settings()
        self._read_wavelength_cache()

        self.operations.update(
            {
                "read": self.read,
                "set_wavelength_nm": self.set_wavelength_nm,
            }
        )
        atexit.register(self.close)

    def close(self) -> None:
        if self._instr is not None:
            with contextlib.suppress(Exception):
                self._write(CMD_DISABLE_CALC)
                self._write(CMD_DISABLE_ROTATION)
                _ = self._query(QRY_IS_CALC_ENABLED)
                _ = self._query(QRY_IS_ROTATION_ENABLED)
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
        )

    @property
    @log_parameter
    def wavelength_nm(self) -> float:
        return self._wavelength_nm_cache

    @log_operation
    def read(self) -> dict[str, float]:
        if self._instr is None:
            msg = "Start the device first."
            raise DeviceNotStartedError(msg)
        raw_reply = self._query(QRY_LATEST)

        token_strs = [p for p in raw_reply.replace(";", ",").split(",") if p]
        parsed_values: list[float | str] = []
        for token_str in token_strs:
            try:
                parsed_values.append(float(token_str))
            except (ValueError, TypeError):
                parsed_values.append(token_str)

        def get_float_at(index: int) -> float:
            try:
                value = parsed_values[index]
                return float(value) if isinstance(value, (float, int)) else float(str(value))
            except (ValueError, TypeError, IndexError):
                return float("nan")

        self._last_theta_deg = get_float_at(9)
        self._last_eta_deg = get_float_at(10)
        self._last_dop = get_float_at(11)
        self._last_power_w = get_float_at(12)

        return {
            "pax_theta_deg": self._last_theta_deg,
            "pax_eta_deg": self._last_eta_deg,
            "pax_dop": self._last_dop,
            "pax_power_w": self._last_power_w,
            "pax_wavelength_nm": self._wavelength_nm_cache,
        }
