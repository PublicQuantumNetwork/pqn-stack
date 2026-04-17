"""Daily health + games report posted to Slack.

Run via `pqn daily-report` (see pqnstack.cli). Loads `DailyReportConfig`, probes
hardware via `/health`, exercises each enabled game except SSM, and posts a
single consolidated Slack digest.
"""

from __future__ import annotations

import logging
import os
import signal
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

import httpx

from pqnstack.app.api.routes.chsh import ChshResult
from pqnstack.app.api.routes.health import ComponentStatus
from pqnstack.app.api.routes.health import HealthStatus

if TYPE_CHECKING:
    from types import FrameType

    from pqnstack.app.core.config import DailyReportConfig

logger = logging.getLogger(__name__)

_SSM_SKIP_REASON = "SSM skipped in daily report (requires coordination dance; run manually)."
_BELL_CLASSICAL_LIMIT = 2.0

_watchdog_state: dict[str, Any] = {}


@dataclass
class GameResult:
    name: str
    title: str
    status: str  # "ok" | "failed" | "skipped"
    data: dict[str, Any] | list[Any] | None = None
    error: str | None = None
    elapsed_s: float = 0.0
    emoji: str = ""


@dataclass
class ReportResult:
    hardware: HealthStatus | None = None
    hardware_error: str | None = None
    games: list[GameResult] = field(default_factory=list)
    skipped_notes: list[str] = field(default_factory=list)

    @property
    def overall_ok(self) -> bool:
        hw_ok = self.hardware_error is None and self.hardware is not None and self.hardware.all_ok
        games_ok = all(g.status == "ok" for g in self.games)
        return hw_ok and games_ok


def _watchdog_handler(_signum: int, _frame: FrameType | None) -> None:
    """SIGALRM handler: post a Slack alert and force-kill the process.

    Uses os._exit instead of sys.exit so that atexit handlers, finally blocks,
    and Python's own shutdown sequence can't delay or swallow the kill — a hung
    process is precisely what we're trying to escape. Reads config from the
    module-level dict because signal handlers can't accept arbitrary arguments.
    """
    webhook = _watchdog_state.get("webhook_url")
    timeout_s = _watchdog_state.get("timeout_s")
    message = (
        f":x: *Daily report watchdog fired* — exceeded overall timeout of `{timeout_s}s`. "
        "Process was killed; investigate the API / hardware."
    )
    if webhook:
        try:
            _post_plain_slack(webhook, message)
        except Exception:
            logger.exception("Failed to post watchdog notification")
    logger.error("Daily report watchdog fired after %ss; exiting", timeout_s)
    os._exit(1)


def _arm_watchdog(config: DailyReportConfig) -> None:
    """Install the SIGALRM watchdog for the entire run.

    SIGALRM is the right tool here: it fires even if the process is blocked in
    a syscall (e.g. waiting on a socket), where threading-based timeouts can't
    reach. Stash config in module state so the signal handler can read it.
    """
    _watchdog_state["webhook_url"] = config.slack_webhook_url
    _watchdog_state["timeout_s"] = config.overall_timeout_s
    signal.signal(signal.SIGALRM, _watchdog_handler)
    signal.alarm(config.overall_timeout_s)


def _disarm_watchdog() -> None:
    """Cancel the watchdog once the run completes normally."""
    signal.alarm(0)


def _check_api(config: DailyReportConfig) -> bool:
    """Return True if the API is reachable, False otherwise.

    Runs before any other probe so that a single "API is down" message replaces
    the cascade of connection-refused errors that would otherwise fill the digest.
    """
    try:
        with httpx.Client(timeout=5.0) as client:
            client.get(f"{config.api_url}/")
    except httpx.ConnectError:
        return False
    return True


def _fetch_hardware(config: DailyReportConfig) -> tuple[HealthStatus | None, str | None]:
    """Probe the node's hardware health and return (result, error).

    Returns a tuple rather than raising so that a failed hardware probe doesn't
    abort the whole run — we still want to attempt the games and post a digest
    that tells operators what's broken.
    """
    url = f"{config.api_url}/health/"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params={"follower_node_address": config.follower_node_address})
        response.raise_for_status()
        return HealthStatus.model_validate(response.json()), None
    except httpx.HTTPError as e:
        logger.exception("Hardware health probe failed")
        return None, f"{type(e).__name__}: {e}"


def _fetch_availability(config: DailyReportConfig) -> dict[str, bool]:
    """Return which games are enabled according to the running node.

    Defaults to all-enabled on failure so a transient availability fetch error
    doesn't silently skip every game — better to attempt and fail visibly than
    to skip silently and miss the problem entirely.
    """
    url = f"{config.api_url}/games/availability"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
        response.raise_for_status()
        payload: dict[str, bool] = response.json()
    except httpx.HTTPError:
        logger.exception("Failed to fetch games availability; assuming all enabled")
        return {"chsh": True, "qf": True, "ssm": True}
    return payload


def _run_chsh(config: DailyReportConfig) -> GameResult:
    """Run one CHSH measurement and return a structured result.

    Catches all exceptions (not just httpx) because pydantic validation errors
    on an unexpected server response shape are equally fatal to the game result
    and must be captured here rather than crashing the whole report.
    """
    started = datetime.now(UTC)
    try:
        with httpx.Client(timeout=float(config.per_game_timeout_s)) as client:
            response = client.post(
                f"{config.api_url}/chsh/",
                params={
                    "follower_node_address": config.follower_node_address,
                    "timetagger_address": config.timetagger_address,
                },
                json=config.basis,
            )
        response.raise_for_status()
        parsed = ChshResult.model_validate(response.json())
    except httpx.HTTPError as e:
        return GameResult(
            name="chsh",
            title="CHSH — Verify Quantum Link",
            status="failed",
            error=f"{type(e).__name__}: {e}",
            elapsed_s=(datetime.now(UTC) - started).total_seconds(),
        )
    except Exception as e:  # noqa: BLE001 - surface any parsing / validation error, don't crash the report
        return GameResult(
            name="chsh",
            title="CHSH — Verify Quantum Link",
            status="failed",
            error=f"{type(e).__name__}: {e}",
            elapsed_s=(datetime.now(UTC) - started).total_seconds(),
        )

    emoji = ":sparkles:" if parsed.chsh_value > _BELL_CLASSICAL_LIMIT else ":thinking_face:"
    return GameResult(
        name="chsh",
        title="CHSH — Verify Quantum Link",
        status="ok",
        data=parsed.model_dump(),
        elapsed_s=(datetime.now(UTC) - started).total_seconds(),
        emoji=emoji,
    )


def _run_qf(config: DailyReportConfig) -> GameResult:
    """Run one Quantum Fortune measurement and return a structured result.

    Omits channels and integration_time_s so the node falls back to its own
    rng_settings — the daily report shouldn't override per-node calibration.
    """
    started = datetime.now(UTC)
    # channels and integration_time_s are omitted — the node uses its configured rng_settings defaults.
    params: dict[str, str] = {"timetagger_address": config.timetagger_address}
    try:
        with httpx.Client(timeout=float(config.per_game_timeout_s)) as client:
            response = client.get(f"{config.api_url}/rng/fortune", params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as e:
        return GameResult(
            name="qf",
            title="Quantum Fortune",
            status="failed",
            error=f"{type(e).__name__}: {e}",
            elapsed_s=(datetime.now(UTC) - started).total_seconds(),
        )

    return GameResult(
        name="qf",
        title="Quantum Fortune",
        status="ok",
        data={"fortune_per_channel": payload},
        elapsed_s=(datetime.now(UTC) - started).total_seconds(),
        emoji=":game_die:",
    )


def _format_value(value: Any) -> str:
    """Render a scalar or numeric list as a human-readable string for Slack."""
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, list):
        if all(isinstance(x, (int, float)) for x in value):
            return "[" + ", ".join(f"{x:.4f}" if isinstance(x, float) else str(x) for x in value) + "]"
        return str(value)
    return str(value)


def _fields_from_dict(data: dict[str, Any]) -> list[dict[str, str]]:
    """Convert an arbitrary result dict to Slack mrkdwn field blocks.

    Operates on the raw dict rather than a typed model so CHSH and QF results
    share one formatting path without coupling this layer to specific schemas.
    """
    fields: list[dict[str, str]] = []
    for key, value in data.items():
        label = key.replace("_", " ").title()
        fields.append({"type": "mrkdwn", "text": f"*{label}:*\n`{_format_value(value)}`"})
    return fields


def _sections_from_fields(fields: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Slack section blocks cap fields at 10 per block; chunk accordingly."""
    chunk = 10
    return [{"type": "section", "fields": fields[i : i + chunk]} for i in range(0, len(fields), chunk)]


def _component_line(label: str, status: ComponentStatus) -> str:
    """Format one hardware component as a single Slack line.

    Accepts the base ComponentStatus type so it works for both plain components
    (router, rotary encoder) and DeviceStatus without needing an overload.
    """
    emoji = ":white_check_mark:" if status.reachable else ":x:"
    if status.reachable and status.latency_ms is not None:
        suffix = f" _({status.latency_ms:.0f}ms)_"
    elif status.error:
        suffix = f" — `{status.error}`"
    else:
        suffix = ""
    return f"{emoji} {label}{suffix}"


def _hardware_text(hardware: HealthStatus | None, error: str | None) -> str:
    """Render the hardware section of the digest as a mrkdwn string.

    Takes the typed HealthStatus model (not a raw dict) so we can iterate
    devices with their purpose labels and show the rotary encoder only when
    it was actually probed (i.e. not virtual).
    """
    if error is not None:
        return f":x: *Hardware probe failed*\n```{error}```"
    if hardware is None:
        return ":x: *Hardware probe returned no data.*"

    lines = ["*Hardware Health*"]
    lines.append(_component_line("Router", hardware.router))
    lines.extend(_component_line(f"`{d.provider}/{d.name}` _({d.purpose})_", d) for d in hardware.devices)
    if hardware.rotary_encoder is not None:
        lines.append(_component_line("Rotary encoder", hardware.rotary_encoder))
    else:
        lines.append(":grey_question: Rotary encoder — _virtual (skipped)_")
    if hardware.follower_node is not None:
        lines.append(_component_line("Follower node", hardware.follower_node))

    return "\n".join(lines)


def _game_blocks(game: GameResult) -> list[dict[str, Any]]:
    """Build Block Kit blocks for one game result.

    Dispatches on status so skipped, failed, and successful games each get an
    appropriate layout — skipped and failed collapse to a single block, while
    a success expands to include the full data fields.
    """
    header = f"{game.emoji} *{game.title}*" if game.emoji else f"*{game.title}*"
    if game.status == "skipped":
        return [{"type": "section", "text": {"type": "mrkdwn", "text": f":fast_forward: {header}\n_{game.error}_"}}]

    if game.status == "failed":
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":x: {header}\n```{game.error}```\n_Elapsed: {game.elapsed_s:.1f}s_",
                },
            }
        ]

    blocks: list[dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f":white_check_mark: {header}"}},
    ]
    if isinstance(game.data, dict):
        blocks.extend(_sections_from_fields(_fields_from_dict(game.data)))
    elif isinstance(game.data, list):
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"`{_format_value(game.data)}`"},
            }
        )
    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f":stopwatch: {game.elapsed_s:.1f}s"}],
        }
    )
    return blocks


def _build_digest(config: DailyReportConfig, result: ReportResult) -> dict[str, Any]:
    """Assemble the full Block Kit digest payload.

    The header emoji distinguishes hardware failures from game failures so
    operators can tell at a glance whether they need to check the hardware rack
    or look at a software/timing issue.
    """
    if result.overall_ok:
        header_emoji = ":white_check_mark:"
        header_text = "Daily Report — all systems nominal"
    elif result.hardware_error is not None or result.hardware is None or not result.hardware.all_ok:
        header_emoji = ":warning:"
        header_text = "Daily Report — hardware issues detected"
    else:
        header_emoji = ":warning:"
        header_text = "Daily Report — game failures detected"

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{header_emoji} {header_text}", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": _hardware_text(result.hardware, result.hardware_error)},
        },
    ]
    for game in result.games:
        blocks.append({"type": "divider"})
        blocks.extend(_game_blocks(game))

    if result.skipped_notes:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": "\n".join(result.skipped_notes)}],
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f":clock1: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}  "
                        f"| Follower: `{config.follower_node_address}`  "
                        f"| TimeTagger: `{config.timetagger_address}`"
                    ),
                }
            ],
        }
    )

    return {"blocks": blocks}


def _post_plain_slack(webhook_url: str, text: str) -> None:
    """Post a bare text message to Slack — used as a last-resort fallback."""
    with httpx.Client(timeout=10.0) as client:
        client.post(webhook_url, json={"text": text})


def _post_slack(webhook_url: str, message: dict[str, Any]) -> bool:
    """Post a Block Kit message to Slack and return whether it was accepted.

    Falls back to a plain-text message if Slack rejects the Block Kit payload
    so operators still get a notification even when the formatting is wrong,
    rather than silently receiving nothing.
    """
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(webhook_url, json=message)
    except httpx.HTTPError:
        logger.exception("Slack post failed")
        return False
    if response.text == "ok":
        return True
    logger.error("Slack rejected the digest: %s", response.text)
    # Fallback: best-effort plain-text notice so the operator sees something.
    try:
        _post_plain_slack(
            webhook_url,
            f":warning: Daily report could not post Block Kit digest. Slack said: `{response.text[:200]}`",
        )
    except httpx.HTTPError:
        logger.exception("Fallback plain Slack post also failed")
    return False


def run_daily_report(config: DailyReportConfig) -> int:
    """Run the daily report end-to-end. Returns a process exit code."""
    _arm_watchdog(config)
    try:
        if not _check_api(config):
            logger.error("API at %s is unreachable", config.api_url)
            _post_plain_slack(
                config.slack_webhook_url,
                f":x: *Daily Report — API is down*\nCould not reach `{config.api_url}`. Start the server and re-run.",
            )
            return 1

        result = ReportResult()

        logger.info("Probing hardware via %s/health/", config.api_url)
        hardware, hardware_error = _fetch_hardware(config)
        result.hardware = hardware
        result.hardware_error = hardware_error

        availability = _fetch_availability(config)

        if availability.get("chsh"):
            logger.info("Running CHSH")
            result.games.append(_run_chsh(config))
        else:
            result.skipped_notes.append(":fast_forward: CHSH disabled in `games_availability`.")

        if availability.get("qf"):
            logger.info("Running Quantum Fortune")
            result.games.append(_run_qf(config))
        else:
            result.skipped_notes.append(":fast_forward: Quantum Fortune disabled in `games_availability`.")

        if availability.get("ssm"):
            result.skipped_notes.append(f":fast_forward: {_SSM_SKIP_REASON}")

        digest = _build_digest(config, result)
        posted = _post_slack(config.slack_webhook_url, digest)

        if not posted:
            return 1
        return 0 if result.overall_ok else 1
    finally:
        _disarm_watchdog()
