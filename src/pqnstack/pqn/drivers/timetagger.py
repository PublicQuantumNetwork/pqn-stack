import logging
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Protocol
from typing import runtime_checkable

from TimeTagger import ChannelEdge
from TimeTagger import Correlation
from TimeTagger import Counter
from TimeTagger import TimeTagger
from TimeTagger import createTimeTaggerNetwork
from TimeTagger import freeTimeTagger

from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import log_parameter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TimeTaggerInfo(InstrumentInfo):
    channels_in_use: list[int] = field(default_factory=list)
    test_signal_enabled: bool = False
    test_signal_divider: int = 1
    last_measurement_rates: list[float] = field(default_factory=list)
    last_coincidence_window_ps: int = 0


@runtime_checkable
@dataclass(slots=True)
class TimeTaggerInstrument(Instrument, Protocol):
    channels_to_use: int = 10
    channels_in_use: list[int] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.operations["measure_coincidence"] = self.measure_coincidence
        self.operations["measure_countrate"] = self.measure_countrate

        self.parameters.add("degrees")

    @property
    def info(self) -> TimeTaggerInfo:
        return TimeTaggerInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            hw_status=self.hw_status,
        )

    @property
    @log_parameter
    def degrees(self) -> float: ...

    @degrees.setter
    @log_parameter
    def degrees(self, degrees: float) -> None: ...

    def measure_coincidence(self) -> float: ...
    def measure_countrate(self) -> float: ...

    def move_to(self, angle: float) -> None:
        """Move the rotator to the specified angle."""
        self.degrees = angle

    def move_by(self, angle: float) -> None:
        """Move the rotator by the specified angle."""
        self.degrees += angle

    @abstractmethod
    def measure_coincidence(self, channel1: int, channel2: int, binwidth_ps: int, measurement_duration_ps: int) -> int:
        "Measaures the coincidence between input channels."

    @abstractmethod
    def measure_countrate(self, channels: list[int], binwidth_ps: int) -> list[int]:
        "Measaures the singles counts on input channels."


@dataclass(slots=True)
class SwabianTimeTagger(TimeTaggerInstrument):
    _tagger: TimeTagger = field(init=False, repr=False)
    _test_signal_enabled: bool = False
    _test_signal_divider: int = 1

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
        self.channels_in_use = all_channels[: self.channels_to_use]

        logger.info("Channels in use: %s", self.channels_in_use)

        for ch in self.channels_in_use:
            self._tagger.setInputDelay(ch, 0)

        logger.info("Swabian Time Tagger device is now READY.")

    def close(self) -> None:
        """Safely closes the connection to the Swabian time tagger hardware."""
        if self._tagger is not None:
            logger.info("Closing Swabian Time Tagger connection.")
            freeTimeTagger(self._tagger)
            self._tagger = None

        logger.info("Swabian Time Tagger device is now OFF.")

    def set_test_signal(self, channels: list[int], *, enable: bool = True, divider: int | None = None) -> None:
        self._tagger.setTestSignal(channels, enable)
        if divider is not None:
            self._tagger.setTestSignalDivider(divider)

    def set_input_delay(self, channel: int, delay_ps: int) -> None:
        self._tagger.setInputDelay(channel, delay_ps)

    def measure_singles(self, channels: list[int], count_time_s: float) -> list[int]:
        # TODO: use these as kwargs
        count_time_ps = int(count_time_s * 1e12)
        counter = Counter(self._tagger, channels, count_time_ps, 1)
        counter.startFor(count_time_ps)
        counter.waitUntilFinished()
        return [item[0] for item in counter.getData()]

    def measure_coincidence(self, channel1: int, channel2: int, count_time_s: float, binwidth_s: float) -> int:
        # TODO: use these as kwargs
        count_time_ps = int(count_time_s * 1e12)
        binwidth_ps = int(binwidth_s * 1e12)
        corr = Correlation(self._tagger, channel1, channel2, binwidth_ps, n_bins=100000)
        corr.startFor(count_time_ps)
        corr.waitUntilFinished()
        counts = max(corr.getData())

        if not isinstance(counts, int):
            return -1

        return counts

    def enable_test_signal(self, *, enabled: bool, test_signal_divider: int = 1) -> None:
        self.enabled = enabled
        self.test_signal_divider = test_signal_divider
        self._test_signal_enabled = self.enabled
        self.test_signal_divider = self.test_signal_divider
        if self._test_signal_enabled:
            self._tagger.setTestSignal(self.channels_in_use, enable=True)
            logger.info("Test signal enabled on channels: %s", self.channels_in_use)
            if self.test_signal_divider != 1:
                self._tagger.setTestSignalDivider(self.test_signal_divider)
                logger.info("Test signal divider set to %d", self.test_signal_divider)
