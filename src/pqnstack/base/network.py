# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
from abc import ABC
from abc import abstractmethod

import zmq

from pqnstack.network.packet import NetworkElementClass
from pqnstack.network.packet import Packet


class NetworkElement(ABC):
    def __init__(self, specs: dict) -> None:
        self.__class: None | NetworkElementClass = None

        # Call the overridden version of `setup` for hardware specifics
        self.setup(specs)

        # Routing must be taken care of for any network-enabled unit
        self.__router_ip = specs["router-ip"]
        self.__router_port = specs["router-port"]

        # Setup 0MQ
        context = zmq.Context()
        self.__socket = context.socket(zmq.REP)

        if self.__class == NetworkElementClass.ROUTER:
            self.__socket.bind(f"tcp://*:{self.__router_port}")
        else:
            self.__socket.bind(f"tcp://{self.__router_ip}:{self.__router_port}")

    @abstractmethod
    def setup(self, specs: dict) -> None:
        pass

    @abstractmethod
    def exec(self) -> None | dict:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def dispatch(self, packet: Packet) -> None | dict:
        pass
