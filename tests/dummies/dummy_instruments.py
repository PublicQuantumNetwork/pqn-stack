# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

from pqnstack.base.driver import DeviceDriver, DeviceInfo, DeviceClass, DeviceStatus, Parameter, Operation


class DummyCommunicator:
    """
    The following is a dummy class to simulate having to handle a communications class.
    """

    def __init__(self, address: str):
        self.address = address

        self._dummy_int = 0
        self._dummy_str = ""
        self._dummy_bool = False
        self._cookie_counter = 0
        self._cookie_str = f"I have eaten {self._cookie_counter} cookies."

        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def send_command(self, command: str) -> str:

        if not self._connected:
            raise ConnectionError("Communicator not connected.")

        if len(command.split(":")) != 2:
            raise ValueError("Command not formatted correctly.")

        cmd, value = command.split(":")

        match cmd:
            case "set_dummy_int":
                self._dummy_int = int(value)
            case "get_dummy_int":
                return str(self._dummy_int)
            case "set_dummy_str":
                self._dummy_str = value
            case "get_dummy_str":
                return self._dummy_str
            case "set_dummy_bool":
                self._dummy_bool = bool(value)
            case "get_dummy_bool":
                return str(self._dummy_bool)
            case "eat_cookie":
                if value == "":
                    self._cookie_counter += 1
                else:
                    self._cookie_counter += int(value)
                self._cookie_str = f"I have eaten {self._cookie_counter} cookies."
            case "how_many_cookies":
                return self._cookie_counter
            case "connected":
                return str(self._connected)
            case _:
                raise ValueError("Command not recognized.")

    def disconnect(self) -> None:
        self._connected = False


class DummyInfo(DeviceInfo):
    address: str
    dummy_int: int
    dummy_str: str
    dummy_bool: bool


class DummyDriver(DeviceDriver):

    # FIXME: Why do we need a setup and init? Can't we just use the init?
    def __init__(self, specs: dict) -> None:
        self.device: DummyCommunicator | None = None

        if "dtype" in specs:
            print("dtype set by driver itself, argument will be ignored.")

        # FIXME: Once the basic driver accepts individual arguments, we can simply pass dtype
        specs["dtype"] = DeviceClass.TESTING
        super().__init__(specs)

    def setup(self, specs: dict) -> None:
        self.device = DummyCommunicator(specs["address"])
        self.device.connect()

    @Parameter
    def dummy_int(self) -> int:
        return int(self.device.send_command(f"get_dummy_int:"))

    @dummy_int.setter
    def dummy_int(self, value: int) -> None:
        self.device.send_command(f"set_dummy_int:{value}")

    @Parameter
    def dummy_str(self) -> str:
        return self.device.send_command(f"get_dummy_str:")

    @dummy_str.setter
    def dummy_str(self, value: str) -> None:
        self.device.send_command(f"set_dummy_str:{value}")

    @Parameter
    def dummy_bool(self) -> bool:
        return bool(self.device.send_command(f"get_dummy_bool:"))

    @dummy_bool.setter
    def dummy_bool(self, value: bool) -> None:
        self.device.send_command(f"set_dummy_bool:{value}")

    @Parameter
    def n_cookies(self) -> int:
        return int(self.device.send_command("how_many_cookies:"))

    @Operation
    def feed_cookie_monster(self, cookies: int) -> None:
        self.device.send_command(f"eat_cookie:{cookies}")

    @Operation
    def remove_excess_cookies(self) -> None:
        """
        Checks if the monster has eaten more than 10 cookies and removes the excess.

        Used for testing Operations with no arguments.
        """
        if self.device.send_command("how_many_cookies:") > 10:
            self.device.send_command("eat_cookie:-10")

    def exec(self, seq: str, **kwargs) -> None | dict:
        pass

    def info(self, attr: str, **kwargs) -> dict:
        pass

    def close(self) -> None:
        self.device.disconnect()

