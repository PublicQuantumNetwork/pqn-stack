import json
import logging
import tomllib
from pathlib import Path
from typing import Annotated

import tomli_w
import typer

from pqnstack.app.core.config import get_settings
from pqnstack.app.cron_manager import describe_schedule
from pqnstack.app.cron_manager import get_daily_report_job
from pqnstack.app.cron_manager import remove_daily_report_job
from pqnstack.app.cron_manager import set_daily_report_schedule
from pqnstack.app.daily_report import run_daily_report
from pqnstack.base.errors import InvalidNetworkConfigurationError
from pqnstack.network.instrument_provider import InstrumentProvider
from pqnstack.network.router import Router

# TODO: check if this way of handling logging from a command line script is ok.
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

app = typer.Typer(no_args_is_help=True, help="CLI for PQN-Stack.")

daily_report_app = typer.Typer(no_args_is_help=True, help="Run and manage the daily health + Slack report.")
app.add_typer(daily_report_app, name="daily-report")


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
        if "hw_address" not in item:
            msg = f"Instrument number #{i + 1} configuration is missing the field 'hw_address'"
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
            help="Host hw_address (IP) of the provider (default: 'localhost'). Usually the IP hw_address of the Router this provider will talk to."
        ),
    ] = None,
    port: Annotated[
        int | None, typer.Option(help="Port of the provider (default: 5555). Has to be the same port as the Router.")
    ] = None,
    beat_period: Annotated[int | None, typer.Option(help="Heartbeat period in milliseconds (default: 1000)")] = None,
    instruments: Annotated[
        str | None,
        typer.Option(
            help='JSON formatted string with necessary arguments to instantiate instruments. Example: \'{"dummy1": {"import": "pqnstack.pqn.drivers.dummies.DummyInstrument", "desc": "Dummy Instrument 1", "hw_address": "123456"}}\''
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
            help="Host hw_address (IP) of the router (default: 'localhost'). Usually the IP hw_address of the machine running the router."
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


@app.command()
def toggle_game(
    games: Annotated[list[str], typer.Argument(help="Games to toggle: chsh, qf, ssm")],
    enable: Annotated[bool, typer.Option("--enable/--disable", help="Enable or disable the games")] = True,  # noqa: FBT002
    config: Annotated[str, typer.Option(help="Path to config.toml")] = "./config.toml",
) -> None:
    """
    Enable or disable one or more games in config.toml.

    Changes take effect on the next server restart. Games: chsh (Verify Quantum Link), qf (Quantum Fortune), ssm (Share a Secret Message).
    """
    valid_games = {"chsh", "qf", "ssm"}
    invalid = [g for g in games if g not in valid_games]
    if invalid:
        msg = f"Game(s) must be one of: chsh, qf, ssm. Invalid: {invalid}"
        raise InvalidNetworkConfigurationError(msg)

    path = Path(config)
    with path.open("rb") as f:
        cfg = tomllib.load(f)

    cfg.setdefault("games_availability", {})
    for game in games:
        cfg["games_availability"][game] = enable

    with path.open("wb") as f:
        tomli_w.dump(cfg, f)

    status = "enabled" if enable else "disabled"
    logger.info("Games %s %s in %s. Restart the server for changes to take effect.", games, status, path)


@daily_report_app.command("run")
def daily_report_run() -> None:
    """
    Run the daily health + games report and post the result to Slack.

    Reads the [daily_report] section from config.toml, probes hardware via the
    running API (`/health`), exercises each enabled game (except SSM), and posts a
    consolidated Slack digest. Exits non-zero if anything failed.
    """
    report_config = get_settings().daily_report
    if report_config is None:
        logger.error("[daily_report] section missing from config.toml")
        raise typer.Exit(code=1)

    raise typer.Exit(code=run_daily_report(report_config))


@daily_report_app.command("status")
def daily_report_status() -> None:
    """Show whether the daily report cron job is active and its schedule."""
    job = get_daily_report_job()
    if job is None:
        typer.echo("Daily report is not scheduled.")
    else:
        typer.echo(f"Daily report is active. Schedule: {describe_schedule(job)}")


_DOW_MAP = {
    "monday": "1",
    "tuesday": "2",
    "wednesday": "3",
    "thursday": "4",
    "friday": "5",
    "saturday": "6",
    "sunday": "0",
}


def _prompt_hhmm() -> tuple[int, int]:
    raw_time = typer.prompt("Time (HH:MM, 24-hour)")
    try:
        h_str, m_str = raw_time.strip().split(":")
        hour, minute = int(h_str), int(m_str)
    except ValueError:
        typer.echo("Invalid time format. Use HH:MM (e.g. 09:00).", err=True)
        raise typer.Exit(code=1)  # noqa: B904
    if not (0 <= hour <= 23 and 0 <= minute <= 59):  # noqa: PLR2004
        typer.echo("Hour must be 0-23 and minute 0-59.", err=True)
        raise typer.Exit(code=1)
    return hour, minute


def _prompt_dow() -> str:
    raw_day = typer.prompt("Day of week (monday-sunday)").strip().lower()
    if raw_day not in _DOW_MAP:
        typer.echo(f"Invalid day '{raw_day}'.", err=True)
        raise typer.Exit(code=1)
    return _DOW_MAP[raw_day]


def _prompt_dom() -> str:
    raw_dom = typer.prompt("Day of month (1-28)")
    dom_int = int(raw_dom)
    if not 1 <= dom_int <= 28:  # noqa: PLR2004
        typer.echo("Day of month must be between 1 and 28.", err=True)
        raise typer.Exit(code=1)
    return str(dom_int)


@daily_report_app.command("schedule")
def daily_report_schedule() -> None:
    """Interactively schedule the daily report cron job."""
    frequency = typer.prompt("Frequency (hourly/daily/weekly/monthly)").strip().lower()
    valid = {"hourly", "daily", "weekly", "monthly"}
    if frequency not in valid:
        typer.echo(f"Invalid frequency '{frequency}'. Choose from: {', '.join(sorted(valid))}", err=True)
        raise typer.Exit(code=1)

    minute: int
    hour: int | str = "*"
    dow = "*"
    dom = "*"

    if frequency == "hourly":
        raw_minute = typer.prompt("Minute past the hour (0-59)")
        minute = int(raw_minute)
        if not 0 <= minute <= 59:  # noqa: PLR2004
            typer.echo("Minute must be between 0 and 59.", err=True)
            raise typer.Exit(code=1)
    else:
        hour, minute = _prompt_hhmm()
        if frequency == "weekly":
            dow = _prompt_dow()
        elif frequency == "monthly":
            dom = _prompt_dom()

    try:
        set_daily_report_schedule(minute=minute, hour=hour, dow=dow, dom=dom)
    except RuntimeError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)  # noqa: B904

    job = get_daily_report_job()
    description = describe_schedule(job) if job else "unknown"
    typer.echo(f"Daily report scheduled. Schedule: {description}")


@daily_report_app.command("unschedule")
def daily_report_unschedule() -> None:
    """Remove the daily report cron job."""
    removed = remove_daily_report_job()
    if removed:
        typer.echo("Daily report unscheduled.")
    else:
        typer.echo("Daily report was not scheduled.")


if __name__ == "__main__":
    app()
