# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
import copy
import pickle
import logging

import zmq

from pqnstack.base.network import NetworkElement
from pqnstack.network.packet import Packet, PacketIntent, NetworkElementClass

logger = logging.getLogger(__name__)


class Router(NetworkElement):
    def __init__(self, specs: dict) -> None:
        super().__init__(specs)

    def setup(self, specs: dict) -> None:
        self.__class = NetworkElementClass.ROUTER

    def exec(self) -> None | dict:
        pass

    def stop(self) -> None:
        pass

    def dispatch(self, packet: Packet) -> None | dict:
        pass


# FIXME: handle not finding destination and source better
class Router2:

    def __init__(self, name, host="localhost", port=5555, start_at_init=True):

        self.name = name
        self.host = host
        self.port = port

        # TODO: Verify that this address is valid
        self.address = f"tcp://{host}:{port}"

        # FIXME, breaking this into 3 different dictionaries is probably not the way to go.
        self.routers = {}  # Holds what other routers are in the network
        self.nodes = {}
        self.clients = {}

        self.context = None
        self.socket = None
        self.running = False

        if start_at_init:
            self.start()

    def start(self):
        logger.info(f"Starting router {self.name} at {self.address}")
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.ROUTER)
        self.socket.bind(self.address)
        logger.info(f"Router {self.name} is now listening on {self.address}")
        self.running = True

        try:
            while self.running:

                identity_binary, packet = self.listen()

                if packet.intent == PacketIntent.REGISTRATION:
                    if packet.request != "REGISTER":
                        self.handle_packet_error(f"Invalid registration request {packet.request}")
                        continue
                    match packet.payload:
                        case NetworkElementClass.NODE:
                            self.nodes[packet.source] = identity_binary
                            logger.info(f"Node {identity_binary} registered")
                        case NetworkElementClass.CLIENT:
                            self.clients[packet.source] = identity_binary
                            logger.info(f"Client {identity_binary} registered")
                        case NetworkElementClass.ROUTER:
                            self.routers[packet.source] = identity_binary
                            logger.info(f"Router {identity_binary} registered")

                    ack_packet = Packet(intent=PacketIntent.REGISTRATION_ACK,
                                        source=self.name,
                                        destination=identity_binary,
                                        hops=0,
                                        request="ACKNOWLEDGE",
                                        payload=None)
                    self.socket.send_multipart([identity_binary, b"", pickle.dumps(ack_packet)])
                    logger.info(f"Sent registration acknowledgment to {identity_binary}")
                    continue
                if packet.destination == self.name:
                    logger.info(f"Packet destination is self, dropping")
                    continue
                elif packet.destination in self.nodes:
                    logger.info(f"Packet destination is a node called {packet.destination}, routing message there")
                    forward_packet = copy.copy(packet)
                    forward_packet.hops += 1
                    # FIXME: What happens if get a message from something else than the node I expect the message.
                    self.socket.send_multipart([self.nodes[packet.destination], b"", pickle.dumps(forward_packet)])
                    logger.info(f"Sent packet to {packet.destination}, awaiting reply")
                    identity_binary, reply_packet = self.listen()
                    logger.info(f"Received reply from {identity_binary}: {reply_packet}. Responding to original sender")
                    reply_packet.hops += 1
                    self.socket.send_multipart([self.clients[reply_packet.destination], b"", pickle.dumps(reply_packet)])

                else:
                    logger.info(f"Packet destination is not a node will ask other routers in system")

        finally:
            self.socket.close()

    def listen(self):
        # Depending on who is sending a request, the number of items received will be different. This is not
        # DEALER sockets send 2 items, REQ sockets send an empty delimiter.
        request = self.socket.recv_multipart()
        if len(request) == 2:
            identity_binary, pickled_packet = request
        elif len(request) == 3:
            identity_binary, _, pickled_packet = request
        else:
            self.handle_packet_error(f"Requests can only have 2 or 3 parts, not {len(request)}")
            return None, None

        packet = pickle.loads(pickled_packet)
        logger.info(f"Received packet from {identity_binary}: {packet}")
        return identity_binary, packet

    # TODO: This should reply with a standard, error in your packet message to whoever sent the packet instead of
    #  just logging.
    @staticmethod  # Static for now, this will change once we have a proper implementation
    def handle_packet_error(logging_message):
        logger.error(logging_message)
