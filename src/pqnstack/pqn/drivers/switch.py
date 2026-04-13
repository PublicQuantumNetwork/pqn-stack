import json
import logging
import requests
from dataclasses import dataclass

from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class HTTPResponse():
    code: int = None
    reason: str = None
    data: dict = None

@dataclass(frozen=True, slots=True)
class SwitchInfo(InstrumentInfo):
    serial_number: str = None
    model: str = None
    software_version: str = None

class Switch(Instrument):
    # The IP address used to connect to the switch's management interface
    _ip_address: str

    # The port number used to connect to the switch's management interface
    _port: int

    # The username used to log into the switch
    _username: str

    # The password used to log into the switch
    _password: str

    """
    Initializes variables and performs a connection test

    Args:
        ip_address: The IP address used to connect to the switch's management interface
        port:       The port number used to connect to the switch's management interface
        username:   The username used to log into the switch
        password:   The password used to log into the switch
    """
    def __init__(self, ip_address: str = "192.168.0.1", port: int = 8008, username: str = "admin", password: str = "root") -> None:

        # Initialize variables
        self._ip_address = ip_address
        self._port = port
        self._username = username
        self._password = password

        logger.info("Performing connection test")

        # Connection test
        response = self._http_request("GET", "/api")
        if (response.code == 200):
            logger.info("Connection test succeeded")
        else:
            logger.error(f"Connection test failed: Received unexpected HTTP response {response.code}")
            raise SwitchAPIError(f"Connection test failed: Received unexpected HTTP response {response.code}")

    def _http_request(self, method: str, path: str, data: dict = None, is_xml: bool = False) -> HTTPResponse:
        if (is_xml):
            response = requests.request(
                method,
                f"http://{self._ip_address}:{str(self._port)}{path}",
                auth=(
                    self._username,
                    self._password
                ),
                headers={
                    "Accept": "application/yang-data+xml"
                },
                data=data
            )
        else:
            response = requests.request(
                method,
                f"http://{self._ip_address}:{str(self._port)}{path}",
                auth=(
                    self._username,
                    self._password
                ),
                headers={
                    "Accept": "application/yang-data+json"
                },
                json=data
            )

        log_msg = f"{method} http://{self._ip_address}:{str(self._port)}{path}: {response.status_code} {response.reason}"

        # Handle 401 Unauthorized
        if response.status_code == 401:
            logger.error(log_msg)
            raise SwitchAPIError(log_msg)
        
        # Otherwise return data
        else: 
            logger.info(log_msg)
            if is_xml:
                return HTTPResponse(response.status_code, response.reason, response.text)
            else:
                return HTTPResponse(response.status_code, response.reason, response.json() if response.text.strip() else {})

    def info(self) -> SwitchInfo:
        response = self._http_request("GET", "/api/data/optical-switch:product-information")
        # TODO: What is the convention for the name and desc fields?
        # TODO: what info to include in hw_status?
        return SwitchInfo("TODO", "TODO", self._ip_address + ":" + str(self._port), None, response.data["optical-switch:product-information"]["serial-number"], response.data["optical-switch:product-information"]["model-name"], response.data["optical-switch:product-information"]["software-version"])
    
    def get_egress(self, ingress: int) -> int:
        response = self._http_request("GET", "/api/data/optical-switch:cross-connects/pair=" + str(ingress))

        if (response.code == 200):
            return int(response.data["optical-switch:pair"]["egress"])
        elif (response.code == 204):
            return None
        else:
            raise SwitchAPIError(f"Received unexpected HTTP response {response.code}")

    def get_patches(self) -> None:
        response = self._http_request("GET", "/api/data/optical-switch:cross-connects")

        if (response.code == 200):
            return response.data["optical-switch:cross-connects"]["pair"]
        elif (response.code == 204):
            return None
        else:
            raise SwitchAPIError(f"Received unexpected HTTP response {response.code}")

    def add_patch(self, ingress: int, egress: int) -> None:
        response = self._http_request("POST", 
            "/api/data/optical-switch:cross-connects",
            "<pair><ingress>" + str(ingress) + "</ingress><egress>" + str(egress) + "</egress></pair>",
            True
        )

        if (response.code == 409):
            logger.warning(f"Unable to patch {ingress} to {egress} - one or both ports are already in use")
        elif (response.code == 201):
            logger.info(f"Successfully patched {ingress} to {egress}")
        else:
            raise SwitchAPIError(f"Received unexpected HTTP response {response.code}")

    def remove_patch(self, ingress: int) -> None:
        response = self._http_request("DELETE", "/api/data/optical-switch:cross-connects/pair=" + str(ingress))
        
        if (response.code == 404):
            logger.warning(f"Unable to remove patch from port {ingress} - existing patch does not exist on this port")
        elif (response.code == 204):
            logger.info(f"Successfully removed patch from {ingress}")
        else:
            raise SwitchAPIError(f"Received unexpected HTTP response {response.code}")
        
    # TODO: implement methods to enable/disable a port or check its status

"""Raised when the switch returns an unexpected or invalid response from the API"""
class SwitchAPIError(Exception):
    pass
