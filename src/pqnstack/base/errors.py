# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes


class DriverNotFound(Exception):
    def __init__(self, driver, message="Device driver configuration not found"):
        self.driver = driver
        self.message = message
        super().__init__(self.message)


class DriverFunctionNotImplemented(Exception):
    def __init__(self, driver, message="One or more driver functions were not implemented"):
        self.driver = driver
        self.message = message
        super().__init__(self.message)


class DriverFunctionUnknown(Exception):
    def __init__(self, driver, message="Device driver function unknown"):
        self.driver = driver
        self.message = message
        super().__init__(self.message)