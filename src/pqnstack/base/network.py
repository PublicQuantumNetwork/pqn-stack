# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
from abc import ABC
from abc import abstractmethod
from enum import Enum

import zmq

from pqnstack.network.packet import Packet


class NetworkElementClass(Enum):
    ROUTER = 0
    NODE = 1
    TELEMETRY = 2


class NetworkElement(ABC):
    def __init__(self, specs: dict) -> None:
        self.__class = None

        # Call the overridden version of `config` for hardware specifics
        self.config(specs)

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

        # After housekeeping, go into idle mode
        self.idle()

    def idle(self) -> None:
        while True:
            packet = Packet.from_json(self.__socket.recv())
            self.dispatch(packet)

    @abstractmethod
    def setup(self, specs: dict) -> None:
        pass

    @abstractmethod
    def exec(self) -> dict:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def dispatch(self, packet: Packet) -> dict:
        pass
