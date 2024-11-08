import logging

from pqnstack.network.client import Client
from pqnstack.network.packet import Packet
from pqnstack.network.packet import PacketIntent

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    c = Client()

    # ping node
    ping_reply = c.ping("node1")
    print(ping_reply)

    devices = c.get_available_devices("node1")
    print(devices)

    # Create instrument proxy
    instrument = c.get_device("node1", "dummy1")
    print(instrument)
    print(f'I should have the proxy object here: {type(instrument)}')

    # Call a method on the instrument
    ret = instrument.double_int()

    print(ret)

    # Callable
    call = instrument.double_int
    print(type(call))

    # Pass argument to operation
    ret = instrument.set_half_input_int(10)
    print(ret)

    # Passing keyword arguments
    ret = instrument.set_half_input_int(value=36)
    print(ret)