# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes


class DeviceNotStartedError(Exception):
    def __init__(self, message: str = "Device not started") -> None:
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


class LogDecoratorOutsideOfClassError(Exception):
    def __init__(self, message: str = "Log decorator used outside of a class") -> None:
        self.message = message
        super().__init__(self.message)


class PacketError(Exception):
    def __init__(self, message: str = "Packet error") -> None:
        self.message = message
        super().__init__(self.message)


