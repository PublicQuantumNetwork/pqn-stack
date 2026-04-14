import logging
from pqnstack.pqn.drivers.switch import Switch
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

logger = logging.getLogger(__name__)
sw = Switch("192.168.0.1", 8008, "admin", "root")
#sw.add_patch(1, 9)
sw.remove_patch(1)
