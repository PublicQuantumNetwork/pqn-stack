from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any

import numpy as np
import TimeTagger
from TimeTagger import ChannelEdge
from TimeTagger import Correlation
from TimeTagger import Counter
from TimeTagger import createTimeTaggerNetwork
from TimeTagger import freeTimeTagger

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass
class MeasurementConfig:
    duration: int  # in picoseconds
    binwidth: int = 500  # in picoseconds
    channel1: int = 1
    channel2: int = 2
    dark_count: int = 0


@dataclass
class TimeTaggerInfo(DeviceInfo):
    """Metadata and current state information for the time tagger device."""

    channels_in_use: list[int] = field(default_factory=list)
    test_signal_enabled: bool = False
    test_signal_divider: int = 1
    last_measurement_rates: list[float] = field(default_factory=list)
    last_coincidence_window_ps: int = 0


class TimeTaggerDevice(DeviceDriver):
    """
    Abstract base class for a time tagger device.

    Inherit from this class to implement specialized time tagger drivers, such as one for Swabian Instruments hardware.
    """

    DEVICE_CLASS = DeviceClass.TIMETAGR

    @abstractmethod
    def info(self) -> TimeTaggerInfo:
        """Return a dataclass containing metadata about the time tagger."""

    @abstractmethod
    def close(self) -> None:
        """Shut down and release resources for the time tagger."""

    @abstractmethod
    def start(self) -> None:
        """
        Initialize and start the time tagger hardware.

        May optionally set up channel usage, test signal parameters, etc.
        """
        #    @abstractmethod
        #    def measure_coincidence(
        #        self, groups: list[tuple[int, ...]], measurement_time: float = 5.0, coincidence_window_ps: int = 10000
        #    ) -> None:
        """Perform a coincidence-counting measurement on a given list of channel groups, for the specified real-time measurement duration and coincidence window."""

    @abstractmethod
    def measure_coincidence(self, channel1: int, channel2: int, binwidth_ps: int, measurement_duration_ps: int) -> int:
        "Measaures the coincidence between input channels."

    @abstractmethod
    def measure_countrate(self, channels: list[int], binwidth_ps: int) -> list[int]:
        "Measaures the singles counts on input channels."


class SwabianTimeTagger(TimeTaggerDevice):
    def __init__(
        self,
        name: str,
        desc: str,
        address: str,
        channels_to_use: int = 10,
    ) -> None:
        """
        Control the Swabian time tagger using a wrapper class.

        :param name: Name of the device (must not contain ':').
        :param desc: Descriptive string for the device.
        :param address: Unique identifier (e.g., device serial number).
        """
        super().__init__(name, desc, address)

        self._tagger: TimeTagger = None
        self._channels_in_use: list[int] = []
        self.channels_to_use = channels_to_use
        self._test_signal_enabled: bool = False
        self._test_signal_divider: int = 1
        self.operations: dict[str, Callable[..., Any]] = {
            "measure_coincidence": self.measure_coincidence,
            "measure_countrate": self.measure_countrate,
        }
        self.status = DeviceStatus.OFF

    def start(self) -> None:
        """Initialize the connection to the Swabian time tagger hardware and configures channels for potential coincidence counting."""
        if self._tagger is not None:
            logger.warning("Time tagger is already started.")
            return

        logger.info("Creating Swabian Time Tagger instance.")
        self._tagger = createTimeTaggerNetwork("127.0.0.1:41101")
        if not self._tagger:
            msg = "Failed to create time tagger. Verify hardware connection."
            logger.error(msg)
            raise RuntimeError(msg)

        all_channels = self._tagger.getChannelList(ChannelEdge.Rising)
        self._channels_in_use = all_channels[: self.channels_to_use]

        logger.info("Channels in use: %s", self._channels_in_use)

        for ch in self._channels_in_use:
            self._tagger.setInputDelay(ch, 0)

        self.status = DeviceStatus.READY
        logger.info("Swabian Time Tagger device is now READY.")

    def close(self) -> None:
        """Safely closes the connection to the Swabian time tagger hardware."""
        if self._tagger is not None:
            logger.info("Closing Swabian Time Tagger connection.")
            freeTimeTagger(self._tagger)
            self._tagger = None

        self.status = DeviceStatus.OFF
        logger.info("Swabian Time Tagger device is now OFF.")

    def info(self) -> TimeTaggerInfo:
        """Return information about this device, including its current parameters and measurement settings."""
        return TimeTaggerInfo(
            name=self.name,
            desc=self.desc,
            address=self.address,
            dtype=self.DEVICE_CLASS,
            status=self.status,
            channels_in_use=self._channels_in_use,
            test_signal_enabled=self._test_signal_enabled,
            test_signal_divider=self._test_signal_divider,
        )

    def set_test_signal(self, channels: list[int], *, enable: bool = True, divider: int | None = None) -> None:
        self._tagger.setTestSignal(channels, enable)
        if divider is not None:
            self._tagger.setTestSignalDivider(divider)

    def set_input_delay(self, channel: int, delay_ps: int) -> None:
        self._tagger.setInputDelay(channel, delay_ps)

    def measure_countrate(self, channels: list[int], binwidth_ps: int) -> list[int]:
        counter = Counter(self._tagger, channels, binwidth_ps, 1)
        counter.startFor(binwidth_ps)
        counter.waitUntilFinished()
        return [item[0] for item in counter.getData()]

    def measure_coincidence(self, channel1: int, channel2: int, binwidth_ps: int, measurement_duration_ps: int) -> int:
        corr = Correlation(self._tagger, channel1, channel2, binwidth_ps, n_bins=100000)
        corr.startFor(measurement_duration_ps)
        corr.waitUntilFinished()
        return int(np.max(corr.getData()))

    def enable_test_signal(self, *, enabled: bool, test_signal_divider: int = 1) -> None:
        self.enabled = enabled
        self.test_signal_divider = test_signal_divider
        self._test_signal_enabled = self.enabled
        self.test_signal_divider = self.test_signal_divider
        if self._test_signal_enabled:
            self._tagger.setTestSignal(self._channels_in_use, enable=True)
            logger.info("Test signal enabled on channels: %s", self._channels_in_use)
            if self.test_signal_divider != 1:
                self._tagger.setTestSignalDivider(self.test_signal_divider)
                logger.info("Test signal divider set to %d", self.test_signal_divider)
