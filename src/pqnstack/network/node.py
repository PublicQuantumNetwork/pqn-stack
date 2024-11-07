# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
import logging
import pickle
import importlib

import zmq

from pqnstack.base.errors import InvalidInstrumentsConfigurationError
from pqnstack.base.driver import DeviceDriver
from pqnstack.network.packet import NetworkElementClass
from pqnstack.network.packet import Packet
from pqnstack.network.packet import PacketIntent
from pqnstack.network.packet import create_registration_packet

logger = logging.getLogger(__name__)


class Node:
    def __init__(self, name: str,
                 host: str = "localhost",
                 port: int | str = 5555,
                 router_name: str = "router1",
                 **instruments) -> None:
        """
        Node class for PQN. A Node is the class that talks with real hardware and performs experiments. It talks to a
        single `Router` instance through zqm and awaits for instructions from it.

        :param name: Name for the Node.
        :param host: Hostname or IP address of the Router this node talks to.
        :param port: Port of the name of the Router this node talks to.
        :param router_name: Name of the Router this node talks to.
        :param instruments: Instruments is a Dictionary holding the necessary instructions to initialize any hardware
         the Node talks to. The keys are the names of the instruments, every key has another dictionary as its value
         with all the necessary instructions to initialize the instrument. Inside of the dictionary for the specific
         instrument, a key called 'import' is required holding the import path for that specific instrument.
         Note that the name is not necessary since that is the key of the dictionary.

         e.g.
         ```
         instruments = {
            "rotator_1": {
                "import": "pqnstack.pqn.drivers.rotator.Rotator",
                "desc": "Rotator in optical table 1",
                "address": "83860213",
                **extra_kwargs
                }
            }
        """
        self.name = name
        self.host = host
        self.port = port
        self.address = f"tcp://{host}:{port}"
        self.router_name = router_name

        self.context: zmq.Context | None = None
        self.socket: zmq.Socket | None = None  # Has the instance of the socket talking to the router.

        # Verify that every instrument contains the minimum required keys.
        for ins_name, ins_dict in instruments.items():
            if not isinstance(ins_dict, dict):
                msg = f"{ins_name} is not a dictionary, please provide the necessary instructions for this instrument"
                raise InvalidInstrumentsConfigurationError(msg)

            if "import" not in ins_dict:
                msg = f"{ins_name} is missing its 'import' key, please provide an import path for this instrument"
                raise InvalidInstrumentsConfigurationError(msg)

            if "desc" not in ins_dict:
                msg = f"{ins_name} is missing its 'desc' key, please provide a description for this instrument"
                raise InvalidInstrumentsConfigurationError(msg)

            if "address" not in ins_dict:
                msg = f"{ins_name} is missing its 'address' key, please provide an address for this instrument"
                raise InvalidInstrumentsConfigurationError(msg)

        self.instruments = instruments
        self.instantiated_instruments: dict[str, DeviceDriver] = {}

        self.running = False

    def instantiate_instruments(self) -> None:

        for ins_name, ins_dict in self.instruments.items():
            ins_import = ins_dict.pop("import")
            ins_desc = ins_dict.pop("desc")
            ins_address = ins_dict.pop("address")

            try:
                module_name, class_name = ins_import.rsplit(".", 1)
                module = importlib.import_module(module_name)
                class_ = getattr(module, class_name)
            except (ImportError, AttributeError) as e:
                msg = f"Could not import {ins_import}. Please verify the import path for this instrument."
                raise InvalidInstrumentsConfigurationError(msg) from e

            try:
                ins = class_(name=ins_name, desc=ins_desc, address=ins_address, **ins_dict)
            # FIXME: Figure out what the exception type could be if the instrument cannot be instantiated.
            except Exception as e:
                msg = f"Could not instantiate {ins_import}. Please verify the parameters for this instrument."
                raise InvalidInstrumentsConfigurationError(msg) from e

            self.instantiated_instruments[ins_name] = ins

    def start(self) -> None:

        self.instantiate_instruments()

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
            packet = self._listen()
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
                packet = self._listen()

                match packet.intent:
                    case PacketIntent.PING:
                        response = Packet(intent=PacketIntent.PING,
                                          request="PONG",
                                          source=self.name,
                                          destination=packet.source,
                                          hops=0,
                                          payload=None)
                        self.socket.send(pickle.dumps(response))

                    case PacketIntent.DATA:

                        if packet.request == "GET_DEVICES":
                            ret_instruments = {name: type(ins) for name, ins in self.instantiated_instruments.items()}
                            response = Packet(intent=PacketIntent.DATA,
                                              request="GET_DEVICES",
                                              source=self.name,
                                              destination=packet.source,
                                              hops=0,
                                              payload=ret_instruments)
                            self.socket.send(pickle.dumps(response))



        finally:
            self.socket.close()

    def _listen(self) -> Packet:
        _, pickled_packet = self.socket.recv_multipart()
        packet = pickle.loads(pickled_packet)
        if packet.destination != self.name:
            # FIXME: This should return an error packet instead of just crashing
            msg = f"Packet intended for {packet.destination} but received by {self.name}. Packet: {packet}"
            raise RuntimeError(msg)

        logger.info("Received packet: %s", packet)
        return packet





