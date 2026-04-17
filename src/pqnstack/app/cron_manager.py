"""Manage the PQN daily-report cron job via the system crontab.

Reads and writes the user's crontab using `crontab -l` / `crontab -` so that
no extra dependencies are required. The managed entry is identified by the
inline tag `# PQN_DAILY_REPORT` appended to the cron line.
"""

from __future__ import annotations

import shutil
import subprocess

CRON_TAG = "# PQN_DAILY_REPORT"

_DOW_NAMES = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]


def _read_crontab() -> list[str]:
    result = subprocess.run(["crontab", "-l"], check=False, capture_output=True, text=True)  # noqa: S607
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def _write_crontab(lines: list[str]) -> None:
    content = "\n".join(lines) + "\n"
    subprocess.run(["crontab", "-"], input=content, text=True, check=True)  # noqa: S607


def get_daily_report_job() -> str | None:
    """Return the tagged cron line, or None if not present."""
    for line in _read_crontab():
        if line.endswith(CRON_TAG):
            return line
    return None


def describe_schedule(cron_line: str) -> str:
    """Parse a tagged cron line and return a human-readable schedule string."""
    fields = cron_line.split()
    if len(fields) < 5:  # noqa: PLR2004
        return cron_line

    minute, hour, dom, _month, dow = fields[:5]

    if minute != "*" and hour == "*" and dom == "*" and dow == "*":
        return f"Hourly at :{int(minute):02d}"

    if minute != "*" and hour != "*" and dom == "*" and dow == "*":
        return f"Daily at {int(hour):02d}:{int(minute):02d}"

    if minute != "*" and hour != "*" and dom == "*" and dow != "*":
        day_name = _DOW_NAMES[int(dow)].capitalize()
        return f"Weekly on {day_name} at {int(hour):02d}:{int(minute):02d}"

    if minute != "*" and hour != "*" and dom != "*" and dow == "*":
        return f"Monthly on day {dom} at {int(hour):02d}:{int(minute):02d}"

    return cron_line


def set_daily_report_schedule(minute: int, hour: int | str, dow: str, dom: str) -> None:
    """Replace (or create) the tagged cron entry with the given schedule."""
    pqn = shutil.which("pqn")
    if pqn is None:
        msg = "Could not find 'pqn' executable on PATH"
        raise RuntimeError(msg)

    new_line = f"{minute} {hour} {dom} * {dow} {pqn} daily-report run {CRON_TAG}"
    lines = [line for line in _read_crontab() if not line.endswith(CRON_TAG)]
    lines.append(new_line)
    _write_crontab(lines)


def remove_daily_report_job() -> bool:
    """Remove the tagged cron entry. Returns True if an entry was removed."""
    lines = _read_crontab()
    filtered = [line for line in lines if not line.endswith(CRON_TAG)]
    if len(filtered) == len(lines):
        return False
    _write_crontab(filtered)
    return True
