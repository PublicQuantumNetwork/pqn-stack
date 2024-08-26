# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

from pqnstack.base.driver import DeviceDriver
from typing import Dict


class WavePlate(DeviceDriver):

    def __init__(self, specs: Dict):
        super.__init__(specs)

    def setup(self, specs: Dict):
        pass

    def exec(self, seq: str):
        pass

