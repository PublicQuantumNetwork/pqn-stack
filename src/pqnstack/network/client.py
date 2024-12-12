import logging
import pickle
import random
import string
from collections.abc import Callable
from types import TracebackType
from typing import Self

import zmq

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.errors import PacketError
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
        port: int = 5555,
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
        self.context: zmq.Context[zmq.Socket[bytes]] | None = None
        self.socket: zmq.Socket[bytes] | None = None

        self.connect()

    def __enter__(self) -> Self:
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

    def ask(self, packet: Packet) -> Packet:
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
        except zmq.error.Again as e:
            logger.error("Timeout occurred.")
            raise TimeoutError() from e

        ret: Packet = pickle.loads(response)
        logger.debug("Response received.")
        logger.debug("Response: %s", str(ret))
        if ret.intent == PacketIntent.ERROR:
            raise PacketError(str(ret))

        return ret

    def create_control_packet(self, destination: str, request: str, payload: tuple[tuple, dict[str, Any]]) -> Packet:
        return Packet(
            intent=PacketIntent.CONTROL,
            request=request,
            source=self.name,
            destination=destination,
            payload=payload,
        )

    def create_data_packet(self, destination: str, request: str, payload: Any) -> Packet:
        return Packet(
            intent=PacketIntent.DATA,
            request=request,
            source=self.name,
            destination=destination,
            payload=payload,
        )


class InstrumentClient(ClientBase):
    def __init__(self, name: str, host: str, port: int, router_name: str, instrument_name: str, node_name: str) -> None:
        super().__init__(name, host, port, router_name)

        self.instrument_name = instrument_name
        self.node_name = node_name

    def trigger_operation(self, operation: str, *args, **kwargs) -> Any:
        packet = self.create_control_packet(
            self.node_name, self.instrument_name + ":OPERATION:" + operation, (args, kwargs)
        )
        response = self.ask(packet)

        return response.payload

    def trigger_parameter(self, parameter: str, *args, **kwargs) -> Any:
        packet = self.create_control_packet(
            self.node_name, self.instrument_name + ":PARAMETER:" + parameter, (args, kwargs)
        )

        response = self.ask(packet)
        return response.payload

    def get_info(self) -> DeviceInfo:
        packet = self.create_control_packet(self.node_name, self.instrument_name + ":INFO:", ((), {}))

        response = self.ask(packet)
        if not isinstance(response.payload, DeviceInfo):
            msg = "Asking for info to proxy driver did not get a DeviceInfo object."
            raise PacketError(msg)

        return response.payload


class ProxyInstrument(DeviceDriver):
    """The address here is the zmq address of the router that the InstrumentClient will talk to."""

    DEVICE_CLASS = DeviceClass.PROXY

    def __init__(
        self,
        name: str,
        desc: str,
        address: str,
        host: str,
        port: int,
        node_name: str,
        router_name: str,
        parameters: set[str],
        operations: dict[str, Callable],
    ) -> None:
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
        client_name = (
            name
            + "_client_"
            + "".join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=6))
        )

        self.client = InstrumentClient(
            name=client_name,
            host=self.host,
            port=self.port,
            router_name=self.router_name,
            instrument_name=name,
            node_name=self.node_name,
        )

        self._instantiating = False

    def __getattr__(self, name: str) -> Any:
        if name in self.operations:
            return lambda *args, **kwargs: self.client.trigger_operation(name, *args, **kwargs)
        if name in self.parameters:
            return self.client.trigger_parameter(name)
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
        msg = "Cannot manually set attributes in a ProxyInstrument"
        raise AttributeError(msg)

    def start(self) -> None:
        pass

    def close(self) -> None:
        self.client.disconnect()

    def info(self) -> DeviceInfo:
        return self.client.get_info()


class Client(ClientBase):
    def ping(self, destination: str) -> Packet | None:
        ping_packet = Packet(
            intent=PacketIntent.PING, request="PING", source=self.name, destination=destination, hops=0, payload=None
        )
        return self.ask(ping_packet)

    def get_available_devices(self, node_name: str) -> dict[str, str]:
        packet = self.create_data_packet(node_name, "GET_DEVICES", None)
        response = self.ask(packet)

        assert isinstance(response.payload, dict)
        return response.payload

    def get_device(self, node_name: str, device_name: str) -> DeviceDriver:
        packet = self.create_data_packet(node_name, "GET_DEVICE_STRUCTURE", device_name)

        response = self.ask(packet)

        if response.intent == PacketIntent.ERROR:
            raise PacketError(str(response))

        assert isinstance(response.payload, dict)

        return ProxyInstrument(
            host=self.host, port=self.port, node_name=node_name, router_name=self.router_name, **response.payload
        )
