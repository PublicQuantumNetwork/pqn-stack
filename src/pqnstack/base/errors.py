# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
from pqnstack.base.driver import Driver


class DriverNotFoundError(Exception):
    def __init__(self, driver: Driver, message: str = "Device driver configuration not found") -> None:
        self.driver = driver
        self.message = message
        super().__init__(self.message)


class DriverFunctionNotImplementedError(Exception):
    def __init__(self, driver: Driver, message: str = "One or more driver functions were not implemented") -> None:
        self.driver = driver
        self.message = message
        super().__init__(self.message)


class DriverFunctionUnknownError(Exception):
    def __init__(self, driver: Driver, message: str = "Device driver function unknown") -> None:
        self.driver = driver
        self.message = message
        super().__init__(self.message)
