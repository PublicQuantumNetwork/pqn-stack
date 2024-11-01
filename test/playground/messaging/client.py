from pqnstack.network.client import ClientBase
from pqnstack.network.packet import Packet, PacketIntent


if __name__ == "__main__":
    c = ClientBase()
    ping_packet = Packet(intent=PacketIntent.PING, request="PING", source=c.name, destination="node1", hops=0, payload=None)
    response = c.ask(ping_packet)
    print(response)
    print("done")
