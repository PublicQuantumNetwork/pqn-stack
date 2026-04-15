#!/usr/bin/env python3
"""
CHSH Daily Report Script.

Runs CHSH measurement and posts results to Slack.

Reads all configuration from config.toml (including Slack webhook URL).

Usage:
    uv run scripts/chsh_daily_report.py
"""

import logging
import sys
import tomllib
from datetime import UTC
from datetime import datetime
from pathlib import Path

import httpx
from pydantic import ValidationError

from pqnstack.app.api.routes.chsh import ChshResult
from pqnstack.app.core.config import DailyReportConfig

logger = logging.getLogger(__name__)


def load_config() -> DailyReportConfig:
    """Load and validate the [daily_report] section from config.toml."""
    config_path = Path(__file__).parent.parent / "config.toml"

    if not config_path.exists():
        logger.error("config.toml not found at %s", config_path)
        logger.error("Please create config.toml from configs/config_app_example.toml")
        sys.exit(1)

    with config_path.open("rb") as f:
        raw = tomllib.load(f)

    daily_report_data = raw.get("daily_report")
    if not daily_report_data:
        logger.error("[daily_report] section not found in config.toml")
        logger.error("Please add it following the example in configs/config_app_example.toml")
        sys.exit(1)

    try:
        return DailyReportConfig.model_validate(daily_report_data)
    except ValidationError:
        logger.exception("Invalid [daily_report] configuration")
        sys.exit(1)


def run_chsh_measurement(config: DailyReportConfig) -> ChshResult:
    """Run CHSH measurement via API."""
    logger.info("Starting CHSH measurement at %s", datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("Basis: %s", config.basis)
    logger.info("Follower: %s", config.follower_node_address)
    logger.info("TimeTagger: %s", config.timetagger_address)

    try:
        with httpx.Client(timeout=600.0) as client:
            response = client.post(
                f"{config.api_url}/chsh/",
                params={
                    "follower_node_address": config.follower_node_address,
                    "timetagger_address": config.timetagger_address,
                },
                json=config.basis,
            )
            response.raise_for_status()
            return ChshResult.model_validate(response.json())

    except httpx.HTTPError:
        logger.exception("Failed to contact CHSH API")
        sys.exit(1)


def post_to_slack(webhook_url: str, chsh_data: ChshResult, config: DailyReportConfig) -> None:
    """Post CHSH results to Slack."""
    # Determine emoji based on Bell inequality violation (CHSH > classical limit)
    bell_inequality_classical_limit = 2
    emoji = ":sparkles:" if chsh_data.chsh_value > bell_inequality_classical_limit else ":thinking_face:"

    # Build fields dynamically from all returned data
    fields = []
    for key, value in chsh_data.model_dump().items():
        field_name = key.replace("_", " ").title()

        if isinstance(value, float):
            formatted_value = f"{value:.4f}"
        elif isinstance(value, list):
            if all(isinstance(x, (int, float)) for x in value):
                formatted_value = "[" + ", ".join(f"{x:.4f}" if isinstance(x, float) else str(x) for x in value) + "]"
            else:
                formatted_value = str(value)
        else:
            formatted_value = str(value)

        fields.append({"type": "mrkdwn", "text": f"*{field_name}:*\n`{formatted_value}`"})

    # Create sections with 2 fields each (Slack limit)
    sections = []
    for i in range(0, len(fields), 2):
        section_fields = fields[i : i + 2]
        sections.append({"type": "section", "fields": section_fields})

    # Add configuration info section
    sections.append(
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Basis:*\n`{config.basis}`"},
                {"type": "mrkdwn", "text": f"*Timestamp:*\n{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}"},
            ],
        }
    )

    # Format Slack message using Block Kit
    slack_message = {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} CHSH Daily Measurement Report", "emoji": True},
            },
            *sections,
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Follower: `{config.follower_node_address}` | TimeTagger: `{config.timetagger_address}`",
                    }
                ],
            },
        ]
    }

    logger.info("Posting to Slack...")

    try:
        with httpx.Client() as client:
            response = client.post(webhook_url, json=slack_message)

            if response.text == "ok":
                logger.info("Successfully posted to Slack")
            else:
                logger.error("Failed to post to Slack: %s", response.text)
                sys.exit(1)

    except httpx.HTTPError:
        logger.exception("Failed to post to Slack")
        sys.exit(1)


def post_error_to_slack(webhook_url: str, error_message: str) -> None:
    """Post error message to Slack."""
    slack_message = {
        "text": f":x: CHSH Daily Report Failed\n*Error:* {error_message}\n*Time:* {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}"
    }

    try:
        with httpx.Client() as client:
            client.post(webhook_url, json=slack_message)
    except httpx.HTTPError:
        logger.debug("Failed to post error notification to Slack")


def main() -> None:
    """Execute the CHSH daily report."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        config = load_config()

        chsh_data = run_chsh_measurement(config)

        logger.info("CHSH measurement completed")
        logger.info("Value: %.4f ± %.4f", chsh_data.chsh_value, chsh_data.chsh_error)

        post_to_slack(config.slack_webhook_url, chsh_data, config)

        logger.info("CHSH daily report completed successfully")

    except Exception as e:
        logger.exception("Unexpected error")

        # Try to post error to Slack if possible
        try:
            config = load_config()
            post_error_to_slack(config.slack_webhook_url, str(e))
        except Exception:  # noqa: BLE001
            logger.debug("Failed to post error notification to Slack")

        sys.exit(1)


if __name__ == "__main__":
    main()
