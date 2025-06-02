import logging
import math
import struct
import time

import serial

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation
from pqnstack.base.driver import log_parameter
from pqnstack.base.errors import DeviceNotStartedError

logger = logging.getLogger(__name__)
MAX_DUTY_PERCENT = 100.0

"""
stty -F /dev/ttyACM0 to check port
"""


class ZEDF9TTimingDevice(DeviceDriver):
    """
    Device driver for the u-blox ZED-F9T timing module.

    configuring TimePulse via the reverse-engineered UBX-CFG-TP packet.
    """

    DEVICE_CLASS = DeviceClass.TIMETAGR

    def __init__(self, name: str, desc: str, address: str = "/dev/ttyACM0", baudrate: int = 38400):
        super().__init__(name, desc, address)
        self.baudrate = baudrate
        self.serial = None

        self.parameters.update({"frequency_hz", "duty_cycle_percent"})
        self._frequency_hz = 1
        self._duty_cycle_percent = 50.0

    def info(self) -> DeviceInfo:
        return DeviceInfo(
            name=self.name, desc=self.desc, address=self.address, dtype=self.DEVICE_CLASS, status=self.status
        )

    @log_operation
    def start(self) -> None:
        self.serial = serial.Serial(self.address, self.baudrate, timeout=1)
        time.sleep(2)
        self.status = DeviceStatus.READY
        self.configure_pulse(0, self._frequency_hz, self._duty_cycle_percent)

    @log_operation
    def close(self) -> None:
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.status = DeviceStatus.OFF

    @staticmethod
    def _ubx_fletcher(data: bytes) -> bytes:
        ck_a = ck_b = 0
        for b in data:
            ck_a = (ck_a + b) & 0xFF
            ck_b = (ck_b + ck_a) & 0xFF
        return bytes((ck_a, ck_b))

    @staticmethod
    def _build_tp_command(tp_idx: int, frequency: int, duty_pct: float) -> bytes:
        prefix = b"\x00\x00"
        ubx_hdr = b"\xb5\x62\x06\x31" + struct.pack("<H", 32)

        tp_byte = struct.pack("<B", tp_idx & 0xFF)
        enable = b"\x01"
        reserved6 = b"\x00" * 6
        freq_le = struct.pack("<I", frequency)
        lock_le = freq_le

        frac = (1 << 32) - 1 if duty_pct >= MAX_DUTY_PERCENT else math.ceil(duty_pct / 100.0 * (1 << 32)) & 4294967295
        duty_le = struct.pack("<I", frac)
        lock_duty = duty_le

        ramp_up = b"\x00" * 4
        ramp_down = bytes.fromhex("6F000000")

        payload = tp_byte + enable + reserved6 + freq_le + lock_le + duty_le + lock_duty + ramp_up + ramp_down

        checksum = ZEDF9TTimingDevice._ubx_fletcher(ubx_hdr[2:] + payload)
        return prefix + ubx_hdr + payload + checksum

    @log_operation
    def configure_pulse(self, tp_idx: int, frequency_hz: int, duty_cycle_percent: float) -> None:
        if not self.serial or not self.serial.is_open:
            msg = "Device must be started first."
            raise DeviceNotStartedError(msg)

        packet = self._build_tp_command(tp_idx, frequency_hz, duty_cycle_percent)
        self.serial.write(packet)

        logger.info("Configured TP%s: Frequency=%d Hz, Duty=%.1f%%", tp_idx, frequency_hz, duty_cycle_percent)

    @property
    @log_parameter
    def frequency_hz(self) -> int:
        return self._frequency_hz

    @frequency_hz.setter
    @log_parameter
    def frequency_hz(self, frequency_hz: int) -> None:
        self._frequency_hz = frequency_hz
        self.configure_pulse(0, self._frequency_hz, self._duty_cycle_percent)

    @property
    @log_parameter
    def duty_cycle_percent(self) -> float:
        return self._duty_cycle_percent

    @duty_cycle_percent.setter
    @log_parameter
    def duty_cycle_percent(self, duty_cycle_percent: float) -> None:
        self._duty_cycle_percent = duty_cycle_percent
        self.configure_pulse(0, self._frequency_hz, self._duty_cycle_percent)

    @log_operation
    def set_period(self, ns: float) -> None:
        self.frequency_hz = int(1e9 / ns)
