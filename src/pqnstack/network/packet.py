# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
#
#
from dataclasses import dataclass
from enum import Enum, auto


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
    hops: int
    payload: object
    version: int = 1

    def signature(self) -> tuple[str, str, str]:
        return self.intent.name, self.request, str(self.payload)

    def routing(self) -> tuple[tuple[int, int], tuple[int, int]]:
        return self.source, self.destination


class PacketRequest(Enum):
    MSR = 1


@dataclass()
class RegistrationPacket(Packet):

    def __init__(self, source, destination, element_type: NetworkElementClass, hops) -> None:
        super().__init__(intent=PacketIntent.REGISTRATION,
                         source=source,
                         request="REGISTER",
                         destination=destination,
                         hops=hops,
                         payload=element_type)


