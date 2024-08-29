# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes
import math
import time
from typing import Any

import zmq

from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.errors import DriverFunctionNotImplementedError
from pqnstack.base.errors import DriverFunctionUnknownError


class IDQTimeTagger(DeviceDriver):
    def __init__(self, specs: dict) -> None:
        # Data structures unique to this class
        self.tc = None
        self.tc_ip = None
        self.tc_port = None

        # Init parent class
        super.__init__(specs)

    def setup(self, specs: dict) -> None:
        # Connect to the time tagger
        context = zmq.Context()
        self.tc = context.socket(zmq.REQ)
        self.tc.connect(f"tcp://{self.tc_ip}:{self.tc_port}")

        # Map each executable function to their internal implementation
        self.executable["set_delay"] = self.__set_delay
        self.executable["single_counts"] = self.__single_counts
        self.executable["coincidence_counts"] = self.__coincidence_counts
        self.executable["tsco_numbers"] = self.__tsco_numbers
        self.executable["histogram"] = self.__histogram
        self.executable["channel_acquis"] = self.__channel_acquis

        # Check all implementations were provided
        if set(self.provides).symmetric_difference(self.executable.keys()) != set():
            msg = "IDQTimeTagger"
            raise DriverFunctionNotImplementedError(msg)

        # Set device as on
        self.status = DeviceStatus.ON

    def exec(self, seq: str, **kwargs) -> dict:
        if str not in self.executable:
            msg = "IDQTimeTagger"
            raise DriverFunctionUnknownError(msg)

        self.executable[seq](**kwargs)

    # Hardware level implementation of executable functions
    # =====================================================

    def __hw_command(self, cmd: str) -> str:
        self.tc.send_string(cmd)
        return self.tc.recv().decode("utf-8")

    def __set_delay(self, **kwargs) -> None:
        command = f"INPU{kwargs['channel']}:DELAY {kwargs['delay']}"
        self.__hw_command(command)

    def __single_counts(self, **kwargs) -> int:
        command = f"INPU{kwargs['channel']}:COUN?"
        return int(self.__hw_command(command))

    def __coincidence_counts(self, **kwargs) -> int:
        command = (
            f"TSCO6:LINK {kwargs['channel1']}; TSCO6:LINK {kwargs['channel2']}; TSCO6:COUN:INTE "
            f"{kwargs['interval']}"
        )
        self.__hw_command(command)
        command = "TSCO6:COUN?"
        return int(self.__hw_command(command))

    def __tsco_numbers(self, **kwargs) -> list:
        tsco_nums = []
        command = f"TSCO6:LINK {kwargs['channel1']}; TSCO6:LINK {kwargs['channel2']}; TSCO6:COUN:INTE 1000"
        self.__hw_command(command)
        command = "TSCO6:COUN?"
        # Dump the next value, possibly due to hardware protocol
        _ = int(self.__hw_command(command))

        for i in range(self.params["tsco_iters"]):
            time.sleep(self.params["cmd_wait"])
            command = f"TSCO{i}:LINK {kwargs['channel1']}; TSCO6:LINK {kwargs['channel2']}; TSCO6:COUN:INTE 1000"
            self.__hw_command(command)
            command = f"TSCO{i}:COUN?"
            tsco_nums.append(self.__hw_command(command))

        return tsco_nums

    # FIXME: Not sure what the return type for this method should be.
    def __histogram(self, **kwargs) -> Any:
        # Set histogram properties in multiples of 100 ps
        min_val_rounded = round(self.params["hist_min_val"] / 100) * 100
        bin_width_rounded = round(self.params["hist_bin_width"] / 100) * 100
        bin_count = math.ceil((self.params["hist_max_val"] - self.params["hist_min_val"]) / bin_width_rounded)

        for i in range(1, self.params["hist_channels"]):
            command = f"HIST{i}:MIN {min_val_rounded}; HIST{i}:BWID {bin_width_rounded}; HIST{i}:BCOU " f"{bin_count}"
            self.__hw_command(command)

        # Flush time tagger memory buffers
        for i in range(1, self.params["hist_channels"]):
            self.__hw_command(f"HIST{i}:FLUS")

        # Record for the amount specified by `duration` entered in seconds
        self.__hw_command("REC:ENAB ON")
        self.__hw_command(f"REC1:DUR {kwargs['duration'] * 1_000_000_000}")
        self.__hw_command("REC:PLAY")
        time.sleep(kwargs["duration"])
        self.__hw_command("REC:STOP")

        # Return resulting histogram
        return self.__hw_command("HIST1:DATA?")

    # FIXME: Not sure what the return type for this method should be.
    def __channel_acquis(self, **kwargs) -> Any:
        command = f"INPU{kwargs['channel']}:COUN:INTE {kwargs['value']}"
        return self.__hw_command(command)
