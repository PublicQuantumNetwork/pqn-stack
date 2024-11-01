import logging

from pqnstack.network.router import Router2

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    print("starting router")
    router = Router2("router1", "127.0.0.1", 5555)
    router.start()


