import argparse
import json
import logging
import tomllib
from pathlib import Path

from pqnstack.base.errors import InvalidNetworkConfigurationError
from pqnstack.network.node import Node
from pqnstack.network.router import Router

# TODO: check if this way of handling logging from a command line script is ok.
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


def _verify_instruments_config(instruments: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    ins = {}
    for i, item in enumerate(instruments):
        if "name" not in item:
            msg = f"Instrument number #{i + 1} configuration is missing the field 'name'"
            raise InvalidNetworkConfigurationError(msg)
        if "import" not in item:
            msg = f"Instrument number #{i + 1} configuration is missing the field 'import'"
            raise InvalidNetworkConfigurationError(msg)
        if "desc" not in item:
            msg = f"Instrument number #{i + 1} configuration is missing the field 'desc'"
            raise InvalidNetworkConfigurationError(msg)
        if "address" not in item:
            msg = f"Instrument number #{i + 1} configuration is missing the field 'address'"
            raise InvalidNetworkConfigurationError(msg)

        name = item.pop("name")
        ins[name] = item

    return ins


def _load_and_parse_node_config(
    config_path: Path | str, kwargs: dict[str, str | int], instruments: dict[str, dict[str, str]]
) -> tuple[dict[str, str | int], dict[str, dict[str, str]]]:
    path = Path(config_path)
    with path.open("rb") as f:
        config = tomllib.load(f)

    if "node" not in config:
        msg = (
            f"Config file {config_path} does not contain a node section. Add node configuration under '[node]' section."
        )
        raise InvalidNetworkConfigurationError(msg)

    node = config["node"]
    if "name" in node:
        kwargs["name"] = str(node["name"])
    if "router_name" in node:
        kwargs["router_name"] = str(node["router_name"])
    if "host" in node:
        kwargs["host"] = str(node["host"])
    if "port" in node:
        kwargs["port"] = int(node["port"])

    if "instruments" in node:
        instruments = _verify_instruments_config(node["instruments"])

    return kwargs, instruments


def start_node() -> None:
    parser = argparse.ArgumentParser(
        description="Start a node",
        epilog="Starts a PQN Node. Can be configured by passing arguments directly into the command line but it is recommended to use a config file if instruments will added.",
    )
    parser.add_argument("-n", "--name", type=str, required=False, help="Name of the node")
    parser.add_argument(
        "-rn",
        "--router_name",
        type=str,
        required=False,
        help="Name of the router this node will talk to (default: 'router1').",
    )
    parser.add_argument(
        "-ho",
        "--host",
        type=str,
        required=False,
        help="Host address (IP) of the node (default: 'localhost'). Usually the IP address of the Router this node will talk to.",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        required=False,
        help="Port of the node (default: 5555). Has to be the same port as the Router.",
    )
    parser.add_argument(
        "-i",
        "--instruments",
        type=str,
        required=False,
        help='JSON formatted string with necessary arguments to instantiate instruments. Example: \'{"dummy1": {"import": "pqnstack.pqn.drivers.dummies.DummyInstrument", "desc": "Dummy Instrument 1", "address": "123456"}}\'',
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=False,
        help="Path to the config file, will get overridden by command line arguments.",
    )

    args = parser.parse_args()

    kwargs: dict[str, str | int] = {}
    instruments: dict[str, dict[str, str]] = {}

    if args.config:
        kwargs, instruments = _load_and_parse_node_config(args.config, kwargs, instruments)

    if args.name:
        kwargs["name"] = args.name
    if args.router_name:
        kwargs["router_name"] = args.router_name
    if args.host:
        kwargs["host"] = args.host
    if args.port:
        kwargs["port"] = args.port
    if args.instruments:
        # We don't want to override instruments, instead combining them with the ones from config file is cleaner behaviour.
        instruments = {**instruments, **json.loads(args.instruments)}

    if "name" not in kwargs:
        msg = "Node name is required"
        raise InvalidNetworkConfigurationError(msg)

    node = Node(**kwargs, **instruments)  # type: ignore[arg-type]
    node.start()


def _load_and_parse_router_config(config_path: Path | str, kwargs: dict[str, str | int]) -> dict[str, str | int]:
    path = Path(config_path)
    with path.open("rb") as f:
        config = tomllib.load(f)
    if "router" not in config:
        msg = f"Config file {config_path} does not contain a router section. Add router configuration under '[router]' section."
        raise InvalidNetworkConfigurationError(msg)
    router = config["router"]
    if "name" in router:
        kwargs["name"] = str(router["name"])
    if "host" in router:
        kwargs["host"] = str(router["host"])
    if "port" in router:
        kwargs["port"] = int(router["port"])
    return kwargs


def start_router() -> None:
    parser = argparse.ArgumentParser(
        description="Start a router",
        epilog="Starts a PQN Router. Can be configured by passing arguments directly into the command line or through a config file. ",
    )

    parser.add_argument("-n", "--name", type=str, required=False, help="Name of the router")
    parser.add_argument(
        "-ho",
        "--host",
        type=str,
        required=False,
        help="Host address (IP) of the router (default: 'localhost'). Usually the IP address of the machine running the router.",
    )
    parser.add_argument("-p", "--port", type=int, required=False, help="Port of the router (default: 5555)")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=False,
        help="Path to the config file, will get overridden by command line arguments.",
    )

    args = parser.parse_args()
    kwargs: dict[str, str | int] = {}
    if args.config:
        kwargs = _load_and_parse_router_config(args.config, kwargs)

    if args.name:
        kwargs["name"] = args.name
    if args.host:
        kwargs["host"] = args.host
    if args.port:
        kwargs["port"] = int(args.port)

    if "name" not in kwargs:
        msg = "Router name is required"
        raise InvalidNetworkConfigurationError(msg)

    # mypy doesn't like **kwargs https://github.com/python/mypy/issues/5382#issuecomment-417433738
    router = Router(**kwargs)  # type: ignore[arg-type]
    router.start()
