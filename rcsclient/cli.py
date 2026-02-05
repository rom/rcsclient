"""Command-line interface for rcsclient."""

import argparse
import re
import sys

from . import __version__
from .client import RCSClient, AuthenticationError, APIError, NetworkError
from .config import load_config, ConfigError
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
    _add_suggestion_args(text_parser)

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
    _add_suggestion_args(card_parser)

    # send carousel
    carousel_parser = send_sub.add_parser("carousel", help="Send a carousel message")
    carousel_parser.add_argument("--to", required=True, type=validate_phone,
                                 help="Recipient phone (E.164)")
    carousel_parser.add_argument("--card", nargs="+", action="append", default=[],
                                 metavar="ARG",
                                 help="Add a card: TITLE DESCRIPTION [IMAGE_URL]")
    carousel_parser.add_argument("--card-width", default="MEDIUM",
                                 choices=["SMALL", "MEDIUM"],
                                 help="Card width (default: MEDIUM)")
    _add_suggestion_args(carousel_parser)

    # send media
    media_parser = send_sub.add_parser("media", help="Send a media file message")
    media_parser.add_argument("--to", required=True, type=validate_phone,
                              help="Recipient phone (E.164)")
    media_parser.add_argument("--file-url", required=True,
                              help="URL of the media file")
    media_parser.add_argument("--content-type", default="",
                              help="MIME type (e.g. image/jpeg, video/mp4)")
    media_parser.add_argument("--thumbnail-url", default="",
                              help="Thumbnail URL for the media")
    media_parser.add_argument("--force-refresh", action="store_true",
                              help="Force the platform to re-fetch the file")
    _add_suggestion_args(media_parser)

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

    # --- event ---
    event_parser = sub.add_parser("event", help="Send an agent event")
    event_parser.add_argument("--to", required=True, type=validate_phone,
                              help="Recipient phone (E.164)")
    event_parser.add_argument("--type", required=True, dest="event_type",
                              choices=["IS_TYPING", "READ"],
                              help="Event type")
    event_parser.add_argument("--message-id", default="",
                              help="Message ID (required for READ events)")

    # --- tester ---
    tester_parser = sub.add_parser("tester", help="Manage testers")
    tester_sub = tester_parser.add_subparsers(dest="tester_action", help="Tester action")

    tester_invite = tester_sub.add_parser("invite", help="Invite a tester")
    tester_invite.add_argument("--phone", required=True, type=validate_phone,
                               help="Phone number to invite (E.164)")

    tester_remove = tester_sub.add_parser("remove", help="Remove a tester")
    tester_remove.add_argument("--phone", required=True, type=validate_phone,
                               help="Phone number to remove (E.164)")

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
                print_error("specify message type: text, richcard, carousel, or media")
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
    elif args.message_type == "carousel":
        cards = []
        for card_args in getattr(args, "card", []):
            if len(card_args) < 2:
                print_error("each --card needs at least TITLE and DESCRIPTION")
                return EXIT_BAD_ARGS
            image_url = card_args[2] if len(card_args) > 2 else None
            cards.append(CarouselCard(
                title=card_args[0], description=card_args[1], image_url=image_url,
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


def _cmd_event(client: RCSClient, args) -> int:
    if args.event_type == "READ" and not args.message_id:
        print_error("--message-id is required for READ events")
        return EXIT_BAD_ARGS
    result = client.send_event(args.to, args.event_type, args.message_id)
    print_result(result, format_event_result, args.event_type,
                 args.json_mode, args.quiet)
    return EXIT_OK


def _cmd_tester(client: RCSClient, args) -> int:
    if not getattr(args, "tester_action", None):
        print_error("specify tester action: invite or remove")
        return EXIT_BAD_ARGS
    if args.tester_action == "invite":
        result = client.invite_tester(args.phone)
        print_result(result, format_tester_invite_result, args.phone,
                     args.json_mode, args.quiet)
    elif args.tester_action == "remove":
        result = client.remove_tester(args.phone)
        print_result(result, format_tester_remove_result, args.phone,
                     args.json_mode, args.quiet)
    return EXIT_OK


def cli_main():
    sys.exit(main())
