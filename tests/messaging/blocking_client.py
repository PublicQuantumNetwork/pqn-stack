import logging

from pqnstack.network.client import Client

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    c = Client()

    # ping provider
    ping_reply = c.ping("provider1")
    logger.info(ping_reply)

    instrument = c.get_device("provider1", "dummy1")
    logger.info(instrument)

    # blocking operation
    instrument.toggle_bool_long()
