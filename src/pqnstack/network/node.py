# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
from abc import abstractmethod

from pqnstack.base.network import NetworkElement
from pqnstack.network.packet import Packet


class Node(NetworkElement):
    def __init__(self, specs: dict) -> None:
        super().__init__(specs)
        self.drivers = {}
        self.setup(specs)

    def exec(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def measure(self) -> None:
        # Ensure the execution context is appropriate and orchestrate
        # the setup
        #
        # Output: list of actual data
        self.call()

        self.filter()

        # Produce a packet
        self.collect()

    @abstractmethod
    def setup(self, specs: dict):
        pass

    @abstractmethod
    def call(self):
        pass

    @abstractmethod
    def filter(self):
        pass

    @abstractmethod
    def collect(self) -> Packet:
        pass
