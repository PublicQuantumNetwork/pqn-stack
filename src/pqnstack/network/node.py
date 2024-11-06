# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
import logging
import pickle

import zmq

from pqnstack.network.packet import NetworkElementClass
from pqnstack.network.packet import Packet
from pqnstack.network.packet import PacketIntent
from pqnstack.network.packet import create_registration_packet

logger = logging.getLogger(__name__)


class Node:
    def __init__(self, name: str,
                 host: str = "localhost",
                 port: int | str = 5555,
                 router_name: str = "router1",) -> None:
        self.name = name
        self.host = host
        self.port = port
        self.address = f"tcp://{host}:{port}"
        self.router_name = router_name

        self.context: zmq.Context | None = None
        self.socket: zmq.Socket | None = None  # Has the instance of the socket talking to the router.
        self.running = False

    def start(self) -> None:

        logger.info("Starting node %s at %s", self.name, self.address)
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.setsockopt_string(zmq.IDENTITY, self.name)

        try:
            self.socket.connect(self.address)
            reg_packet = create_registration_packet(source=self.name,
                                                    destination=self.router_name,
                                                    payload=NetworkElementClass.NODE,
                                                    hops=0)
            self.socket.send(pickle.dumps(reg_packet))
            _, pickled_packet = self.socket.recv_multipart()
            packet = pickle.loads(pickled_packet)
            if packet.intent != PacketIntent.REGISTRATION_ACK:
                msg = f"Registration failed. Packet: {packet}"
                raise RuntimeError(msg)
            logger.info("Node %s is connected to router at %s", self.name, self.address)
            self.running = True
        # TODO: Handle connection error properly.
        except zmq.error.ZMQError as e:
            logger.error("Could not connect to router at %s", self.address)
            raise e
        try:
            while self.running:
                _, pickled_packet = self.socket.recv_multipart()
                packet = pickle.loads(pickled_packet)

                if packet.intent == PacketIntent.PING:
                    logger.info("Received ping from %s", packet.source)
                    response = Packet(intent=PacketIntent.PING,
                                      request="PONG",
                                      source=self.name,
                                      destination=packet.source,
                                      hops=0,
                                      payload=None)
                    self.socket.send(pickle.dumps(response))

        finally:
            self.socket.close()
