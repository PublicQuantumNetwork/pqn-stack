import serial
import struct
import time
import logging
from pqnstack.base.driver import DeviceDriver, DeviceInfo, DeviceClass, DeviceStatus, log_operation, log_parameter
from pqnstack.base.errors import DeviceNotStartedError

logger = logging.getLogger(__name__)

class ZEDF9TTimingDevice(DeviceDriver):
    """
    Device driver for the u-blox ZED-F9T GNSS timing receiver.

    Provides methods for configuring and managing precision timing functionalities,
    including setting timepulse (PPS) frequency and pulse length, and configuring the survey-in
    process to establish a highly accurate fixed antenna position for optimal timing accuracy.
    """
    DEVICE_CLASS = DeviceClass.TIMETAGR

    def __init__(self, name: str, desc: str, address: str = '/dev/ttyACM0', baudrate: int = 38400):
        """
        Initializes the ZED-F9T timing device driver instance.

        :param name: Human-readable name of the device.
        :param desc: Description of the device.
        :param address: Serial port address of the device (default '/dev/ttyACM0').
        :param baudrate: Communication baud rate (default 38400).
        """
        super().__init__(name, desc, address)
        self.baudrate = baudrate
        self.serial = None

        self.parameters.update({"pulse_period_us", "pulse_length_us", "survey_in_duration_s", "survey_in_accuracy_m"})

        # Default configuration parameters
        self._pulse_period_us = 1  # Hz
        self._pulse_length_us = 100_000_000  # 100 ms pulse length
        self._survey_in_duration_s = 300  # Minimum survey-in duration (seconds)
        self._survey_in_accuracy_m = 5.0  # Target survey-in accuracy (meters)

    def info(self) -> DeviceInfo:
        """
        Provides detailed device information.

        :return: DeviceInfo object containing device metadata and status.
        """
        return DeviceInfo(
            name=self.name,
            desc=self.desc,
            address=self.address,
            dtype=self.DEVICE_CLASS,
            status=self.status
        )

    @log_operation
    def start(self) -> None:
        """
        Starts communication with the ZED-F9T via the configured USB serial interface.

        Initializes the serial connection, triggers the default survey-in procedure,
        and configures the initial timepulse settings.
        """
        self.serial = serial.Serial(self.address, self.baudrate, timeout=1)
        time.sleep(2)  # Allow serial connection to establish
        self.status = DeviceStatus.READY
        logger.info("ZED-F9T module initialized and serial communication established.")

        self.configure_survey_in(self._survey_in_duration_s, self._survey_in_accuracy_m)
        self.configure_timepulse(0, self._pulse_period_us, self._pulse_length_us)

    @log_operation
    def close(self) -> None:
        """
        Closes the serial communication with the ZED-F9T device.

        Ensures that the serial connection is properly terminated to free system resources.
        """
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.status = DeviceStatus.OFF
        logger.info("ZED-F9T serial connection safely closed.")

    def _send_ubx(self, class_id: int, msg_id: int, payload: bytes) -> None:
        """
        Sends a UBX protocol binary message to the device.

        :param class_id: UBX message class identifier.
        :param msg_id: UBX message ID within the class.
        :param payload: Payload of the UBX message as bytes.
        """
        header = b'\xB5\x62' + bytes([class_id, msg_id])
        length = struct.pack('<H', len(payload))
        msg = header + length + payload
        checksum = self._ubx_checksum(msg[2:])
        full_msg = msg + checksum
        self.serial.write(full_msg)

    @staticmethod
    def _ubx_checksum(msg: bytes) -> bytes:
        """
        Calculates the UBX protocol checksum for a given message.

        :param msg: UBX message (excluding sync chars).
        :return: Checksum as two-byte sequence.
        """
        ck_a, ck_b = 0, 0
        for b in msg:
            ck_a = (ck_a + b) & 0xFF
            ck_b = (ck_b + ck_a) & 0xFF
        return bytes([ck_a, ck_b])

    @log_operation
    def configure_timepulse(self, tp_idx: int, period_us: int, length_us: int) -> None:
        """
        Configures the timepulse output with explicitly provided period and pulse length in microseconds.

        :param tp_idx: Index of the timepulse (0 for TIMEPULSE1, 1 for TIMEPULSE2).
        :param period_us: Period between pulses in microseconds.
        :param length_us: Length of each pulse in microseconds.
        """
        if not self.serial or not self.serial.is_open:
            raise DeviceNotStartedError("Device must be started before configuring timepulse.")

        # Construct payload explicitly as observed from u-center captures
        payload = bytearray(32)
        payload[0] = tp_idx                    # Timepulse selection (0 or 1)
        payload[1] = 0x01                      # Version
        payload[4:8] = (50).to_bytes(4, 'little')  # antCableDelay, fixed at 50ns (0x32)
        payload[8:12] = (1_000_000).to_bytes(4, 'little')  # rfGroupDelay, fixed (0x0F4240)

        # Set frequency/period (microseconds)
        payload[12:16] = period_us.to_bytes(4, 'little')
        payload[16:20] = period_us.to_bytes(4, 'little')  # Same for locked/unlocked

        # Explicit pulse length (microseconds)
        payload[20:24] = length_us.to_bytes(4, 'little')
        payload[24:28] = length_us.to_bytes(4, 'little')  # Same for locked/unlocked

        payload[28:32] = (247).to_bytes(4, 'little')  # userConfigDelay (fixed at 247)

        # Send UBX message
        self._send_ubx(0x06, 0x31, payload)
        logger.info(f"Configured TP{tp_idx + 1}: Period={period_us}us, Pulse Length={length_us}us")

    @property
    @log_parameter
    def pulse_period_us(self) -> float:
        """
        Current frequency of the timepulse output in Hz.

        :return: Pulse frequency in Hz.
        """
        return self._pulse_period_us

    @property
    @log_parameter
    def pulse_period_us(self) -> int:
        """Current pulse period in microseconds."""
        return self._pulse_period_us

    @pulse_period_us.setter
    @log_parameter
    def pulse_period_us(self, period_us: int) -> None:
        """Sets the pulse period in microseconds and updates the device immediately."""
        self._pulse_period_us = period_us
        self.configure_timepulse(0, self._pulse_period_us, self._pulse_length_us)

    @property
    @log_parameter
    def pulse_length_us(self) -> int:
        """Current pulse length in microseconds."""
        return self._pulse_length_us

    @pulse_length_us.setter
    @log_parameter
    def pulse_length_us(self, length_us: int) -> None:
        """Sets the pulse length in microseconds and updates the device immediately."""
        self._pulse_length_us = length_us
        self.configure_timepulse(0, self._pulse_period_us, self._pulse_length_us)


    @log_operation
    def configure_survey_in(self, duration_s: int, accuracy_m: float) -> None:
        """
        Initiates and configures the survey-in process.

        The survey-in determines a fixed antenna position for optimal timing accuracy.

        :param duration_s: Minimum duration of the survey-in (seconds).
        :param accuracy_m: Target horizontal position accuracy (meters).
        """
        if not self.serial or not self.serial.is_open:
            raise DeviceNotStartedError("Device must be started before configuring survey-in.")

        payload = struct.pack('<B3xII',
                              1,  # Survey-in mode enabled
                              int(duration_s),
                              int(accuracy_m * 10000))  # Accuracy specified in 0.1 mm units

        self._send_ubx(0x06, 0x71, payload)
        logger.info(f"Survey-in started: Duration={duration_s}s, Accuracy={accuracy_m}m")


    @property
    @log_parameter
    def survey_in_duration_s(self) -> int:
        """
        Minimum duration set for the survey-in process in seconds.

        :return: Duration in seconds.
        """
        return self._survey_in_duration_s

    @survey_in_duration_s.setter
    @log_parameter
    def survey_in_duration_s(self, duration_s: int) -> None:
        """
        Sets and initiates the survey-in process with a new minimum duration.

        :param duration_s: Survey-in duration in seconds.
        """
        self._survey_in_duration_s = duration_s
        self.configure_survey_in(self._survey_in_duration_s, self._survey_in_accuracy_m)

    @property
    @log_parameter
    def survey_in_accuracy_m(self) -> float:
        """
        Target horizontal accuracy set for the survey-in process in meters.

        :return: Accuracy in meters.
        """
        return self._survey_in_accuracy_m

    @survey_in_accuracy_m.setter
    @log_parameter
    def survey_in_accuracy_m(self, accuracy_m: float) -> None:
        """
        Sets and initiates the survey-in process with a new target accuracy.

        :param accuracy_m: Target accuracy in meters.
        """
        self._survey_in_accuracy_m = accuracy_m
        self.configure_survey_in(self._survey_in_duration_s, self._survey_in_accuracy_m)

