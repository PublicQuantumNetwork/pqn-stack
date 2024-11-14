import logging

from pqnstack.network.node import Node

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    node = Node("node1", "127.0.0.1", 5555)
    node.start()
