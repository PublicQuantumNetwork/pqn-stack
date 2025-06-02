import logging

from pqnstack.network.client import Client

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    c = Client()

    # ping provider
    ping_reply = c.ping("provider1")
    logger.info(ping_reply)

    devices = c.get_available_devices("provider1")
    logger.info(devices)

    # Create instrument proxy
    instrument = c.get_device("provider1", "dummy1")
    logger.info(instrument)
    logger.info("I should have the proxy object here: %s", type(instrument))

    # Call a method on the instrument
    ret = instrument.double_int()

    logger.info(ret)

    # Callable
    call = instrument.double_int
    logger.info(type(call))

    # Pass argument to operation
    ret = instrument.set_half_input_int(10)
    logger.info(ret)

    # Passing keyword arguments
    ret = instrument.set_half_input_int(value=36)
    logger.info(ret)

    # Get a parameter
    param = instrument.param_int
    logger.info(param)

    param_str = instrument.param_str
    logger.info(param_str)

    # Set a parameter
    instrument.param_int = 42
    logger.info(instrument.param_int)

    # Set a parameter
    try:
        instrument.new_attr = 348
    except AttributeError as e:
        logger.info("Caught exception: %s cannot set parameter", e)

    logger.info("Proxy instrument seems to be working correctly.")
