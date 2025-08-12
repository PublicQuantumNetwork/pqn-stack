import json
import logging
import tomllib
from pathlib import Path
from typing import Annotated

import typer

from pqnstack.base.errors import InvalidNetworkConfigurationError
from pqnstack.network.instrument_provider import InstrumentProvider
from pqnstack.network.router import Router

# TODO: check if this way of handling logging from a command line script is ok.
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

app = typer.Typer(no_args_is_help=True, help="CLI for PQN-Stack.")


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


def _load_and_parse_provider_config(
    config_path: Path | str, kwargs: dict[str, str | int], instruments: dict[str, dict[str, str]]
) -> tuple[dict[str, str | int], dict[str, dict[str, str]]]:
    path = Path(config_path)
    with path.open("rb") as f:
        config = tomllib.load(f)

    if "provider" not in config:
        msg = f"Config file {config_path} does not contain a provider section. Add provider configuration under '[provider]' section."
        raise InvalidNetworkConfigurationError(msg)

    provider = config["provider"]
    if "name" in provider:
        kwargs["name"] = str(provider["name"])
    if "router_name" in provider:
        kwargs["router_name"] = str(provider["router_name"])
    if "host" in provider:
        kwargs["host"] = str(provider["host"])
    if "port" in provider:
        kwargs["port"] = int(provider["port"])
    if "beat_period" in provider:
        kwargs["beat_period"] = int(provider["beat_period"])

    if "instruments" in provider:
        instruments = _verify_instruments_config(provider["instruments"])

    return kwargs, instruments


@app.command()
def start_provider(  # noqa: PLR0913
    name: Annotated[str | None, typer.Option(help="Name of the InstrumentProvider.")] = None,
    router_name: Annotated[
        str | None, typer.Option(help="Name of the router this provider will talk to (default: 'router1').")
    ] = None,
    host: Annotated[
        str | None,
        typer.Option(
            help="Host address (IP) of the provider (default: 'localhost'). Usually the IP address of the Router this provider will talk to."
        ),
    ] = None,
    port: Annotated[
        int | None, typer.Option(help="Port of the provider (default: 5555). Has to be the same port as the Router.")
    ] = None,
    beat_period: Annotated[int | None, typer.Option(help="Heartbeat period in milliseconds (default: 1000)")] = None,
    instruments: Annotated[
        str | None,
        typer.Option(
            help='JSON formatted string with necessary arguments to instantiate instruments. Example: \'{"dummy1": {"import": "pqnstack.pqn.drivers.dummies.DummyInstrument", "desc": "Dummy Instrument 1", "address": "123456"}}\''
        ),
    ] = None,
    config: Annotated[
        str | None, typer.Option(help="Path to the config file, will get overridden by command line arguments.")
    ] = None,
) -> None:
    """
    Start a PQN InstrumentProvider.

    Can be configured by passing arguments directly into the command line but it is recommended to use a config file if instruments will be added.
    """
    kwargs: dict[str, str | int] = {}
    ins: dict[str, dict[str, str]] = {}

    if config:
        kwargs, ins = _load_and_parse_provider_config(config, kwargs, ins)

    if name:
        kwargs["name"] = name
    if router_name:
        kwargs["router_name"] = router_name
    if host:
        kwargs["host"] = host
    if port:
        kwargs["port"] = port
    if beat_period:
        kwargs["beat_period"] = beat_period
    if instruments:
        # We don't want to override instruments, instead combining them with the ones from config file is cleaner behaviour.
        ins = {**ins, **json.loads(instruments)}

    if "name" not in kwargs:
        msg = "InstrumentProvider name is required"
        raise InvalidNetworkConfigurationError(msg)

    provider = InstrumentProvider(**kwargs, **ins)  # type: ignore[arg-type]
    provider.start()


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


@app.command()
def start_router(
    name: Annotated[str | None, typer.Option(help="Name of the router (default 'router1')")] = None,
    host: Annotated[
        str | None,
        typer.Option(
            help="Host address (IP) of the router (default: 'localhost'). Usually the IP address of the machine running the router."
        ),
    ] = None,
    port: Annotated[str | None, typer.Option(help="Port of the router (default: 5555)")] = None,
    config: Annotated[
        str | None, typer.Option(help="Path to the config file, will get overridden by command line arguments.")
    ] = None,
) -> None:
    """
    Start a PQN Router.

    Can be configured by passing arguments directly into the command line or through a config file.
    """
    kwargs: dict[str, str | int] = {}
    if config:
        kwargs = _load_and_parse_router_config(config, kwargs)

    if name:
        kwargs["name"] = name
    if host:
        kwargs["host"] = host
    if port:
        kwargs["port"] = int(port)

    if "name" not in kwargs:
        msg = "Router name is required"
        raise InvalidNetworkConfigurationError(msg)

    # mypy doesn't like **kwargs https://github.com/python/mypy/issues/5382#issuecomment-417433738
    router = Router(**kwargs)  # type: ignore[arg-type]
    router.start()


if __name__ == "__main__":
    app()
