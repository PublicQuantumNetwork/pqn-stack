# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes


class InvalidDriverError(Exception):
    """Not in errors file because DeviceDriver needs it and it leads to infinite imports."""
    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(self.message)


class DriverNotFoundError(Exception):
    def __init__(self, message: str = "Device driver configuration not found") -> None:
        self.message = message
        super().__init__(self.message)


class DriverFunctionNotImplementedError(Exception):
    def __init__(self, message: str = "One or more driver functions were not implemented") -> None:
        self.message = message
        super().__init__(self.message)


class DriverFunctionUnknownError(Exception):
    def __init__(self, message: str = "Device driver function unknown") -> None:
        self.message = message
        super().__init__(self.message)
