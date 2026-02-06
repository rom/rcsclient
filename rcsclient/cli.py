"""Command-line interface for rcsclient."""

import argparse
import json
import re
import sys

from . import __version__
from .config import load_config, ConfigError, DEFAULT_CONFIG_PATH
from .models import (
    TextMessage, RichCard, CarouselCard, Carousel, MediaMessage,
    SuggestedReply, SuggestedAction, ViewLocationAction, CreateCalendarEventAction,
)
from .output import (
    print_result,
    print_error,
    format_send_result,
    format_status_result,
    format_revoke_result,
    format_capability_result,
    format_event_result,
    format_tester_invite_result,
    format_tester_remove_result,
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


def _add_suggestion_args(parser):
    """Add common suggestion arguments to a send subcommand parser."""
    parser.add_argument("--reply", action="append", default=[],
                        help="Add a suggested reply (can repeat)")
    parser.add_argument("--dial", nargs=2, action="append", default=[],
                        metavar=("LABEL", "PHONE"),
                        help="Add a dial action: LABEL PHONE")
    parser.add_argument("--url", nargs=2, action="append", default=[],
                        metavar=("LABEL", "URL"),
                        help="Add an open-URL action: LABEL URL")
    parser.add_argument("--share-location", dest="share_location",
                        action="append", default=[], metavar="LABEL",
                        help="Add a share-location action with LABEL")
    parser.add_argument("--location", nargs="+", action="append", default=[],
                        metavar="ARG",
                        help="View-location action: LABEL LAT LONG [MAP_LABEL]")
    parser.add_argument("--calendar", nargs="+", action="append", default=[],
                        metavar="ARG",
                        help="Calendar event action: LABEL TITLE START END [DESC]")


class _HyphenSafeParser(argparse.ArgumentParser):
    """ArgumentParser subclass that catches mis-split hyphenated options.

    Standard ``argparse`` silently converts dashes inside option names
    to underscores when building the ``dest`` attribute, but the mapping
    is implicit and easy to get wrong.  This subclass intercepts stray
    single-dash fragments that look like part of a known long option
    (e.g. ``--agent -id`` instead of ``--agent-id``) and raises a clear
    error instead of silently consuming them as values.
    """

    def _parse_optional(self, arg_string):
        result = super()._parse_optional(arg_string)

        # Only inspect unrecognised single-dash tokens (like ``-id``)
        if result is None and arg_string.startswith("-") and not arg_string.startswith("--"):
            fragment = arg_string.lstrip("-")
            for action in self._actions:
                for opt in action.option_strings:
                    if opt.startswith("--") and opt.endswith("-" + fragment):
                        self.error(
                            f"unrecognised option '{arg_string}'; "
                            f"did you mean '{opt}'?"
                        )
        return result


def build_parser() -> _HyphenSafeParser:
    parser = _HyphenSafeParser(
        prog="rcsclient",
        description="Send RCS messages from the command line.",
    )
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")

    # --- global options (explicit dest for every hyphenated name) ---
    parser.add_argument("--agent-id", dest="agent_id",
                        metavar="ID",
                        help="RBM agent identifier")
    parser.add_argument("--credentials", metavar="PATH",
                        help="Path to service account JSON key file")
    parser.add_argument("--config", metavar="PATH",
                        help="Path to config file")
    parser.add_argument("--json", dest="json_mode", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress non-error output")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose/debug output")
    parser.add_argument("--timeout", type=int, metavar="SECONDS",
                        help="HTTP timeout in seconds")
    parser.add_argument("--base-url", dest="base_url",
                        metavar="URL",
                        help="API base URL override")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="Show what would be sent without making API calls")
    parser.add_argument("--output", "-o", dest="output_file",
                        metavar="FILE",
                        help="Write output to FILE instead of stdout")
    parser.add_argument("--max-retries", dest="max_retries",
                        type=int, metavar="N",
                        help="Maximum number of retries for failed requests")

    sub = parser.add_subparsers(dest="command", help="Command to run")

    # --- send ---
    send_parser = sub.add_parser("send", help="Send a message")
    send_sub = send_parser.add_subparsers(dest="message_type",
                                          help="Message type")

    # send text
    text_parser = send_sub.add_parser("text",
                                      help="Send a plain text message")
    text_parser.add_argument("--to", required=True, type=validate_phone,
                             help="Recipient phone (E.164)")
    text_parser.add_argument("--message", "-m", required=True,
                             help="Message text")
    text_parser.add_argument("--recipients-file", dest="recipients_file",
                             metavar="FILE",
                             help="File with phone numbers (one per line) "
                                  "for batch send")
    _add_suggestion_args(text_parser)

    # send richcard
    card_parser = send_sub.add_parser("richcard",
                                      help="Send a rich card message")
    card_parser.add_argument("--to", required=True, type=validate_phone,
                             help="Recipient phone (E.164)")
    card_parser.add_argument("--title", required=True, help="Card title")
    card_parser.add_argument("--description", required=True,
                             help="Card description")
    card_parser.add_argument("--image-url", dest="image_url",
                             metavar="URL",
                             help="Image URL for the card")
    card_parser.add_argument("--image-height", dest="image_height",
                             default="MEDIUM",
                             choices=["SHORT", "MEDIUM", "TALL"],
                             help="Image height (default: MEDIUM)")
    _add_suggestion_args(card_parser)

    # send carousel
    carousel_parser = send_sub.add_parser("carousel",
                                          help="Send a carousel message")
    carousel_parser.add_argument("--to", required=True, type=validate_phone,
                                 help="Recipient phone (E.164)")
    carousel_parser.add_argument("--card", nargs="+", action="append",
                                 default=[], metavar="ARG",
                                 help="Add a card: TITLE DESCRIPTION "
                                      "[IMAGE_URL]")
    carousel_parser.add_argument("--card-width", dest="card_width",
                                 default="MEDIUM",
                                 choices=["SMALL", "MEDIUM"],
                                 help="Card width (default: MEDIUM)")
    _add_suggestion_args(carousel_parser)

    # send media
    media_parser = send_sub.add_parser("media",
                                       help="Send a media file message")
    media_parser.add_argument("--to", required=True, type=validate_phone,
                              help="Recipient phone (E.164)")
    media_parser.add_argument("--file-url", dest="file_url", required=True,
                              metavar="URL",
                              help="URL of the media file")
    media_parser.add_argument("--content-type", dest="content_type",
                              default="", metavar="MIME",
                              help="MIME type (e.g. image/jpeg, video/mp4)")
    media_parser.add_argument("--thumbnail-url", dest="thumbnail_url",
                              default="", metavar="URL",
                              help="Thumbnail URL for the media")
    media_parser.add_argument("--force-refresh", dest="force_refresh",
                              action="store_true",
                              help="Force the platform to re-fetch the file")
    _add_suggestion_args(media_parser)

    # --- status ---
    status_parser = sub.add_parser("status",
                                   help="Check message delivery status")
    status_parser.add_argument("--to", required=True, type=validate_phone,
                               help="Recipient phone (E.164)")
    status_parser.add_argument("--message-id", dest="message_id",
                               required=True, metavar="ID",
                               help="Message ID to check")

    # --- revoke ---
    revoke_parser = sub.add_parser("revoke", help="Revoke a sent message")
    revoke_parser.add_argument("--to", required=True, type=validate_phone,
                               help="Recipient phone (E.164)")
    revoke_parser.add_argument("--message-id", dest="message_id",
                               required=True, metavar="ID",
                               help="Message ID to revoke")

    # --- capability ---
    cap_parser = sub.add_parser("capability",
                                help="Check RCS capability of a phone")
    cap_parser.add_argument("--to", required=True, type=validate_phone,
                            help="Phone number to check (E.164)")

    # --- event ---
    event_parser = sub.add_parser("event", help="Send an agent event")
    event_parser.add_argument("--to", required=True, type=validate_phone,
                              help="Recipient phone (E.164)")
    event_parser.add_argument("--type", required=True, dest="event_type",
                              choices=["IS_TYPING", "READ"],
                              help="Event type")
    event_parser.add_argument("--message-id", dest="message_id", default="",
                              metavar="ID",
                              help="Message ID (required for READ events)")

    # --- tester ---
    tester_parser = sub.add_parser("tester", help="Manage testers")
    tester_sub = tester_parser.add_subparsers(dest="tester_action",
                                              help="Tester action")

    tester_invite = tester_sub.add_parser("invite",
                                          help="Invite a tester")
    tester_invite.add_argument("--phone", required=True,
                               type=validate_phone,
                               help="Phone number to invite (E.164)")

    tester_remove = tester_sub.add_parser("remove",
                                          help="Remove a tester")
    tester_remove.add_argument("--phone", required=True,
                               type=validate_phone,
                               help="Phone number to remove (E.164)")

    # --- config ---
    config_parser = sub.add_parser("config",
                                   help="Manage configuration")
    config_sub = config_parser.add_subparsers(dest="config_action",
                                              help="Config action")

    config_sub.add_parser("show", help="Show current configuration")

    config_init = config_sub.add_parser("init",
                                        help="Create a default config file")
    config_init.add_argument("--force", action="store_true",
                             help="Overwrite existing config file")

    return parser


def _build_suggestions(args) -> list:
    suggestions = []
    for text in getattr(args, "reply", []):
        suggestions.append(SuggestedReply(text=text))
    for label, phone in getattr(args, "dial", []):
        suggestions.append(SuggestedAction(text=label, action_type="dial", value=phone))
    for label, url in getattr(args, "url", []):
        suggestions.append(SuggestedAction(text=label, action_type="openUrl", value=url))
    for label in getattr(args, "share_location", []):
        suggestions.append(SuggestedAction(text=label, action_type="shareLocation"))
    for loc_args in getattr(args, "location", []):
        if len(loc_args) < 3:
            continue
        try:
            lat = float(loc_args[1])
            lon = float(loc_args[2])
        except ValueError:
            continue
        map_label = loc_args[3] if len(loc_args) > 3 else ""
        suggestions.append(ViewLocationAction(
            text=loc_args[0], latitude=lat, longitude=lon, label=map_label,
        ))
    for cal_args in getattr(args, "calendar", []):
        if len(cal_args) < 4:
            continue
        desc = cal_args[4] if len(cal_args) > 4 else ""
        suggestions.append(CreateCalendarEventAction(
            text=cal_args[0], title=cal_args[1],
            start_time=cal_args[2], end_time=cal_args[3], description=desc,
        ))
    return suggestions


def _verbose_log(args, message: str):
    """Print a debug message when --verbose is active."""
    if getattr(args, "verbose", False):
        print(f"[debug] {message}", file=sys.stderr)


def _write_output(args, text: str):
    """Write output to file (--output) or stdout."""
    output_file = getattr(args, "output_file", None)
    if output_file:
        with open(output_file, "a") as f:
            f.write(text + "\n")
    else:
        print(text)


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return EXIT_BAD_ARGS

    # Handle config subcommands (no API client needed)
    if args.command == "config":
        return _cmd_config(args)

    # Load configuration
    try:
        _verbose_log(args, f"loading config (cli_agent_id={args.agent_id})")
        config = load_config(
            cli_agent_id=args.agent_id,
            cli_credentials=args.credentials,
            cli_base_url=args.base_url,
            cli_timeout=args.timeout,
            cli_config_path=args.config,
        )

        if args.max_retries is not None:
            _verbose_log(args, f"overriding max_retries={args.max_retries}")

        config.validate()
    except ConfigError as e:
        print_error(str(e))
        return EXIT_BAD_ARGS

    _verbose_log(args, f"config loaded: agent_id={config.agent_id}, "
                       f"base_url={config.base_url}, timeout={config.timeout}")

    if args.dry_run:
        _verbose_log(args, "dry-run mode enabled")

    # Late import so config subcommands don't need google-auth installed
    from .client import RCSClient, AuthenticationError, APIError, NetworkError

    client = RCSClient(config)

    # Apply max_retries if given
    if args.max_retries is not None:
        from . import client as client_mod
        client_mod.MAX_RETRIES = args.max_retries

    try:
        if args.command == "send":
            if not args.message_type:
                print_error("specify message type: text, richcard, "
                            "carousel, or media")
                return EXIT_BAD_ARGS
            return _cmd_send(client, args)
        elif args.command == "status":
            return _cmd_status(client, args)
        elif args.command == "revoke":
            return _cmd_revoke(client, args)
        elif args.command == "capability":
            return _cmd_capability(client, args)
        elif args.command == "event":
            return _cmd_event(client, args)
        elif args.command == "tester":
            return _cmd_tester(client, args)
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


def _cmd_send(client, args) -> int:
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
    elif args.message_type == "carousel":
        cards = []
        for card_args in getattr(args, "card", []):
            if len(card_args) < 2:
                print_error("each --card needs at least TITLE and DESCRIPTION")
                return EXIT_BAD_ARGS
            image_url = card_args[2] if len(card_args) > 2 else None
            cards.append(CarouselCard(
                title=card_args[0], description=card_args[1],
                image_url=image_url,
            ))
        if len(cards) < 2:
            print_error("carousel requires at least 2 cards")
            return EXIT_BAD_ARGS
        msg = Carousel(
            cards=cards,
            card_width=getattr(args, "card_width", "MEDIUM"),
            suggestions=suggestions,
        )
    elif args.message_type == "media":
        msg = MediaMessage(
            file_url=args.file_url,
            content_type=getattr(args, "content_type", ""),
            thumbnail_url=getattr(args, "thumbnail_url", ""),
            force_refresh=getattr(args, "force_refresh", False),
            suggestions=suggestions,
        )
    else:
        print_error(f"unknown message type: {args.message_type}")
        return EXIT_BAD_ARGS

    # Collect recipients (primary --to plus optional --recipients-file)
    recipients = [args.to]
    recipients_file = getattr(args, "recipients_file", None)
    if recipients_file:
        try:
            with open(recipients_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if not E164_PATTERN.match(line):
                            print_error(
                                f"invalid phone number in recipients "
                                f"file: '{line}'"
                            )
                            return EXIT_BAD_ARGS
                        if line not in recipients:
                            recipients.append(line)
        except OSError as e:
            print_error(f"failed to read recipients file: {e}")
            return EXIT_BAD_ARGS
        _verbose_log(args, f"batch send to {len(recipients)} recipients")

    if args.dry_run:
        payload = msg.to_api_payload()
        payload["messageId"] = msg.message_id
        dry_info = {
            "dry_run": True,
            "recipients": recipients,
            "payload": payload,
        }
        _write_output(args, json.dumps(dry_info, indent=2))
        return EXIT_OK

    errors = []
    for phone in recipients:
        _verbose_log(args, f"sending to {phone}")
        try:
            result = client.send_message(phone, msg)
            print_result(result, format_send_result, msg.message_id,
                         args.json_mode, args.quiet)
        except Exception as e:
            errors.append((phone, str(e)))
            print_error(f"failed to send to {phone}: {e}")

    if errors:
        return EXIT_API if len(errors) < len(recipients) else EXIT_ERROR

    return EXIT_OK


def _cmd_status(client, args) -> int:
    if args.dry_run:
        _write_output(args, json.dumps({
            "dry_run": True,
            "action": "get_status",
            "phone": args.to,
            "message_id": args.message_id,
        }, indent=2))
        return EXIT_OK

    result = client.get_message_status(args.to, args.message_id)
    print_result(result, format_status_result, None,
                 args.json_mode, args.quiet)
    return EXIT_OK


def _cmd_revoke(client, args) -> int:
    if args.dry_run:
        _write_output(args, json.dumps({
            "dry_run": True,
            "action": "revoke",
            "phone": args.to,
            "message_id": args.message_id,
        }, indent=2))
        return EXIT_OK

    result = client.revoke_message(args.to, args.message_id)
    print_result(result, format_revoke_result, None,
                 args.json_mode, args.quiet)
    return EXIT_OK


def _cmd_capability(client, args) -> int:
    if args.dry_run:
        _write_output(args, json.dumps({
            "dry_run": True,
            "action": "check_capability",
            "phone": args.to,
        }, indent=2))
        return EXIT_OK

    result = client.check_capability(args.to)
    print_result(result, format_capability_result, None,
                 args.json_mode, args.quiet)
    return EXIT_OK


def _cmd_event(client, args) -> int:
    if args.event_type == "READ" and not args.message_id:
        print_error("--message-id is required for READ events")
        return EXIT_BAD_ARGS

    if args.dry_run:
        _write_output(args, json.dumps({
            "dry_run": True,
            "action": "send_event",
            "phone": args.to,
            "event_type": args.event_type,
            "message_id": args.message_id,
        }, indent=2))
        return EXIT_OK

    result = client.send_event(args.to, args.event_type, args.message_id)
    print_result(result, format_event_result, args.event_type,
                 args.json_mode, args.quiet)
    return EXIT_OK


def _cmd_tester(client, args) -> int:
    if not getattr(args, "tester_action", None):
        print_error("specify tester action: invite or remove")
        return EXIT_BAD_ARGS

    if args.dry_run:
        _write_output(args, json.dumps({
            "dry_run": True,
            "action": f"tester_{args.tester_action}",
            "phone": args.phone,
        }, indent=2))
        return EXIT_OK

    if args.tester_action == "invite":
        result = client.invite_tester(args.phone)
        print_result(result, format_tester_invite_result, args.phone,
                     args.json_mode, args.quiet)
    elif args.tester_action == "remove":
        result = client.remove_tester(args.phone)
        print_result(result, format_tester_remove_result, args.phone,
                     args.json_mode, args.quiet)
    return EXIT_OK


def _cmd_config(args) -> int:
    """Handle the 'config' subcommand."""
    action = getattr(args, "config_action", None)
    if not action:
        print_error("specify config action: show or init")
        return EXIT_BAD_ARGS

    if action == "show":
        return _config_show(args)
    elif action == "init":
        return _config_init(args)

    return EXIT_BAD_ARGS


def _config_show(args) -> int:
    """Display the current resolved configuration."""
    import os
    from pathlib import Path

    config_path = args.config or str(DEFAULT_CONFIG_PATH)
    info = {
        "config_file": config_path,
        "config_file_exists": Path(config_path).exists(),
        "environment": {
            "RCS_AGENT_ID": os.environ.get("RCS_AGENT_ID", "(not set)"),
            "RCS_CREDENTIALS": os.environ.get("RCS_CREDENTIALS", "(not set)"),
            "RCS_BASE_URL": os.environ.get("RCS_BASE_URL", "(not set)"),
            "RCS_TIMEOUT": os.environ.get("RCS_TIMEOUT", "(not set)"),
        },
    }

    if Path(config_path).exists():
        try:
            with open(config_path) as f:
                info["file_contents"] = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            info["file_error"] = str(e)

    _write_output(args, json.dumps(info, indent=2))
    return EXIT_OK


def _config_init(args) -> int:
    """Create a default configuration file."""
    from pathlib import Path

    config_path = Path(args.config) if args.config else DEFAULT_CONFIG_PATH
    force = getattr(args, "force", False)

    if config_path.exists() and not force:
        print_error(
            f"config file already exists: {config_path} "
            f"(use --force to overwrite)"
        )
        return EXIT_BAD_ARGS

    template = {
        "agent_id": "",
        "credentials_file": "",
        "base_url": "https://rcsbusinessmessaging.googleapis.com",
        "timeout": 30,
    }

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(template, f, indent=2)
            f.write("\n")
        _write_output(args, f"Config file created: {config_path}")
        _write_output(args, "Edit it to fill in your agent_id and "
                            "credentials_file.")
    except OSError as e:
        print_error(f"failed to write config file: {e}")
        return EXIT_ERROR

    return EXIT_OK


def cli_main():
    sys.exit(main())
