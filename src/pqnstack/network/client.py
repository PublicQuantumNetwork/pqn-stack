import logging
import pickle
import random
import string
from types import TracebackType
from typing import Any

import zmq

from pqnstack.base.errors import PacketError
from pqnstack.base.driver import DeviceDriver, DeviceClass
from pqnstack.network.packet import NetworkElementClass
from pqnstack.network.packet import Packet
from pqnstack.network.packet import PacketIntent
from pqnstack.network.packet import create_registration_packet

logger = logging.getLogger(__name__)


class ClientBase:

    def __init__(self, name: str = "",
                 host: str = "127.0.0.1",
                 port: int | str = 5555,
                 router_name: str = "router1",
                 timeout: int = 5000) -> None:

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

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc_val: BaseException | None,
                 exc_tb: TracebackType | None) -> None:
        self.disconnect()

    def connect(self) -> None:
        logger.info("Starting client '%s' Connecting to %s", self.name, self.address)
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
        if ret.intent == PacketIntent.ERROR:
            raise PacketError(str(ret))

        return ret


class InstrumentClient(ClientBase):

    def __init__(self, name: str,
                 host: str,
                 port: int | str,
                 router_name: str,
                 instrument_name: str,
                 node_name: str) -> None:
        super().__init__(name, host, port, router_name)

        self.instrument_name = instrument_name
        self.node_name = node_name

    def get_device_structure(self):
        packet = Packet(intent=PacketIntent.DATA,
                        request="GET_DEVICE_STRUCTURE",
                        source=self.name,
                        destination=self.node_name,
                        payload=self.instrument_name)
        response = self.ask(packet)

        if response.intent == PacketIntent.ERROR:
            raise PacketError(str(response))

    def trigger_operation(self, operation: str, *args, **kwargs) -> Any:
        packet = Packet(intent=PacketIntent.CONTROL,
                        request=str(self.instrument_name) + ":OPERATION:" + operation,
                        source=self.name,
                        destination=self.node_name,
                        payload=(args, kwargs)
                        )
        response = self.ask(packet)
        return response.payload

    def trigger_parameter(self, parameter: str, *args, **kwargs) -> Any:
        packet = Packet(intent=PacketIntent.CONTROL,
                        request=str(self.instrument_name) + ":PARAMETER:" + parameter,
                        source=self.name,
                        destination=self.node_name,
                        payload=(args, kwargs))
        response = self.ask(packet)
        return response.payload


class ProxyInstrument(DeviceDriver):
    """
    The address here is the zmq address of the router that the InstrumentClient will talk to.
    """

    DEVICE_CLASS = DeviceClass.PROXY

    def __init__(self, name: str,
                 desc: str,
                 address: str,
                 host: str,
                 port: str,
                 node_name: str,
                 router_name: str,
                 parameters: set[str],
                 operations=set[str]) -> None:

        # Boolean used to control when new attributes are being set.
        self._instantiating = True

        super().__init__(name, desc, address)

        self.host = host
        self.port = port

        self.parameters = parameters
        self.operations = operations

        self.node_name = node_name
        self.router_name = router_name

        # The client's name is the instrument name with "_client" appended and a random 6 character string appended.
        # This is to avoid any potential conflicts with other clients.
        client_name = name + "_client_" + "".join(
            random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=6))

        self.client = InstrumentClient(name=client_name,
                                       host=self.host,
                                       port=self.port,
                                       router_name=self.router_name,
                                       instrument_name=name,
                                       node_name=self.node_name)

        self._instantiating = False

    def __getattr__(self, name: str) -> Any:
        try:
            return super().__getattr__(name)
        except AttributeError as e:
            logger.debug("Attribute %s not found in %s. Trying to find it in the client.", name, self.name)

        if name in self.operations:
            return lambda *args, **kwargs: self.client.trigger_operation(name, *args, **kwargs)
        if name in self.parameters:
            return self.client.trigger_parameter(name)
            pass
        else:
            msg = f"Attribute '{name}' not found."
            raise AttributeError(msg)

    def __setattr__(self, name: str, value: Any) -> None:
        # Catch the first iteration
        if name == "_instantiating" or self._instantiating:
            super().__setattr__(name, value)
            return
        if name in self.parameters:
            self.client.trigger_parameter(name, value)
            return

        raise AttributeError(f"Cannot manually set attributes in a ProxyInstrument")

    def start(self) -> None:
        pass

    def close(self) -> None:
        self.client.disconnect()

    def info(self) -> None:
        pass


class Client(ClientBase):

    def ping(self, destination: str) -> Packet | None:
        ping_packet = Packet(intent=PacketIntent.PING,
                             request="PING",
                             source=self.name,
                             destination=destination,
                             hops=0,
                             payload=None)
        return self.ask(ping_packet)

    def get_available_devices(self, node_name: str) -> dict[str, str]:
        packet = Packet(intent=PacketIntent.DATA,
                        request="GET_DEVICES",
                        source=self.name,
                        destination=node_name,
                        hops=0,
                        payload=None)
        response = self.ask(packet)
        if response is None:
            return {}

        assert isinstance(response.payload, dict)
        return response.payload

    def get_device(self, node_name: str, device_name: str) -> DeviceDriver:

        packet = Packet(intent=PacketIntent.DATA,
                        request="GET_DEVICE_STRUCTURE",
                        source=self.name,
                        destination=node_name,
                        payload=device_name)

        response = self.ask(packet)
        if response.intent == PacketIntent.ERROR:
            raise PacketError(str(response))

        assert isinstance(response.payload, dict)

        return ProxyInstrument(host=self.host,
                               port=self.port,
                               node_name=node_name,
                               router_name=self.router_name,
                               **response.payload)




