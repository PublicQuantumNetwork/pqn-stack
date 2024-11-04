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
                match packet.intent:
                    case PacketIntent.REGISTRATION:
                        if packet.destination != self.name:
                            self.handle_packet_error(identity_binary, f"Router {self.name} is not the destination")
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
                        self._send(identity_binary, ack_packet)

                    case PacketIntent.ROUTING:
                        logger.info(f'Got routing packet from {identity_binary}')
                    case _:

                        if packet.destination == self.name:
                            logger.info(f"Packet destination is self, dropping")
                            
                        elif packet.destination in self.nodes:
                            logger.info(f"Packet destination is a node called {packet.destination}, routing message "
                                        f"there")
                            forward_packet = copy.copy(packet)
                            forward_packet.hops += 1
                            # FIXME: What happens if get a message from something else than the node I expect the
                            #  message.
                            self._send(self.nodes[packet.destination], forward_packet)
                            logger.info(f"Sent packet to {packet.destination}, awaiting reply")
                            identity_binary, reply_packet = self.listen()
                            logger.info(f"Received reply from {identity_binary}: {reply_packet}. Responding to "
                                        f"original sender")
                            reply_packet.hops += 1
                            self._send(self.clients[reply_packet.destination], reply_packet)

                        else:
                            logger.info(f"Packet destination is not a node will ask other routers in system")
                            # FIXME: This is temporary and should be replaced with the routing algorithm.
                            self.handle_packet_error(identity_binary, "Routing not implemented yet.")

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

    def _send(self, destination: bytes, packet: Packet):
        logger.info(f"Sending packet to {packet.destination} | Packet: {packet}")
        self.socket.send_multipart([destination,
                                    b"",
                                    pickle.dumps(packet)])
        logger.info(f"Packet sent to {packet.destination}")

    # TODO: This should reply with a standard, error in your packet message to whoever sent the packet instead of
    #  just logging.
    def handle_packet_error(self, destination: bytes, message: str):
        logger.error(message)
        error_packet = Packet(intent=PacketIntent.ERROR,
                              request="ERROR",
                              source=self.name,
                              destination=destination.decode("utf-8"),
                              hops=0,
                              payload=message)
        self._send(destination, error_packet)

