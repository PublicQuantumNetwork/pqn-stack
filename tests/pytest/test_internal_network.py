import logging
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from pqnstack.network.client import Client
from pqnstack.network.client import ProxyInstrument
from pqnstack.network.packet import Packet
from pqnstack.network.packet import PacketIntent
from pqnstack.pqn.drivers.dummies import DummyInstrument

logger = logging.getLogger(__name__)


@pytest.fixture
def messaging_services():
    """Start router and provider services for testing."""
    logger.debug("Starting messaging services...")
    # Get the path to the config file relative to this test file, not current working directory
    test_dir = Path(__file__).parent
    config_path = test_dir / "test_network_config.toml"
    uv_path = shutil.which("uv")
    if not uv_path:
        msg = "Could not find 'uv' executable in PATH"
        raise RuntimeError(msg)

    logger.debug("Using uv path: %s, starting router and provider with config: %s", uv_path, config_path)

    # Start router process
    router_process = subprocess.Popen(  # Noqa: S603 # Subprocess is used for testing purposes, not in production code.
        [uv_path, "run", "pqn", "start-router", "--config", str(config_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Give router time to start up
    time.sleep(1)

    # Start provider process
    provider_process = subprocess.Popen(  # Noqa: S603 # Subprocess is used for testing purposes, not in production code.
        [uv_path, "run", "pqn", "start-provider", "--config", str(config_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Give provider time to start up and connect to router
    time.sleep(1)

    # Check if provider started successfully
    if provider_process.poll() is not None:
        stdout, stderr = provider_process.communicate()
        msg = f"Provider failed to start. Exit code: {provider_process.returncode}\nStdout: {stdout.decode()}\nStderr: {stderr.decode()}"
        raise RuntimeError(msg)

    logger.debug("Services should be ready for testing")

    try:
        yield
    finally:
        logger.debug("Cleaning up messaging services...")

        # Terminate provider first (depends on router)
        if provider_process.poll() is None:
            provider_process.terminate()
            try:
                provider_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                provider_process.kill()
                provider_process.wait()

        # Then terminate router
        if router_process.poll() is None:
            router_process.terminate()
            try:
                router_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                router_process.kill()
                router_process.wait()

        logger.debug("All services cleaned up")


def test_client_ping(messaging_services):  # noqa: ARG001
    client = Client(host="localhost", port=5556, router_name="pqnstack-router", timeout=1000)
    response = client.ping("pqnstack-provider")

    assert isinstance(response, Packet)
    assert response.intent == PacketIntent.PING
    assert response.source == "pqnstack-provider"
    assert response.destination == client.name
    assert response.request == "PONG"


def test_getting_all_instruments(messaging_services):  # noqa: ARG001
    client = Client(host="localhost", port=5556, router_name="pqnstack-router", timeout=1000)

    response = client.get_available_devices("pqnstack-provider")

    instruments_names = ["dummy1", "dummy2"]

    assert instruments_names == list(response.keys())
    # Get available devices returns the __class__ of the instrument as the value.
    assert isinstance(response["dummy1"], DummyInstrument.__class__)
    assert isinstance(response["dummy2"], DummyInstrument.__class__)


def test_proxy_instrument(messaging_services):  # noqa: ARG001
    client = Client(host="localhost", port=5556, router_name="pqnstack-router", timeout=1000)

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
