import logging

from pqnstack.network.node import Node

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    instruments = {
        "signal_hwp": {
            "import": "pqnstack.pqn.drivers.rotator.APTRotatorDevice",
            "desc": "signal hwp",
            "address": "83832034",
            "offset_degrees": 234.1306,
        },
        "idler_hwp": {
            "import": "pqnstack.pqn.drivers.rotator.SerialRotatorDevice",
            "desc": "idler hwp",
            "address": "/dev/ttyUSB0",
        }
    }
    node = Node("loomis_server", "172.30.63.109", 5555, **instruments)
    node.start()
