import logging

from pqnstack.network.node import Node2

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    print("starting node1")
    node = Node2("node1", "127.0.0.1", 5555)
    print("done with node1")
