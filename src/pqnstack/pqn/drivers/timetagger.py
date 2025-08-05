import logging
from dataclasses import dataclass
from dataclasses import field
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

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TimeTaggerInfo(InstrumentInfo):
    active_channels: list[int] = field(default_factory=list)
    test_signal_enabled: bool = False
    test_signal_divider: int = 1


@runtime_checkable
@dataclass(slots=True)
class TimeTaggerInstrument(Instrument, Protocol):
    active_channels: list[int] = field(default_factory=list)
    test_signal_enabled: bool = False
    test_signal_divider: int = 1

    def __post_init__(self) -> None:
        self.operations["count_singles"] = self.count_singles
        self.operations["measure_correlation"] = self.measure_correlation

    def count_singles(self, channels: list[int], integration_time_s: float) -> list[int]: ...
    def measure_correlation(self, start_ch: int, stop_ch: int, integration_time_s: float, binwidth_ps: int) -> int: ...


@dataclass(slots=True)
class SwabianTimeTagger(TimeTaggerInstrument):
    """Instantiate a SwabianTimeTagger Instrument.

    `hw_address` should be of the form "ip:port"
        e.g.: hw_address = "127.0.0.1:41101".
    """

    _tagger: TimeTagger = field(init=False, repr=False)

    def start(self) -> None:
        """Initialize the connection to the Swabian time tagger hardware and configures channels for potential coincidence counting."""
        logger.info("Creating Swabian Time Tagger instance.")
        self._tagger = createTimeTaggerNetwork(self.hw_address)
        if not self._tagger:
            msg = "Failed to create time tagger. Verify hardware connection."
            logger.error(msg)
            raise RuntimeError(msg)

        hw_channels = self._tagger.getChannelList(ChannelEdge.Rising)
        self.active_channels = [hw_channels[ch - 1] for ch in self.active_channels]

        for ch in self.active_channels:
            self._tagger.setInputDelay(ch, 0)

        logger.info("Swabian Time Tagger device is now READY.")

    def close(self) -> None:
        """Safely closes the connection to the Swabian time tagger hardware."""
        if self._tagger is not None:
            logger.info("Closing Swabian Time Tagger connection.")
            freeTimeTagger(self._tagger)
            self._tagger = None

        logger.info("Swabian Time Tagger device is now OFF.")

    @property
    def info(self) -> TimeTaggerInfo:
        return TimeTaggerInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            # hw_status=,
            active_channels=self.active_channels,
            test_signal_enabled=self.test_signal_enabled,
            test_signal_divider=self.test_signal_divider,
        )

    def set_input_delay(self, channel: int, delay_ps: int) -> None:
        self._tagger.setInputDelay(channel, delay_ps)

    def set_test_signal(self, channels: list[int], *, enable: bool = True, divider: int = 1) -> None:
        self._tagger.setTestSignal(channels, enable)
        if enable:
            self._tagger.setTestSignalDivider(divider)

    def count_singles(self, channels: list[int], integration_time_s: float = 1.0) -> list[int]:
        # TODO: use these as kwargs
        _duration_ps = int(integration_time_s * 1e12)
        counter = Counter(self._tagger, channels, _duration_ps, 1)
        counter.startFor(_duration_ps)
        counter.waitUntilFinished()
        return [item[0] for item in counter.getData()]

    def measure_correlation(
        self,
        start_ch: int,
        stop_ch: int,
        integration_time_s: float = 1.0,
        binwidth_ps: int = 1,
        n_bins: int = int(1e5),
    ) -> int:
        # TODO: use these as kwargs
        count_time_ps = int(integration_time_s * 1e12)
        corr = Correlation(self._tagger, start_ch, stop_ch, binwidth_ps, n_bins=n_bins)
        corr.startFor(count_time_ps)
        corr.waitUntilFinished()
        return int(max(corr.getData()))
