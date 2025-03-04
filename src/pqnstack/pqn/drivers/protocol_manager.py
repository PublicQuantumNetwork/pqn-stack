from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation
from pqnstack.base.driver import log_parameter
from pqnstack.base.errors import DeviceNotStartedError
from pqnstack.network.client import Client
import logging
from dataclasses import dataclass

from time import sleep

logger = logging.getLogger(__name__)

class ProtocolManager(DeviceDriver):
    DEVICE_CLASS = DeviceClass.MANAGER

