# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

from pqnstack.base.errors import DriverNotFoundError
from pqnstack.network.node import Node
from pqnstack.network.packet import Packet
from pqnstack.pqn.drivers.optics import WavePlate
from pqnstack.pqn.drivers.time import IDQTimeTagger


class QuantumNode(Node):
    def __init__(self, specs: dict) -> None:
        """Initialize as much as we can from a generic node."""
        super().__init__(specs)

    def setup(self, specs: dict) -> None:
        # Initialize time tagger device
        if "time-tagger" not in specs["drivers"]:
            msg = "IDQTimeTagger"
            raise DriverNotFoundError(msg)

        self.drivers["time-tagger"] = IDQTimeTagger(specs["drivers"]["time-tagger"])

        # Initialize wave plate motor
        if "wave-plate" not in specs["drivers"]:
            msg = "WavePlate"
            raise DriverNotFoundError(msg)

        self.drivers["wave-plate"] = WavePlate(specs["drivers"]["wave-plate"])

    def call(self) -> list:
        """
        Call drivers in sequence.

        Activate the wave plate and collect list of measurement, takes time.
        Send command to time tagger.
        Wait period and collect raw data.
        Return wave plate to the starting position (clean up!).
        Produce a list of measurements with respective bases.
        """

    def filter(self) -> list:
        """
        Filter the data.

        Calculate error - does the job of estimating matches.
        Computes statistics.
        Pass a new list/object.
        """

    def collect(self) -> Packet:
        """Now, generate a packet we can send to the network."""
