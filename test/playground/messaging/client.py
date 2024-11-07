import logging

from pqnstack.network.client import ClientBase
from pqnstack.network.packet import Packet
from pqnstack.network.packet import PacketIntent

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    c = ClientBase()
    ping_packet = Packet(intent=PacketIntent.PING,
                         request="PING",
                         source=c.name,
                         destination="node1",
                         hops=0,
                         payload=None)
    response = c.ask(ping_packet)
    logger.info("Response: %s", response)
    logger.info("Done")
