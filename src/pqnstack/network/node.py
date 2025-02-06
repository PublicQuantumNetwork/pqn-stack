# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
import importlib
import logging
import pickle
from typing import Any

import zmq

from pqnstack.base.driver import DeviceDriver
from pqnstack.base.errors import CouldNotConnectToNetworkElementError
from pqnstack.base.errors import InvalidInstrumentsConfigurationError
from pqnstack.network.packet import NetworkElementClass
from pqnstack.network.packet import Packet
from pqnstack.network.packet import PacketIntent
from pqnstack.network.packet import create_registration_packet

logger = logging.getLogger(__name__)


class Node:
    def __init__(
        self,
        name: str,
        host: str = "localhost",
        port: int = 5555,
        router_name: str = "router1",
        beat_period: int = 1000,
        **instruments: dict[str, Any],
    ) -> None:
        """
        Node class for PQN.

        A Node is the class that talks with real hardware and performs experiments. It talks to a
        single `Router` instance through zqm and awaits for instructions from it. Every `beat_interval` milliseconds,
        sends a registration packet to the router.
        This is done so if the router goes offline, the node can reconnect to the router automatically.

        :param name: Name for the Node.
        :param host: Hostname or IP address of the Router this node talks to.
        :param port: Port of the name of the Router this node talks to.
        :param router_name: Name of the Router this node talks to.
        :param beat_period: Interval in milliseconds to send a beat to the Router.
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
        self.beat_period = beat_period

        self.context: zmq.Context[zmq.Socket[bytes]] | None = None
        self.socket: zmq.Socket[bytes] | None = None  # Has the instance of the socket talking to the router.

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

            logger.info("Instantiating %s", ins_name)
            try:
                module_name, class_name = ins_import.rsplit(".", 1)
                module = importlib.import_module(module_name)
                class_ = getattr(module, class_name)
            except (ImportError, AttributeError) as e:
                msg = f"Could not import {ins_import}. Please verify the import path for this instrument."
                raise InvalidInstrumentsConfigurationError(msg) from e

            try:
                ins = class_(name=ins_name, desc=ins_desc, address=ins_address, **ins_dict)
                ins.start()
            # FIXME: Figure out what the exception type could be if the instrument cannot be instantiated.
            except Exception as e:
                msg = f"Could not instantiate {ins_import}. Please verify the parameters for this instrument."
                raise InvalidInstrumentsConfigurationError(msg) from e

            self.instantiated_instruments[ins_name] = ins
            logger.info("Successfully instantiated %s", ins_name)

    def start(self) -> None:
        self.instantiate_instruments()

        logger.info("Starting node %s at %s", self.name, self.address)
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.setsockopt_string(zmq.IDENTITY, self.name)

        # Wait 10 beats for the first check before timing out
        self.socket.setsockopt(zmq.RCVTIMEO, self.beat_period * 10)
        try:
            self._beat()
        except zmq.error.Again as er:
            logger.exception("Could not connect to router at %s", self.address)
            msg = "Could not connect to router."
            raise CouldNotConnectToNetworkElementError(msg) from er

        # Set the beat interval to the normal value.
        self.socket.setsockopt(zmq.RCVTIMEO, self.beat_period)

        try:
            while self.running:
                try:
                    packet = self._listen()
                except zmq.error.ZMQError:
                    logger.debug("Time inverval happened, sending a beat.")
                    self._beat()
                    continue

                match packet.intent:
                    case PacketIntent.PING:
                        response = self._handle_ping(packet)
                        self.socket.send(pickle.dumps(response))

                    case PacketIntent.DATA:
                        match packet.request:
                            case "GET_DEVICES":
                                response = self._handle_get_devices(packet)
                                self.socket.send(pickle.dumps(response))

                            case "GET_DEVICE_STRUCTURE":
                                response = self._handle_get_device_structure(packet)
                                self.socket.send(pickle.dumps(response))

                    case PacketIntent.CONTROL:
                        response = self._handle_instrument_control(packet)
                        self.socket.send(pickle.dumps(response))

        finally:
            self.socket.close()

    def _listen(self) -> Packet:
        # This should never happen, but mypy complains if the check is not done
        if self.socket is None:
            msg = "Socket is None, cannot listen."
            logger.error(msg)
            raise RuntimeError(msg)

        _, pickled_packet = self.socket.recv_multipart()
        packet = pickle.loads(pickled_packet)
        if packet.destination != self.name:
            # FIXME: This should return an error packet instead of just crashing
            msg = f"Packet intended for {packet.destination} but received by {self.name}. Packet: {packet}"
            raise RuntimeError(msg)

        logger.info("Received packet: %s", packet)

        if not isinstance(packet, Packet):
            msg = f"Received packet is not a Packet object, got {type(packet)}"
            raise TypeError(msg)

        return packet

    def _beat(self) -> None:
        """
        Execute a single beat to the ROUTER.

         This is the same process as initial registration. If the Router cannot be reached, logs the message and keeps going.

        :return:
        """
        try:
            # This should never happen, but mypy complains if the check is not done
            if self.socket is None:
                msg = "Socket is None, cannot listen."
                logger.error(msg)
                raise RuntimeError(msg)

            self.socket.connect(self.address)
            reg_packet = create_registration_packet(
                source=self.name, destination=self.router_name, payload=NetworkElementClass.NODE, hops=0
            )
            self.socket.send(pickle.dumps(reg_packet))
            packet = self._listen()
            if packet.intent != PacketIntent.REGISTRATION_ACK:
                msg = f"Registration failed. Packet: {packet}"
                raise RuntimeError(msg)
            logger.info("Node %s is connected to router at %s", self.name, self.address)
            self.running = True

        # This indicates that the router is down, raise a warning but do not crash. Keep trying until its manually stopped.
        except zmq.error.Again:
            logger.warning("Router at %s did not reply to heartbeat, router seems offline", self.address)

    def _handle_ping(self, packet: Packet) -> Packet:
        return Packet(
            intent=PacketIntent.PING, request="PONG", source=self.name, destination=packet.source, payload=None
        )

    def _handle_get_devices(self, packet: Packet) -> Packet:
        ret_instruments = {name: type(ins) for name, ins in self.instantiated_instruments.items()}
        return Packet(
            intent=PacketIntent.DATA,
            request="GET_DEVICES",
            source=self.name,
            destination=packet.source,
            payload=ret_instruments,
        )

    def _handle_get_device_structure(self, packet: Packet) -> Packet:
        if packet.payload not in self.instantiated_instruments:
            return self._create_error_packet(packet.source, f"Instrument '{packet.payload}' not found.")

        ins_name = packet.payload
        if not isinstance(ins_name, str):
            return self._create_error_packet(
                packet.source, f"Payload must be the instrument name as a string, not {type(ins_name)}"
            )

        params = self.instantiated_instruments[ins_name].parameters
        operations = set(self.instantiated_instruments[ins_name].operations.keys())

        payload = {
            "name": self.instantiated_instruments[ins_name].name,
            "desc": self.instantiated_instruments[ins_name].desc,
            "address": self.instantiated_instruments[ins_name].address,
            "parameters": params,
            "operations": operations,
        }

        return Packet(
            intent=PacketIntent.DATA,
            request="GET_DEVICE_STRUCTURE",
            source=self.name,
            destination=packet.source,
            payload=payload,
        )

    def _validate_instrument_control_packet(
        self, packet: Packet
    ) -> tuple[str, str, str, DeviceDriver, tuple[Any, ...], dict[str, Any]] | Packet:
        request_parts = packet.request.split(":")
        correct_request_len = 3
        if len(request_parts) != correct_request_len:
            msg = (
                f"CONTROL packets should have a request field with 3 parts divided by a ':', "
                f"not {len(request_parts)}, formatted as: "
                f"<instrument_name>:<OPERATION/PARAMETER/INFO>:<Operation/Parameter name/empty for info>"
            )
            return self._create_error_packet(packet.source, msg)

        ins_name, request_type, request_name = request_parts
        if ins_name not in self.instantiated_instruments:
            return self._create_error_packet(packet.source, f"Instrument '{ins_name}' not found.")

        instrument = self.instantiated_instruments[ins_name]

        if request_type not in ["OPERATION", "PARAMETER", "INFO"]:
            msg = f"Request type must be either 'OPERATION', 'PARAMETER', 'INFO', not {request_type}"
            return self._create_error_packet(packet.source, msg)

        if not isinstance(packet.payload, tuple):
            msg = (
                f"Payload must be a tuple with the arguments and kwargs (have empty args and kwargs "
                f"if not necessary) for the operation or parameter, not {type(packet.payload)}"
            )
            return self._create_error_packet(packet.source, msg)

        args, kwargs = packet.payload
        return ins_name, request_type, request_name, instrument, args, kwargs

    def _handle_operation_control(
        self, request_name: str, instrument: DeviceDriver, packet: Packet, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> Packet:
        if request_name not in instrument.operations:
            return self._create_error_packet(
                packet.source, f"Operation '{request_name}' not found in '{instrument.name}'"
            )

        try:
            operation_ret = instrument.operations[request_name](*args, **kwargs)
        # Adding ruff exception due to not know what type of exceptions instruments can raise.
        except Exception as e:  # noqa:BLE001
            msg = f"Error executing operation '{request_name}' in '{instrument.name}'. Error: {e}"
            return self._create_error_packet(packet.source, msg)

        return self._create_control_packet(packet.source, f"{instrument.name}:OPERATION:{request_name}", operation_ret)

    def _handle_parameter_control(
        self, request_name: str, instrument: DeviceDriver, packet: Packet, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> Packet:
        if request_name not in instrument.parameters:
            return self._create_error_packet(
                packet.source, f"Parameter '{request_name}' not found in '{instrument.name}'"
            )

            # Check if this is just reading the parameter or setting it.
        if len(args) == 0 and len(kwargs) == 0:
            try:
                parameter_ret = getattr(instrument, request_name)
            except AttributeError as e:
                msg = f"Error reading parameter '{request_name}' in '{instrument.name}'. Error: {e}"
                return self._create_error_packet(packet.source, msg)

            return self._create_control_packet(
                packet.source, f"{instrument.name}:PARAMETER:{request_name}", parameter_ret
            )

        try:
            setattr(instrument, request_name, *args, **kwargs)
            # TODO: Double check this exception type, I am not entirely sure this would work.
        except AttributeError as e:
            msg = f"Error setting parameter '{request_name}' in '{instrument.name}'. Error: {e}"
            return self._create_error_packet(packet.source, msg)

        return self._create_control_packet(packet.source, f"{instrument.name}:PARAMETER:{request_name}", "OK")

    def _handle_instrument_control(self, packet: Packet) -> Packet:
        validated_packet = self._validate_instrument_control_packet(packet)

        # If it's a packet it means that there was an error with the incoming packet so return the error packet.
        if isinstance(validated_packet, Packet):
            return validated_packet

        ins_name, request_type, request_name, instrument, args, kwargs = validated_packet

        if request_type == "OPERATION":
            return self._handle_operation_control(request_name, instrument, packet, args, kwargs)

        if request_type == "PARAMETER":
            return self._handle_parameter_control(request_name, instrument, packet, args, kwargs)

        if request_type == "INFO":
            return self._create_control_packet(packet.source, f"{ins_name}:INFO", instrument.info())

        # All the possible packet options should have been handled by now, so if we get here, something went wrong.
        msg = f"Something inside node {self.name} went wrong. Check that your packet is correct and try again."
        return self._create_error_packet(packet.source, msg)

    def _create_error_packet(self, destination: str, error_msg: str) -> Packet:
        return Packet(
            intent=PacketIntent.ERROR,
            request="ERROR",
            source=self.name,
            destination=destination,
            payload=error_msg,
        )

    def _create_control_packet(self, destination: str, request: str, payload: Any) -> Packet:
        return Packet(
            intent=PacketIntent.CONTROL,
            request=request,
            source=self.name,
            destination=destination,
            payload=payload,
        )
