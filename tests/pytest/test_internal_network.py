import shutil
import subprocess
from pathlib import Path

import pytest

from pqnstack.network.client import Client
from pqnstack.network.client import ProxyInstrument
from pqnstack.network.packet import Packet
from pqnstack.network.packet import PacketIntent
from pqnstack.pqn.drivers.dummies import DummyInstrument


@pytest.fixture
def messaging_services():
    config_path = Path("./test_network_config.toml").resolve()
    uv_path = shutil.which("uv")
    if not uv_path:
        msg = "Could not find 'uv' executable in PATH"
        raise RuntimeError(msg)

    router_process = subprocess.Popen(  # noqa: S603
        [uv_path, "run", "pqn", "start-router", "--config", str(config_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    provider_process = subprocess.Popen(  # noqa: S603
        [uv_path, "run", "pqn", "start-provider", "--config", str(config_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    yield

    router_process.terminate()
    router_process.wait()

    provider_process.terminate()
    provider_process.wait()


def test_client_ping(messaging_services): # noqa: ARG001
    client = Client(host="localhost", port=5556, router_name="pqnstack-router")
    response = client.ping("pqnstack-provider")

    assert isinstance(response, Packet)
    assert response.intent == PacketIntent.PING
    assert response.source == "pqnstack-provider"
    assert response.destination == client.name
    assert response.request == "PONG"


def test_getting_all_instruments(messaging_services): # noqa: ARG001
    client = Client(host="localhost", port=5556, router_name="pqnstack-router")

    response = client.get_available_devices("pqnstack-provider")

    instruments_names = ["dummy1", "dummy2"]

    assert instruments_names == list(response.keys())
    # Get available devices returns the __class__ of the instrument as the value.
    assert isinstance(response["dummy1"], DummyInstrument.__class__)
    assert isinstance(response["dummy2"], DummyInstrument.__class__)


def test_proxy_instrument(messaging_services): # noqa: ARG001
    client = Client(host="localhost", port=5556, router_name="pqnstack-router")

    proxy_instrument = client.get_device("pqnstack-provider", "dummy1")
    assert isinstance(proxy_instrument, ProxyInstrument)

    base_int = 2
    double_int = base_int * 2
    arbitrary_int = 12

    assert proxy_instrument.name == "dummy1"
    assert proxy_instrument.param_int == base_int
    assert proxy_instrument.param_str == "hello"

    assert proxy_instrument.double_int() == double_int
    assert proxy_instrument.param_int == double_int

    proxy_instrument.param_int = arbitrary_int
    assert proxy_instrument.param_int == arbitrary_int

    assert proxy_instrument.uppercase_str() == "HELLO"
    assert proxy_instrument.param_str == "HELLO"

    # Make sure you cannot add attributes to the proxy instrument
    fail_flag = False
    try:
        proxy_instrument.new_attr = 42
    except AttributeError:
        fail_flag = True

    assert fail_flag, "Should not be able to set new attributes on the ProxyInstrument"
