import logging
import random
import string

import zmq
import pickle

from pqnstack.network.packet import Packet, create_registration_packet, PacketIntent, NetworkElementClass

logger = logging.getLogger(__name__)


class ClientBase:

    def __init__(self, name="", host="127.0.0.1", port=5555, router_name="router1", timeout=5000):

        if name == "":
            name = "".join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=6))
        self.name = name

        self.host = host
        self.port = port
        self.address = f"tcp://{host}:{port}"
        self.router_name = router_name

        self.timeout = timeout

        self.connected = False
        self.context = None
        self.socket = None

        self.connect()

    def __enter__(self):
        if not self.connected:
            self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self):
        logger.info(f"Starting client '{self.name}' Connecting to {self.address}")
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout)
        self.socket.setsockopt_string(zmq.IDENTITY, self.name)
        self.socket.connect(self.address)
        self.connected = True

        reg_packet = create_registration_packet(source=self.name,
                                                destination=self.router_name,
                                                payload=NetworkElementClass.CLIENT,
                                                hops=0)
        ret = self.ask(reg_packet)
        if ret.intent != PacketIntent.REGISTRATION_ACK:
            raise RuntimeError("Registration failed.")
        logger.info(f"Acknowledged by server. Client is connected.")

    def disconnect(self):
        logger.info(f"Disconnecting from {self.address}")
        self.socket.close()
        self.connected = False

    def ask(self, packet: Packet):
        if not self.connected:
            raise RuntimeError("No connection yet.")

        # try so that if timeout happens, the client remains usable
        try:
            self.socket.send(pickle.dumps(packet))
            
            response = self.socket.recv()
            ret = pickle.loads(response)
            logger.debug(f"Response received.")
            logger.debug(f"Response: {str(ret)}")
            return ret
        except zmq.error.Again as e:
            logger.error("Timeout occurred.")
            return None

