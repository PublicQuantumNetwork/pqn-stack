import logging

from pqnstack.network.router import Router

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    router = Router("router1", "127.0.0.1", 5555)
    router.start()
