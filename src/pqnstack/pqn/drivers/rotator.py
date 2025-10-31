# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

import logging
import time
from dataclasses import dataclass
from dataclasses import field
from typing import Protocol
from typing import runtime_checkable

import serial
from thorlabs_apt_device import TDC001

from pqnstack.base.errors import DeviceNotStartedError
from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import log_parameter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RotatorInfo(InstrumentInfo):
    degrees: float = 0.0
    offset_degrees: float = 0.0


@runtime_checkable
@dataclass(slots=True)
class RotatorInstrument(Instrument, Protocol):
    offset_degrees: float = 0.0

    def __post_init__(self) -> None:
        self.operations["move_to"] = self.move_to
        self.operations["move_by"] = self.move_by

        self.parameters.add("degrees")

    @property
    @log_parameter
    def degrees(self) -> float: ...

    @degrees.setter
    @log_parameter
    def degrees(self, degrees: float) -> None: ...

    def move_to(self, angle: float) -> None:
        """Move the rotator to the specified angle."""
        self.degrees = angle

    def move_by(self, angle: float) -> None:
        """Move the rotator by the specified angle."""
        self.degrees += angle


@dataclass(slots=True)
class APTRotator(RotatorInstrument):
    _degrees: float = field(default=0.0, init=False)
    _device: TDC001 = field(init=False, repr=False)
    _encoder_units_per_degree: float = field(default=86384 / 45, init=False, repr=False)

    def start(self) -> None:
        # Additional setup for APT Rotator
        self._device = TDC001(serial_number=self.hw_address)
        offset_eu = round(self.offset_degrees * self._encoder_units_per_degree)

        # NOTE: Velocity units seem to not match position units
        # (Device does not actually move at 1000 deg/s...)
        # 500 is noticeably slower, but more than 1000 doesn't seem faster
        vel = round(1000 * self._encoder_units_per_degree)

        self._device.set_home_params(velocity=vel, offset_distance=offset_eu)
        self._device.set_velocity_params(vel, vel)
        time.sleep(0.5)
        self._wait_for_stop()

    def close(self) -> None:
        if self._device is not None:
            logger.info("Closing APT Rotator")
            self._device.close()

    @property
    def info(self) -> RotatorInfo:
        return RotatorInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            hw_status=self._device.status,
            degrees=self.degrees,
            offset_degrees=self.offset_degrees,
        )

    def _wait_for_stop(self) -> None:
        if self._device is None:
            msg = "Start the device before setting parameters"
            raise DeviceNotStartedError(msg)

        try:
            time.sleep(0.5)
            while (
                self._device.status["moving_forward"]
                or self._device.status["moving_reverse"]
                or self._device.status["jogging_forward"]
                or self._device.status["jogging_reverse"]
            ):
                time.sleep(0.1)
        except KeyboardInterrupt:
            self._device.stop(immediate=True)

    @property
    def degrees(self) -> float:
        return self._degrees

    @degrees.setter
    def degrees(self, degrees: float) -> None:
        self._set_degrees_unsafe(degrees)
        self._wait_for_stop()

    def _set_degrees_unsafe(self, degrees: float) -> None:
        self._degrees = degrees
        self._device.move_absolute(int(degrees * self._encoder_units_per_degree))


@dataclass(slots=True)
class SerialRotator(RotatorInstrument):
    _degrees: float = 0.0  # The hardware doesn't support position tracking
    _conn: serial.Serial = field(init=False, repr=False)

    def start(self) -> None:
        self._conn = serial.Serial(self.hw_address, baudrate=115200, timeout=1)
        self._conn.write(b"open_channel")
        self._conn.read(100)
        self._conn.write(b"motor_ready")
        self._conn.read(100)

        self.degrees = self.offset_degrees

    def close(self) -> None:
        self.degrees = 0
        self._conn.close()

    @property
    def info(self) -> RotatorInfo:
        return RotatorInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            degrees=self.degrees,
            offset_degrees=self.offset_degrees,
        )

    @property
    def degrees(self) -> float:
        return self._degrees

    @degrees.setter
    def degrees(self, degrees: float) -> None:
        self._conn.write(f"SRA {degrees}".encode())
        self._degrees = degrees
        _ = self._conn.readline().decode()


@dataclass(slots=True)
class ELL14KRotator(RotatorInstrument):
    """
    Implement a Thorlabs Elliptec ELL14K rotator over the Elliptec ASCII protocol.

    Inputs:
      name: Logical name.
      desc: Description.
      hw_address: Serial port path.
      offset_degrees: Static mechanical zero offset in degrees.
      addr_hex: One-hex-digit device address string in [0-9A-F]. If unknown, leave "0".
      block_while_moving: If True, motion calls wait until motion stops.
      timeout_s: I/O timeout in seconds.
      handshake_retries: Maximum discovery passes across candidate addresses.
      home_on_start: If True, homes after successful handshake.
      home_dir_cw: If True, home clockwise; otherwise counterclockwise.
    """

    name: str
    desc: str
    hw_address: str
    offset_degrees: float = 0.0
    addr_hex: str = "0"
    block_while_moving: bool = True
    timeout_s: float = 2.5
    handshake_retries: int = 3
    home_on_start: bool = False
    home_dir_cw: bool = True

    _degrees: float = 0.0
    _conn: serial.Serial = field(init=False, repr=False)
    _ppd: float = field(init=False, default=0.0, repr=False)
    _travel_deg: int = field(init=False, default=360, repr=False)
    _raw_in: str = field(init=False, default="", repr=False)

    _IN_MIN_PARTS: int = field(init=False, default=9, repr=False)
    _IN_FIXED_MIN_LEN: int = field(init=False, default=30, repr=False)
    _WAIT_TIMEOUT_S: float = field(init=False, default=30.0, repr=False)
    _DRAIN_SLEEP_S: float = field(init=False, default=0.005, repr=False)

    def start(self) -> None:
        """Open, identify, scale, and synchronize."""
        self._open_port()
        parsed, addr = self._identify()
        self.addr_hex = addr
        self._init_scale(parsed)
        self._maybe_home()
        self._sync_angle()

    def close(self) -> None:
        """Return to zero and close the port."""
        try:
            self.degrees = 0.0
        except (OSError, RuntimeError) as exc:
            logger.warning("ell14k.close.zero_failed err=%r", exc)
        try:
            self._conn.close()
        except (OSError, RuntimeError) as exc:
            logger.warning("ell14k.close.serial_failed err=%r", exc)

    @property
    def info(self) -> RotatorInfo:
        """
        Return a snapshot of metadata and current angle.

        Outputs:
          RotatorInfo with name, description, port, degrees, and offset.
        """
        return RotatorInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            degrees=self.degrees,
            offset_degrees=self.offset_degrees,
        )

    @property
    def degrees(self) -> float:
        """
        Get the cached current angle in degrees referenced to the configured offset.

        Outputs:
          Float in [0, 360).
        """
        return self._degrees

    @degrees.setter
    def degrees(self, degrees: float) -> None:
        """
        Move to an absolute mechanical angle in degrees.

        Inputs:
          degrees: Target angle referenced to user offset. Wrapped into [0, 360).
        """
        target = (degrees + self.offset_degrees) % 360.0
        eu = self._deg_to_eu(target)
        cmd = f"{self.addr_hex}ma{eu:08X}"
        gs0 = self._get_status()
        t0 = time.time()
        self._send(cmd)
        logger.info("ell14k.move_to tx=%s target_deg=%.9f eu=%08X status_before=%r", cmd, target, eu, gs0)
        if self.block_while_moving:
            self._wait_for_completion()
        pos = self._get_position_eu()
        gs1 = self._get_status()
        if pos is None:
            self._degrees = degrees % 360.0
            logger.warning(
                "ell14k.move_to.readback_none kept_req_deg=%.9f elapsed=%.3fs status_after=%r",
                degrees,
                time.time() - t0,
                gs1,
            )
            return
        rb = (self._eu_to_deg(pos) - self.offset_degrees) % 360.0
        self._degrees = rb
        logger.info(
            "ell14k.move_to.readback po_eu=%08X rb_deg=%.9f elapsed=%.3fs status_after=%r",
            pos,
            rb,
            time.time() - t0,
            gs1,
        )

    def _open_port(self) -> None:
        """Open and prime the serial link."""
        logger.info("ell14k.start port=%s req_addr=%s timeout=%.2f", self.hw_address, self.addr_hex, self.timeout_s)
        self._conn = serial.Serial(
            self.hw_address,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout_s,
            write_timeout=self.timeout_s,
            rtscts=False,
            dsrdtr=False,
            xonxoff=False,
        )
        self._conn.reset_input_buffer()
        self._conn.reset_output_buffer()
        self._send("")
        self._drain_reads(0.05)

    def _identify(self) -> tuple[dict[str, str], str]:
        """
        Identify the device and resolve the active address.

        Outputs:
          Tuple of (parsed IN fields, confirmed address).
        """
        addrs = [self.addr_hex.upper()] + [a for a in "0123456789ABCDEF" if a != self.addr_hex.upper()]
        ok_addr: str | None = None
        parsed: dict[str, str] | None = None
        for attempt in range(1, self.handshake_retries + 1):
            for a in addrs:
                self._drain_reads(0.01)
                t0 = time.time()
                self._send(f"{a}in")
                line = self._readline_ascii()
                dt = time.time() - t0
                logger.info(
                    "ell14k.in attempt=%d addr=%s rx=%r latency=%.3fs in_wait=%d",
                    attempt,
                    a,
                    line,
                    dt,
                    int(self._conn.in_waiting),
                )
                if not line or not line.startswith(f"{a}IN"):
                    continue
                self._raw_in = line
                try:
                    parsed = self._parse_in(line)
                except ValueError:
                    logger.exception("ell14k.in.parse addr=%s line=%r", a, line)
                    continue
                ok_addr = a
                break
            if ok_addr:
                break
            self._send("")
            self._drain_reads(0.05)
        if not ok_addr or not parsed:
            logger.error("ell14k.start.identify_failed")
            msg = "ELL14K identify timed out"
            raise RuntimeError(msg)
        return parsed, ok_addr

    def _init_scale(self, parsed: dict[str, str]) -> None:
        """
        Initialize travel and pulses-per-degree scale.

        Inputs:
          parsed: Result of _parse_in.
        """
        self._travel_deg = int(parsed.get("travel_hex", "168"), 16) if parsed.get("travel_hex") else 360
        ppu_hex = parsed.get("pulses_per_unit_hex", "00000000")
        pulses_val = int(ppu_hex, 16) if ppu_hex else 0
        if self._travel_deg > 0 and pulses_val > 0:
            self._ppd = float(pulses_val) / float(self._travel_deg)
        else:
            self._ppd = 262144.0 / 360.0
        logger.info(
            "ell14k.scale addr=%s travel_deg=%d pulses_hex=%s pulses_val=%d ppd=%.9f raw_in=%r",
            self.addr_hex,
            self._travel_deg,
            ppu_hex,
            pulses_val,
            self._ppd,
            self._raw_in,
        )

    def _maybe_home(self) -> None:
        if not self.home_on_start:
            return
        dir_code = "0" if self.home_dir_cw else "1"
        t0 = time.time()
        self._send(f"{self.addr_hex}ho{dir_code}")
        logger.info("ell14k.home cmd=%s", f"{self.addr_hex}ho{dir_code}")
        self._wait_for_completion()
        logger.info("ell14k.home.done elapsed=%.3fs", time.time() - t0)

    def _sync_angle(self) -> None:
        """Read back position and update cached degrees."""
        pos_eu = self._get_position_eu()
        if pos_eu is not None:
            self._degrees = (self._eu_to_deg(pos_eu) - self.offset_degrees) % 360.0
        else:
            self._degrees = 0.0
        gs_after = self._get_status()
        logger.info("ell14k.start.sync degrees=%.9f status_after=%r", self._degrees, gs_after)

    def _send(self, payload: str) -> None:
        """
        Transmit a single Elliptec command with CR termination.

        Inputs:
          payload: ASCII command excluding terminator. May be empty to send CR only.
        """
        tx = (payload + "\r").encode("ascii")
        n = self._conn.write(tx)
        logger.debug("ell14k.tx bytes=%d data=%r", n, tx)

    def _readline_ascii(self) -> str | None:
        """
        Read one CRLF-terminated line as ASCII and strip line endings.

        Outputs:
          Decoded string or None on timeout.
        """
        raw = self._conn.readline()
        if not raw:
            return None
        s = raw.decode("ascii", errors="ignore").strip("\r\n")
        logger.debug("ell14k.rx line=%r", s)
        return str(s)

    def _cmd(self, cmd: str) -> list[str]:
        """
        Send one command and collect the immediate reply burst.

        Inputs:
          cmd: ASCII command without terminator.

        Outputs:
          List of decoded reply lines received before timeout or input drain.
        """
        self._send(cmd)
        lines: list[str] = []
        t0 = time.time()
        while time.time() - t0 < self.timeout_s:
            line = self._readline_ascii()
            if not line:
                break
            lines.append(line)
            if self._conn.in_waiting == 0:
                break
        logger.debug("ell14k.cmd tx=%r rx_lines=%r", cmd, lines)
        return lines

    def _drain_reads(self, duration_s: float) -> None:
        """
        Drain any pending input bytes for a fixed duration.

        Inputs:
          duration_s: Seconds to spend draining.
        """
        t0 = time.time()
        total = 0
        while time.time() - t0 < duration_s:
            n = int(self._conn.in_waiting)
            if n <= 0:
                time.sleep(self._DRAIN_SLEEP_S)
                continue
            _ = self._conn.read(n)
            total += n
        if total:
            logger.debug("ell14k.drain bytes=%d", total)

    def _parse_in(self, line: str) -> dict[str, str]:
        """
        Decode an IN identification reply in CSV or fixed-field format.

        Inputs:
          line: One IN reply line starting with '<addr>IN'.

        Outputs:
          Dict with keys: ell, sn, year, fw, hw, travel_hex, pulses_per_unit_hex.
        """
        if "," in line:
            parts = line.split(",")
            if len(parts) < self._IN_MIN_PARTS:
                msg = f"bad IN csv: {line!r}"
                raise ValueError(msg)
            return {
                "ell": parts[2],
                "sn": parts[3],
                "year": parts[4],
                "fw": parts[5],
                "hw": parts[6],
                "travel_hex": parts[7],
                "pulses_per_unit_hex": parts[8],
            }
        data = line[3:]
        if len(data) < self._IN_FIXED_MIN_LEN:
            msg = f"bad IN fixed: {line!r}"
            raise ValueError(msg)
        return {
            "ell": data[0:2],
            "sn": data[2:10],
            "year": data[10:14],
            "fw": data[14:16],
            "hw": data[16:18],
            "travel_hex": data[18:22],
            "pulses_per_unit_hex": data[22:30],
        }

    def _get_position_eu(self) -> int | None:
        """
        Query the device for the current encoder units position.

        Outputs:
          Unsigned 32-bit integer parsed from PO field, or None on failure.
        """
        reps = self._cmd(f"{self.addr_hex}gp")
        if not reps:
            logger.debug("ell14k.gp no_reply")
            return None
        rep = reps[0]
        idx = rep.find("PO")
        if idx < 0 or len(rep) < idx + 10:
            logger.debug("ell14k.gp bad_line=%r", rep)
            return None
        try:
            val = int(rep[idx + 2 : idx + 10], 16)
        except ValueError as exc:
            logger.debug("ell14k.gp parse_error line=%r err=%r", rep, exc)
            return None
        else:
            logger.debug("ell14k.gp po=%08X line=%r", val, rep)
            return val

    def _get_status(self) -> dict[str, str] | None:
        """
        Fetch the raw GS status line.

        Outputs:
          Dict with key 'raw' holding the first reply line, or None on timeout.
        """
        reps = self._cmd(f"{self.addr_hex}gs")
        if not reps:
            return None
        return {"raw": reps[0]}

    def _wait_for_completion(self) -> None:
        """Poll until motion stops or the watchdog expires."""
        t0 = time.time()
        last_po: int | None = None
        last_gs: str | None = None
        while time.time() - t0 < self._WAIT_TIMEOUT_S:
            reps = self._cmd(f"{self.addr_hex}gp")
            if reps:
                rep = reps[0]
                if "PO" in rep:
                    try:
                        pos_start = rep.find("PO") + 2
                        cur = int(rep[pos_start : pos_start + 8], 16)
                    except ValueError as exc:
                        logger.debug("ell14k.wait parse_error line=%r err=%r", rep, exc)
                    else:
                        if last_po is not None and cur == last_po:
                            logger.debug("ell14k.wait stable_po=%08X", cur)
                            return
                        last_po = cur
            gs = self._get_status()
            if gs and gs.get("raw") != last_gs:
                last_gs = gs.get("raw")
                logger.debug("ell14k.wait status=%r", last_gs)
            time.sleep(0.05)
        logger.warning("ell14k.wait timeout")

    def _deg_to_eu(self, deg: float) -> int:
        """
        Encode degrees into encoder units using the discovered scale.

        Inputs:
          deg: Angle in degrees. Wrapped into [0, 360).

        Outputs:
          Unsigned 32-bit integer within one revolution.
        """
        return round((deg % 360.0) * self._ppd) % int(self._ppd * 360.0) if self._ppd > 0 else 0

    def _eu_to_deg(self, eu: int | None) -> float:
        """
        Decode encoder units back to degrees using the discovered scale.

        Inputs:
          eu: Unsigned 32-bit integer position or None.

        Outputs:
          Angle in degrees in [0, 360). Returns 0.0 if scale unknown or input None.
        """
        if eu is None or self._ppd <= 0:
            return 0.0
        return ((eu % int(self._ppd * 360.0)) / float(self._ppd)) % 360.0
