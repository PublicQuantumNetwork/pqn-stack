import logging
import pickle
import random
import string
from types import TracebackType

import zmq

from pqnstack.network.packet import NetworkElementClass
from pqnstack.network.packet import Packet
from pqnstack.network.packet import PacketIntent
from pqnstack.network.packet import create_registration_packet

logger = logging.getLogger(__name__)


class ClientBase:
    def __init__(
        self,
        name: str = "",
        host: str = "127.0.0.1",
        port: int | str = 5555,
        router_name: str = "router1",
        timeout: int = 5000,
    ) -> None:
        if name == "":
            name = "".join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=6))
        self.name = name

        self.host = host
        self.port = port
        self.address = f"tcp://{host}:{port}"
        self.router_name = router_name

        self.timeout = timeout

        self.connected = False
        self.context: zmq.Context | None = None
        self.socket: zmq.Socket | None = None  # Has the instance of the socket talking to the router.

        self.connect()

    def __enter__(self) -> "ClientBase":
        if not self.connected:
            self.connect()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        self.disconnect()

    def connect(self) -> None:
        logger.info("Starting client '%s' Connecting to %s", self.name, self.address)
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout)
        self.socket.setsockopt_string(zmq.IDENTITY, self.name)
        self.socket.connect(self.address)
        self.connected = True

        reg_packet = create_registration_packet(
            source=self.name, destination=self.router_name, payload=NetworkElementClass.CLIENT, hops=0
        )
        ret = self.ask(reg_packet)
        if ret is None:
            msg = "Something went wrong with the registration."
            raise RuntimeError(msg)
        if ret.intent != PacketIntent.REGISTRATION_ACK:
            msg = "Registration failed."
            raise RuntimeError(msg)
        logger.info("Acknowledged by server. Client is connected.")

    def disconnect(self) -> None:
        logger.info("Disconnecting from %s", self.address)
        if self.socket is None:
            logger.warning("Socket is already None.")
            self.connected = False
            return

        self.socket.close()
        self.connected = False
        logger.info("Disconnected from %s", self.address)

    def ask(self, packet: Packet) -> Packet | None:
        if not self.connected:
            msg = "No connection yet."
            logger.error(msg)
            raise RuntimeError(msg)

        if self.socket is None:
            msg = "Socket is None. Cannot ask."
            logger.error(msg)
            raise RuntimeError(msg)

        # try so that if timeout happens, the client remains usable

        self.socket.send(pickle.dumps(packet))
        try:
            response = self.socket.recv()
        except zmq.error.Again:
            logger.error("Timeout occurred.")
            return None

        ret = pickle.loads(response)
        logger.debug("Response received.")
        logger.debug("Response: %s", str(ret))
        return ret
