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

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load configuration from config.toml."""
    config_path = Path(__file__).parent.parent / "config.toml"

    if not config_path.exists():
        logger.error("config.toml not found at %s", config_path)
        logger.error("Please create config.toml from configs/config_app_example.toml")
        sys.exit(1)

    with config_path.open("rb") as f:
        return tomllib.load(f)


def get_daily_report_config(config: dict) -> dict:
    """Get and validate daily_report configuration."""
    daily_report_config = config.get("daily_report", {})

    if not daily_report_config:
        logger.error("[daily_report] section not found in config.toml")
        logger.error("Please add it following the example in configs/config_app_example.toml")
        sys.exit(1)

    # Check required fields
    required_fields = ["slack_webhook_url", "follower_node_address"]
    for field in required_fields:
        if not daily_report_config.get(field):
            logger.error("%s not set in config.toml [daily_report] section", field)
            sys.exit(1)

    return daily_report_config


def run_chsh_measurement(config: dict) -> dict:
    """Run CHSH measurement via API."""
    daily_report_config = get_daily_report_config(config)

    api_url = daily_report_config.get("api_url", "http://localhost:8000")
    timetagger_address = daily_report_config.get("timetagger_address", "127.0.0.1:8000")
    follower_node_address = daily_report_config["follower_node_address"]
    basis = daily_report_config.get("basis", [0, 22.5])

    logger.info("Starting CHSH measurement at %s", datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("Basis: %s", basis)
    logger.info("Follower: %s", follower_node_address)
    logger.info("TimeTagger: %s", timetagger_address)

    try:
        with httpx.Client(timeout=600.0) as client:
            response = client.post(
                f"{api_url}/chsh/",
                params={
                    "follower_node_address": follower_node_address,
                    "timetagger_address": timetagger_address,
                },
                json=basis,
            )
            response.raise_for_status()
            return response.json()

    except httpx.HTTPError:
        logger.exception("Failed to contact CHSH API")
        sys.exit(1)


def post_to_slack(webhook_url: str, chsh_data: dict, config: dict):
    """Post CHSH results to Slack."""
    # Determine emoji based on Bell inequality violation (CHSH > classical limit) if chsh_value exists
    bell_inequality_classical_limit = 2
    chsh_value = chsh_data.get("chsh_value", 0)
    emoji = ":sparkles:" if chsh_value > bell_inequality_classical_limit else ":thinking_face:"

    daily_report_config = config.get("daily_report", {})
    basis = daily_report_config.get("basis", [0, 22.5])
    follower_address = daily_report_config.get("follower_node_address", "unknown")
    timetagger_address = daily_report_config.get("timetagger_address", "unknown")

    # Build fields dynamically from all returned data
    fields = []

    # Add all fields from the API response
    for key, value in chsh_data.items():
        # Format the key nicely (replace underscores with spaces, capitalize)
        field_name = key.replace("_", " ").title()

        # Format the value based on type
        if isinstance(value, float):
            formatted_value = f"{value:.4f}"
        elif isinstance(value, list):
            # Format list nicely
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
                {"type": "mrkdwn", "text": f"*Basis:*\n`{basis}`"},
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
                    {"type": "mrkdwn", "text": f"Follower: `{follower_address}` | TimeTagger: `{timetagger_address}`"}
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


def post_error_to_slack(webhook_url: str, error_message: str):
    """Post error message to Slack."""
    slack_message = {
        "text": f":x: CHSH Daily Report Failed\n*Error:* {error_message}\n*Time:* {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}"
    }

    try:
        with httpx.Client() as client:
            client.post(webhook_url, json=slack_message)
    except httpx.HTTPError:
        logger.debug("Failed to post error notification to Slack")


def main():
    """Execute the CHSH daily report."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        # Load configuration
        config = load_config()
        daily_report_config = get_daily_report_config(config)
        webhook_url = daily_report_config["slack_webhook_url"]

        # Run CHSH measurement
        chsh_data = run_chsh_measurement(config)

        logger.info("CHSH measurement completed")
        logger.info("Value: %.4f ± %.4f", chsh_data["chsh_value"], chsh_data["chsh_error"])

        # Post to Slack
        post_to_slack(webhook_url, chsh_data, config)

        logger.info("CHSH daily report completed successfully")

    except Exception as e:
        logger.exception("Unexpected error")

        # Try to post error to Slack if possible
        try:
            config = load_config()
            daily_report_config = get_daily_report_config(config)
            webhook_url = daily_report_config["slack_webhook_url"]
            post_error_to_slack(webhook_url, str(e))
        except Exception:  # noqa: BLE001
            logger.debug("Failed to post error notification to Slack")

        sys.exit(1)


if __name__ == "__main__":
    main()
