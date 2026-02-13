#!/usr/bin/env python3
"""
CHSH Daily Report Script

Runs CHSH measurement and posts results to Slack.

Reads all configuration from config.toml (including Slack webhook URL).

Usage:
    uv run scripts/chsh_daily_report.py
"""

import json
import sys
import tomllib
from datetime import datetime
from pathlib import Path

import httpx


def load_config() -> dict:
    """Load configuration from config.toml."""
    config_path = Path(__file__).parent.parent / "config.toml"

    if not config_path.exists():
        print(f"❌ Error: config.toml not found at {config_path}")
        print("Please create config.toml from configs/config_app_example.toml")
        sys.exit(1)

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def get_daily_report_config(config: dict) -> dict:
    """Get and validate daily_report configuration."""
    daily_report_config = config.get("daily_report", {})

    if not daily_report_config:
        print("❌ Error: [daily_report] section not found in config.toml")
        print("Please add it following the example in configs/config_app_example.toml")
        sys.exit(1)

    # Check required fields
    required_fields = ["slack_webhook_url", "follower_node_address"]
    for field in required_fields:
        if not daily_report_config.get(field):
            print(f"❌ Error: {field} not set in config.toml [daily_report] section")
            sys.exit(1)

    return daily_report_config


def run_chsh_measurement(config: dict) -> dict:
    """Run CHSH measurement via API."""
    daily_report_config = get_daily_report_config(config)

    api_url = daily_report_config.get("api_url", "http://localhost:8000")
    timetagger_address = daily_report_config.get("timetagger_address", "127.0.0.1:8000")
    follower_node_address = daily_report_config["follower_node_address"]
    basis = daily_report_config.get("basis", [0, 22.5])

    print(f"🔬 Starting CHSH measurement at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Basis: {basis}")
    print(f"   Follower: {follower_node_address}")
    print(f"   TimeTagger: {timetagger_address}")

    try:
        with httpx.Client(timeout=600.0) as client:
            response = client.post(
                f"{api_url}/chsh/",
                params={
                    "follower_node_address": follower_node_address,
                    "timetagger_address": timetagger_address,
                },
                json={"basis": basis}
            )
            response.raise_for_status()
            return response.json()

    except httpx.HTTPError as e:
        print(f"❌ Failed to contact CHSH API: {e}")
        sys.exit(1)


def post_to_slack(webhook_url: str, chsh_data: dict, config: dict):
    """Post CHSH results to Slack."""
    chsh_value = chsh_data["chsh_value"]
    chsh_error = chsh_data["chsh_error"]
    expectation_values = chsh_data["expectation_values"]
    expectation_errors = chsh_data["expectation_errors"]
    expectation_values_sign_fixed = chsh_data["expectation_values_sign_fixed"]

    # Determine emoji based on Bell inequality violation (CHSH > 2)
    emoji = ":sparkles:" if chsh_value > 2 else ":thinking_face:"

    daily_report_config = config.get("daily_report", {})
    basis = daily_report_config.get("basis", [0, 22.5])
    follower_address = daily_report_config.get("follower_node_address", "unknown")
    timetagger_address = daily_report_config.get("timetagger_address", "unknown")

    # Format Slack message using Block Kit
    slack_message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} CHSH Daily Measurement Report",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*CHSH Value:*\n`{chsh_value:.4f}` ± `{chsh_error:.4f}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Basis:*\n`{basis}`"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Expectation Values:*\n`{expectation_values}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Expectation Errors:*\n`{expectation_errors}`"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Expectation Values (Sign Fixed):*\n`{expectation_values_sign_fixed}`"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Timestamp:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Follower: `{follower_address}` | TimeTagger: `{timetagger_address}`"
                    }
                ]
            }
        ]
    }

    print("📤 Posting to Slack...")

    try:
        with httpx.Client() as client:
            response = client.post(webhook_url, json=slack_message)

            if response.text == "ok":
                print("✅ Successfully posted to Slack")
            else:
                print(f"❌ Failed to post to Slack: {response.text}")
                sys.exit(1)

    except httpx.HTTPError as e:
        print(f"❌ Failed to post to Slack: {e}")
        sys.exit(1)


def post_error_to_slack(webhook_url: str, error_message: str):
    """Post error message to Slack."""
    slack_message = {
        "text": f":x: CHSH Daily Report Failed\n*Error:* {error_message}\n*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    }

    try:
        with httpx.Client() as client:
            client.post(webhook_url, json=slack_message)
    except Exception:
        pass  # Silently fail if we can't post the error


def main():
    """Main entry point."""
    try:
        # Load configuration
        config = load_config()
        daily_report_config = get_daily_report_config(config)
        webhook_url = daily_report_config["slack_webhook_url"]

        # Run CHSH measurement
        chsh_data = run_chsh_measurement(config)

        print(f"✅ CHSH measurement completed")
        print(f"   Value: {chsh_data['chsh_value']:.4f} ± {chsh_data['chsh_error']:.4f}")

        # Post to Slack
        post_to_slack(webhook_url, chsh_data, config)

        print("✅ CHSH daily report completed successfully")

    except Exception as e:
        print(f"❌ Unexpected error: {e}")

        # Try to post error to Slack if possible
        try:
            config = load_config()
            daily_report_config = get_daily_report_config(config)
            webhook_url = daily_report_config["slack_webhook_url"]
            post_error_to_slack(webhook_url, str(e))
        except Exception:
            pass

        sys.exit(1)


if __name__ == "__main__":
    main()