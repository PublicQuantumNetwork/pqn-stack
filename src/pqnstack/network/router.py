# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
from pqnstack.base.network import NetworkElement, NetworkElementClass
from pqnstack.network.packet import Packet
from typing import Dict


class Router(NetworkElement):

    def __init__(self, specs: Dict):
        super().__init__(specs)

    def config(self, specs: Dict):
        self.__class = NetworkElementClass.ROUTER

    def exec(self):
        pass

    def stop(self):
        pass

    def dispatch(self, packet: Packet):
        pass

