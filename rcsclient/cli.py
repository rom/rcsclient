"""Command-line interface for rcsclient."""

import argparse
import re
import sys

from . import __version__
from .client import RCSClient, AuthenticationError, APIError, NetworkError
from .config import load_config, ConfigError
from .models import TextMessage, RichCard, SuggestedReply, SuggestedAction
from .output import (
    print_result,
    print_error,
    format_send_result,
    format_status_result,
    format_revoke_result,
    format_capability_result,
)

# Exit codes
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_BAD_ARGS = 2
EXIT_AUTH = 3
EXIT_API = 4
EXIT_NETWORK = 5
EXIT_TIMEOUT = 6

E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")


def validate_phone(phone: str) -> str:
    if not E164_PATTERN.match(phone):
        raise argparse.ArgumentTypeError(
            f"invalid phone number '{phone}' (must be E.164 format, e.g. +14155551234)"
        )
    return phone


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rcsclient",
        description="Send RCS messages from the command line.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--agent-id", help="RBM agent identifier")
    parser.add_argument("--credentials", help="Path to service account JSON key file")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--json", dest="json_mode", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress non-error output")
    parser.add_argument("--timeout", type=int, help="HTTP timeout in seconds")
    parser.add_argument("--base-url", help="API base URL override")

    sub = parser.add_subparsers(dest="command", help="Command to run")

    # --- send ---
    send_parser = sub.add_parser("send", help="Send a message")
    send_sub = send_parser.add_subparsers(dest="message_type", help="Message type")

    # send text
    text_parser = send_sub.add_parser("text", help="Send a plain text message")
    text_parser.add_argument("--to", required=True, type=validate_phone,
                             help="Recipient phone (E.164)")
    text_parser.add_argument("--message", "-m", required=True,
                             help="Message text")
    text_parser.add_argument("--reply", action="append", default=[],
                             help="Add a suggested reply (can repeat)")
    text_parser.add_argument("--dial", nargs=2, action="append", default=[],
                             metavar=("LABEL", "PHONE"),
                             help="Add a dial action: LABEL PHONE")
    text_parser.add_argument("--url", nargs=2, action="append", default=[],
                             metavar=("LABEL", "URL"),
                             help="Add an open-URL action: LABEL URL")

    # send richcard
    card_parser = send_sub.add_parser("richcard", help="Send a rich card message")
    card_parser.add_argument("--to", required=True, type=validate_phone,
                             help="Recipient phone (E.164)")
    card_parser.add_argument("--title", required=True, help="Card title")
    card_parser.add_argument("--description", required=True, help="Card description")
    card_parser.add_argument("--image-url", help="Image URL for the card")
    card_parser.add_argument("--image-height", default="MEDIUM",
                             choices=["SHORT", "MEDIUM", "TALL"],
                             help="Image height (default: MEDIUM)")
    card_parser.add_argument("--reply", action="append", default=[],
                             help="Add a suggested reply (can repeat)")
    card_parser.add_argument("--url", nargs=2, action="append", default=[],
                             metavar=("LABEL", "URL"),
                             help="Add an open-URL action: LABEL URL")

    # --- status ---
    status_parser = sub.add_parser("status", help="Check message delivery status")
    status_parser.add_argument("--to", required=True, type=validate_phone,
                               help="Recipient phone (E.164)")
    status_parser.add_argument("--message-id", required=True,
                               help="Message ID to check")

    # --- revoke ---
    revoke_parser = sub.add_parser("revoke", help="Revoke a sent message")
    revoke_parser.add_argument("--to", required=True, type=validate_phone,
                               help="Recipient phone (E.164)")
    revoke_parser.add_argument("--message-id", required=True,
                               help="Message ID to revoke")

    # --- capability ---
    cap_parser = sub.add_parser("capability", help="Check RCS capability of a phone")
    cap_parser.add_argument("--to", required=True, type=validate_phone,
                            help="Phone number to check (E.164)")

    return parser


def _build_suggestions(args) -> list:
    suggestions = []
    for text in getattr(args, "reply", []):
        suggestions.append(SuggestedReply(text=text))
    for label, phone in getattr(args, "dial", []):
        suggestions.append(SuggestedAction(text=label, action_type="dial", value=phone))
    for label, url in getattr(args, "url", []):
        suggestions.append(SuggestedAction(text=label, action_type="openUrl", value=url))
    return suggestions


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return EXIT_BAD_ARGS

    # Load configuration
    try:
        config = load_config(
            cli_agent_id=args.agent_id,
            cli_credentials=args.credentials,
            cli_base_url=args.base_url,
            cli_timeout=args.timeout,
            cli_config_path=args.config,
        )
        config.validate()
    except ConfigError as e:
        print_error(str(e))
        return EXIT_BAD_ARGS

    client = RCSClient(config)

    try:
        if args.command == "send":
            if not args.message_type:
                print_error("specify message type: text or richcard")
                return EXIT_BAD_ARGS
            return _cmd_send(client, args)
        elif args.command == "status":
            return _cmd_status(client, args)
        elif args.command == "revoke":
            return _cmd_revoke(client, args)
        elif args.command == "capability":
            return _cmd_capability(client, args)
    except AuthenticationError as e:
        print_error(str(e))
        return EXIT_AUTH
    except APIError as e:
        print_error(f"{e}\n{e.body}" if e.body else str(e))
        return EXIT_API
    except NetworkError as e:
        if "timed out" in str(e):
            print_error(str(e))
            return EXIT_TIMEOUT
        print_error(str(e))
        return EXIT_NETWORK

    return EXIT_OK


def _cmd_send(client: RCSClient, args) -> int:
    suggestions = _build_suggestions(args)

    if args.message_type == "text":
        msg = TextMessage(text=args.message, suggestions=suggestions)
    elif args.message_type == "richcard":
        msg = RichCard(
            title=args.title,
            description=args.description,
            image_url=getattr(args, "image_url", None),
            image_height=getattr(args, "image_height", "MEDIUM"),
            suggestions=suggestions,
        )
    else:
        print_error(f"unknown message type: {args.message_type}")
        return EXIT_BAD_ARGS

    result = client.send_message(args.to, msg)
    print_result(result, format_send_result, msg.message_id,
                 args.json_mode, args.quiet)
    return EXIT_OK


def _cmd_status(client: RCSClient, args) -> int:
    result = client.get_message_status(args.to, args.message_id)
    print_result(result, format_status_result, None,
                 args.json_mode, args.quiet)
    return EXIT_OK


def _cmd_revoke(client: RCSClient, args) -> int:
    result = client.revoke_message(args.to, args.message_id)
    print_result(result, format_revoke_result, None,
                 args.json_mode, args.quiet)
    return EXIT_OK


def _cmd_capability(client: RCSClient, args) -> int:
    result = client.check_capability(args.to)
    print_result(result, format_capability_result, None,
                 args.json_mode, args.quiet)
    return EXIT_OK


def cli_main():
    sys.exit(main())
