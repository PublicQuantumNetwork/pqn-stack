# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
import pickle
import logging
from abc import abstractmethod

import zmq

from pqnstack.base.driver import DeviceDriver
from pqnstack.base.network import NetworkElement
from pqnstack.network.packet import Packet, RegistrationPacket, PacketIntent, NetworkElementClass

logger = logging.getLogger(__name__)


class Node2:
    def __init__(self, name, host="localhost", port=5555, start_at_init=True):
        self.name = name
        self.host = host
        self.port = port
        self.address = f"tcp://{host}:{port}"

        self.context = None
        self.socket = None  # Has the instance of the socket talking to the router.
        self.running = False

        if start_at_init:
            self.start()

    def start(self):

        logger.info(f"Starting node {self.name} at {self.address}")
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.setsockopt_string(zmq.IDENTITY, self.name)

        try:
            self.socket.connect(self.address)
            reg_packet = RegistrationPacket(source=self.name,
                                            destination=self.address,
                                            element_type=NetworkElementClass.NODE,
                                            hops=0)
            self.socket.send(pickle.dumps(reg_packet))
            _, pickled_packet = self.socket.recv_multipart()
            packet = pickle.loads(pickled_packet)
            if packet.intent != PacketIntent.REGISTRATION_ACK:
                raise RuntimeError("Registration failed.")
            logger.info(f"Node {self.name} is connected to router at {self.address}")
            self.running = True
        # TODO: Handle connection error properly.
        except zmq.error.ZMQError as e:
            logger.error(f"Could not connect to router at {self.address}")
            raise e
        try:
            while self.running:
                _, pickled_packet = self.socket.recv_multipart()
                packet = pickle.loads(pickled_packet)

                if packet.intent == PacketIntent.PING:
                    logger.info(f"Received ping from {packet.source}")
                    response = Packet(intent=PacketIntent.PING,
                                      request="PONG",
                                      source=self.name,
                                      destination=packet.source,
                                      hops=0,
                                      payload=None)
                    self.socket.send(pickle.dumps(response))

        finally:
            self.socket.close()


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
