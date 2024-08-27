# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes


from pqnstack.base.driver import DeviceDriver


class WavePlate(DeviceDriver):
    def __init__(self, specs: dict):
        super.__init__(specs)

    def setup(self, specs: dict):
        pass

    def exec(self, seq: str):
        pass
