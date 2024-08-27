# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes


class DriverNotFoundError(Exception):
    def __init__(self, driver, message="Device driver configuration not found"):
        self.driver = driver
        self.message = message
        super().__init__(self.message)


class DriverFunctionNotImplementedError(Exception):
    def __init__(self, driver, message="One or more driver functions were not implemented"):
        self.driver = driver
        self.message = message
        super().__init__(self.message)


class DriverFunctionUnknownError(Exception):
    def __init__(self, driver, message="Device driver function unknown"):
        self.driver = driver
        self.message = message
        super().__init__(self.message)
