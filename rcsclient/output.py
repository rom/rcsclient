"""Output formatting for CLI results."""

import json
import sys


def is_tty() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def format_json(data: dict) -> str:
    return json.dumps(data, indent=2)


def format_send_result(data: dict, message_id: str) -> str:
    lines = [
        f"Message sent successfully.",
        f"  Message ID: {message_id}",
    ]
    if "name" in data:
        lines.append(f"  Resource:   {data['name']}")
    return "\n".join(lines)


def format_status_result(data: dict) -> str:
    status = data.get("status", "UNKNOWN")
    lines = [
        f"Message status: {status}",
    ]
    if "name" in data:
        lines.append(f"  Resource: {data['name']}")
    return "\n".join(lines)


def format_revoke_result(data: dict) -> str:
    return "Message revoked successfully."


def format_capability_result(data: dict) -> str:
    features = data.get("features", [])
    if features:
        lines = ["RCS capabilities:"]
        for feat in features:
            lines.append(f"  - {feat}")
        return "\n".join(lines)
    return "Phone supports RCS (no detailed features returned)."


def print_result(data: dict, formatter, format_arg: str, json_mode: bool, quiet: bool):
    """Print a result to stdout using the appropriate format.

    Args:
        data: The API response data.
        formatter: A callable that formats data for human-readable output.
        format_arg: Extra argument passed to the formatter (e.g., message_id).
        json_mode: If True, always output JSON.
        quiet: If True, suppress output entirely.
    """
    if quiet:
        return
    if json_mode or not is_tty():
        print(format_json(data))
    else:
        if format_arg is not None:
            print(formatter(data, format_arg))
        else:
            print(formatter(data))


def print_error(message: str):
    """Print an error message to stderr."""
    print(f"error: {message}", file=sys.stderr)
