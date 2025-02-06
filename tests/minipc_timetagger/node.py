import logging

from pqnstack.network.node import Node

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    instruments = {
        "tagger": {
            "import": "pqnstack.pqn.drivers.timetagger.SwabianTimeTagger",
            "desc": "SwabianTimeTagger",
            "address": "2410001AE",
        }
    }
    node = Node("mini_pc", "172.30.63.109", 5555, **instruments)
    node.start()
