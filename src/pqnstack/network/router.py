# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
import copy
import logging
import pickle

import zmq

from pqnstack.network.packet import NetworkElementClass
from pqnstack.network.packet import Packet
from pqnstack.network.packet import PacketIntent

logger = logging.getLogger(__name__)


# FIXME: handle not finding destination and source better
class Router:
    def __init__(self, name: str, host: str = "localhost", port: int = 5555) -> None:
        self.name = name
        self.host = host
        self.port = port

        # TODO: Verify that this address is valid
        self.address = f"tcp://{host}:{port}"

        # FIXME, breaking this into 3 different dictionaries is probably not the way to go.
        self.routers: dict[str, bytes] = {}  # Holds what other routers are in the network
        self.nodes: dict[str, bytes] = {}
        self.clients: dict[str, bytes] = {}

        self.context: zmq.Context[zmq.Socket[bytes]] | None = None
        self.socket: zmq.Socket[bytes] | None = None
        self.running = False

    def start(self) -> None:
        logger.info("Starting router %s at %s", self.name, self.address)
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.ROUTER)
        self.socket.bind(self.address)
        logger.info("Router %s is now listening on %s", self.name, self.address)
        self.running = True

        try:
            while self.running:
                identity_binary, packet = self.listen()
                if packet is None or identity_binary is None:
                    logger.error("Error listening to packets. Either the packet is None or the identity is None.")
                    continue

                match packet.intent:
                    case PacketIntent.REGISTRATION:
                        self.handle_registration(identity_binary, packet)
                    case PacketIntent.ROUTING:
                        logger.info("Got routing packet from %s", identity_binary)
                    case _:
                        self.handle_pass_packet(identity_binary, packet)

        finally:
            self.socket.close()

    def handle_registration(self, identity_binary: bytes, packet: Packet) -> None:
        if packet.destination != self.name:
            self.handle_packet_error(identity_binary, f"Router {self.name} is not the destination")
            return
        match packet.payload:
            case NetworkElementClass.NODE:
                self.nodes[packet.source] = identity_binary
                logger.info("Node %s registered", identity_binary)
            case NetworkElementClass.CLIENT:
                self.clients[packet.source] = identity_binary
                logger.info("Client %s registered", identity_binary)
            case NetworkElementClass.ROUTER:
                self.routers[packet.source] = identity_binary
                logger.info("Router %s registered", identity_binary)

        ack_packet = Packet(
            intent=PacketIntent.REGISTRATION_ACK,
            source=self.name,
            destination=identity_binary.decode("utf-8"),
            hops=0,
            request="ACKNOWLEDGE",
            payload=None,
        )
        self._send(identity_binary, ack_packet)

    def handle_pass_packet(self, identity_binary: bytes, packet: Packet) -> None:
        """Handle all the logic to get a packet from one place to another."""
        if packet.destination == self.name:
            logger.info("Packet destination is self, dropping")

        elif packet.destination in self.nodes or packet.destination in self.clients:
            logger.info("Packet destination is a node called %s, routing message there", packet.destination)
            forward_packet = copy.copy(packet)
            forward_packet.hops += 1
            dest = self.nodes.get(packet.destination) or self.clients.get(packet.destination)
            if dest is None:
                self.handle_packet_error(identity_binary, f"Destination {packet.destination} not found.")
                return
            self._send(dest, forward_packet)
            logger.info("Sent packet to %s", packet.destination)

        else:
            logger.info("Packet destination is not a node will ask other routers in system")
            # FIXME: This is temporary and should be replaced with the routing algorithm.
            self.handle_packet_error(identity_binary, "Routing not implemented yet.")

    def listen(self) -> tuple[bytes, Packet] | tuple[None, None]:
        # This should never happen, but mypy complains if the check is not done
        if self.socket is None:
            msg = "Socket is None, cannot listen."
            logger.error(msg)
            raise RuntimeError(msg)

        # Depending on who is sending a request, the number of items received will be different. This is not
        # DEALER sockets send 2 items, REQ sockets send an empty delimiter.
        dealer_parts = 2
        req_parts = 3
        request = self.socket.recv_multipart()
        if len(request) == dealer_parts:
            identity_binary, pickled_packet = request
        elif len(request) == req_parts:
            identity_binary, _, pickled_packet = request
        else:
            self.handle_packet_error(request[0], f"Requests can only have 2 or 3 parts, not {len(request)}")
            return None, None

        packet = pickle.loads(pickled_packet)
        logger.info("Received packet from %s: %s", identity_binary, packet)
        return identity_binary, packet

    def _send(self, destination: bytes, packet: Packet) -> None:
        # This should never happen, but mypy complains if the check is not done
        if self.socket is None:
            msg = "Socket is None, cannot send message."
            logger.error(msg)
            raise RuntimeError(msg)

        logger.info("Sending packet to %s | Packet: %s", packet.destination, packet)
        self.socket.send_multipart([destination, b"", pickle.dumps(packet)])
        logger.info("Packet sent to %s", packet.destination)

    # TODO: This should reply with a standard, error in your packet message to whoever sent the packet instead of
    #  just logging.
    def handle_packet_error(self, destination: bytes, message: str) -> None:
        logger.error(message)
        error_packet = Packet(
            intent=PacketIntent.ERROR,
            request="ERROR",
            source=self.name,
            destination=destination.decode("utf-8"),
            hops=0,
            payload=message,
        )
        self._send(destination, error_packet)
