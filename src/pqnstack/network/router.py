# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

from pqnstack.base.network import NetworkElement
from pqnstack.base.network import NetworkElementClass
from pqnstack.network.packet import Packet


class Router(NetworkElement):
    def __init__(self, specs: dict) -> None:
        super().__init__(specs)

    def config(self, specs: dict) -> None:
        self.__class = NetworkElementClass.ROUTER

    def exec(self) -> dict:
        pass

    def stop(self) -> None:
        pass

    def dispatch(self, packet: Packet) -> dict:
        pass
