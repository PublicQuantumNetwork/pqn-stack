# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
#
#
from dataclasses import dataclass
from enum import Enum
from enum import auto

from pqnstack.base.errors import PacketError


class NetworkElementClass(Enum):
    ROUTER = auto()
    NODE = auto()
    CLIENT = auto()
    TELEMETRY = auto()


class PacketIntent(Enum):
    DATA = auto()
    OPERATION = auto()
    CONTROL = auto()
    REGISTRATION = auto()
    REGISTRATION_ACK = auto()
    ROUTING = auto()  # These are used for discovering network topology automatically
    PING = auto()
    ERROR = auto()


@dataclass(kw_only=True)
class Packet:
    intent: PacketIntent
    request: str
    source: str
    destination: str
    payload: object
    hops: int = 0
    version: int = 1

    def signature(self) -> tuple[str, str, str]:
        return self.intent.name, self.request, str(self.payload)

    def routing(self) -> tuple[str, str]:
        return self.source, self.destination


def create_registration_packet(**kwargs) -> Packet:
    if "payload" not in kwargs:
        msg = "payload argument not present when creating registration packet."
        raise PacketError(msg)

    if not isinstance(kwargs["payload"], NetworkElementClass):
        msg = "payload argument must be of type NetworkElementClass."
        raise PacketError(msg)

    kwargs |= {"intent": PacketIntent.REGISTRATION, "request": "REGISTER"}
    return Packet(**kwargs)





