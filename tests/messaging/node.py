import logging

from pqnstack.network.node import Node

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    instruments = {
        "dummy1": {
            "import": "pqnstack.pqn.drivers.dummies.DummyInstrument",
            "desc": "Dummy Instrument 1",
            "address": "123456",
        }
    }
    node = Node("node1", "127.0.0.1", 5555, **instruments)
    node.start()
