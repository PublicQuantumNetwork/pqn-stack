# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
from abc import abstractmethod

from pqnstack.base.driver import DeviceDriver
from pqnstack.base.network import NetworkElement
from pqnstack.network.packet import Packet


class Node(NetworkElement):
    def __init__(self, specs: dict) -> None:
        super().__init__(specs)
        self.drivers: dict[str, DeviceDriver] = {}
        self.setup(specs)

    def exec(self) -> None | dict:
        pass

    def stop(self) -> None:
        pass

    def measure(self) -> list:
        """
        Ensure the execution context is appropriate and orchestrate the setup.

        :return: list of actual data
        """
        self.call()

        self.filter()

        # Produce a packet
        self.collect()

        return []

    @abstractmethod
    def setup(self, specs: dict) -> None:
        pass

    @abstractmethod
    def call(self) -> None | dict:
        pass

    @abstractmethod
    def filter(self) -> None:
        pass

    @abstractmethod
    def collect(self) -> Packet:
        # FIXME: This is a placeholder packet
        return Packet("", "", (-1, -1), (-1, -1), -1, -1)
