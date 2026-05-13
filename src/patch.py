import sys
INPUT_PORT = int(sys.argv[1])
OUTPUT_PORT = 15

import logging
from pqnstack.pqn.drivers.switch import Switch

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

switch = Switch("switch", "POLATIS test unit", "192.168.0.1", 8008, "admin", "root")
switch.start()

# Remove all existing patches
logger.info("Removing existing patches")
for i in range(8):
    switch.remove_patch(i+1)

# Add a new patch from INPUT_PORT to OUTPUT_PORT
logger.info("Creating new patch")
switch.add_patch(INPUT_PORT, OUTPUT_PORT)
