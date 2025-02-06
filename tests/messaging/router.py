import logging

from pqnstack.network.router import Router

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    router = Router("router1", "172.30.63.109", 5555)
    router.start()
