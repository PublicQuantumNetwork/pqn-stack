import argparse
import logging
import tomllib
from pathlib import Path

from pqnstack.base.errors import InvalidNetworkConfigurationError
from pqnstack.network.router import Router

# TODO: check if this way of handling logging from a command line script is ok.
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


def load_and_parse_router_config(config_path: Path | str) -> tuple[str | None, str | None, int | None]:
    path = Path(config_path)
    with path.open("rb") as f:
        config = tomllib.load(f)
    if "router" not in config:
        msg = f"Config file {config_path} does not contain a router section. Add router configuration under '[router]' section."
        raise InvalidNetworkConfigurationError(msg)
    router = config["router"]
    name, host, port = None, None, None
    if "name" in router:
        name = str(router["name"])
    if "host" in router:
        host = str(router["host"])
    if "port" in router:
        port = int(router["port"])
    return name, host, port


def start_router() -> None:
    parser = argparse.ArgumentParser(description="Start a router",
                                     epilog="Starts a PQN router. Can be configured by passing arguments directly into the command line or through a config file. ")

    parser.add_argument("-n", "--name", type=str, required=False, help="Name of the router")
    parser.add_argument("-ho", "--host", type=str, required=False, help="Host address (IP) of the router (default: 'localhost'). Usually the IP address of the machine running the router.")
    parser.add_argument("-p", "--port", type=int, required=False, help="Port of the router (default: 5555)")
    parser.add_argument("-c", "--config", type=str, required=False, help="Path to the config file, will get overridden by command line arguments.")

    args = parser.parse_args()
    kwargs: dict[str, str | int] = {}
    if args.config:
        name, host, port = load_and_parse_router_config(args.config)
        if name:
            kwargs["name"] = name
        if host:
            kwargs["host"] = host
        if port:
            kwargs["port"] = int(port)

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
