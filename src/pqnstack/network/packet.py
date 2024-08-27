# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
#
#
from dataclasses_json import dataclass_json
from dataclasses import dataclass
from typing import Tuple
from enum import Enum


@dataclass_json
@dataclass
class Packet:
    intent: str
    request: str
    source: Tuple[int, int]
    destination: Tuple[int, int]
    hops: int
    payload: object

    def signature(self):
        return self.intent, self.request

    def routing(self):
        return self.source, self.destination


class PacketIntent(Enum):
    DATA = 1
    CTRL = 2
    RTNG = 3


class PacketRequest(Enum):
    MSR = 1
