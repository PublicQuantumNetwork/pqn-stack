# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
from pqnstack.network.packet import Packet
from abc import ABC, abstractmethod
from typing import Dict
from enum import Enum
import zmq


class NetworkElementClass(Enum):
    ROUTER = 0
    NODE = 1
    TELEMETRY = 2


class NetworkElement(ABC):

    def __init__(self, specs: Dict):
        self.__class = None

        # Call the overridden version of `config` for hardware specifics
        self.config(specs)

        # Routing must be taken care of for any network-enabled unit
        self.__router_ip = specs['router-ip']
        self.__router_port = specs['router-port']

        # Setup 0MQ
        context = zmq.Context()
        self.__socket = context.socket(zmq.REP)

        if self.__class == NetworkElementClass.ROUTER:
            self.__socket.bind(f'tcp://*:{self.__router_port}')
        else:
            self.__socket.bind(f'tcp://{self.__router_ip}:{self.__router_port}')

        # After housekeeping, go into idle mode
        self.idle()

    def idle(self):
        while True:
            packet = Packet.from_json(self.__socket.recv())
            self.dispatch(packet)

    @abstractmethod
    def setup(self, specs: Dict):
        pass

    @abstractmethod
    def exec(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def dispatch(self, packet: Packet):
        pass
