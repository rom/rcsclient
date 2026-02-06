# RCS Client Design Document

## Overview

`rcsclient` is a command-line tool for sending RCS (Rich Communication Services)
messages. It targets the Google RCS Business Messaging (RBM) API and is designed
to be used both interactively by a person and programmatically by scripts or
other programs.

## Goals

- Send RCS text messages to phone numbers
- Send rich cards with images, titles, and descriptions
- Send carousel messages with multiple cards
- Send standalone media files (images, videos, PDFs)
- Send suggested replies and actions alongside messages (dial, open URL,
  view location, create calendar event, share location)
- Send agent events (typing indicators, read receipts)
- Manage testers for the agent
- Check message delivery status
- Automatic retry with exponential backoff for transient failures
- Be scriptable: deterministic exit codes, optional JSON output, quiet mode
- Support configuration via file, environment variables, and CLI flags

## Non-Goals

- Receiving inbound messages (that requires a webhook server)
- Group messaging
- GUI or TUI interface
- Supporting non-Google RCS APIs (though the design allows future providers)

## Architecture

```
rcsclient/
├── rcsclient/           # Python package
│   ├── __init__.py      # Package version
│   ├── __main__.py      # python -m rcsclient entry point
│   ├── cli.py           # Argument parsing and command dispatch
│   ├── client.py        # RCS Business Messaging API client
│   ├── config.py        # Configuration loading (file, env, flags)
│   ├── models.py        # Data classes for messages, cards, suggestions
│   └── output.py        # Output formatting (text, JSON)
├── tests/
│   ├── __init__.py
│   ├── test_client.py   # API client tests (incl. retry, events, testers)
│   ├── test_config.py   # Configuration tests
│   └── test_models.py   # Model tests (all message and action types)
├── requirements.txt     # Runtime dependencies
├── setup.py             # Package installation
├── DESIGN.md            # This file
└── README.md            # User-facing documentation
```

### Component Responsibilities

**cli.py** - Entry point. Parses arguments with `argparse`, loads
configuration, dispatches to the appropriate action (send, status, revoke,
capability, event, tester), formats output, and sets the exit code.

**client.py** - Thin wrapper around the Google RBM REST API. Handles
authentication (OAuth2 service account), request construction, HTTP calls,
response parsing, and automatic retry with exponential backoff. Uses `requests`
for HTTP. All methods return structured data or raise typed exceptions.

**config.py** - Loads configuration from three sources in priority order:
1. CLI flags (highest priority)
2. Environment variables (`RCS_AGENT_ID`, `RCS_CREDENTIALS`, etc.)
3. Configuration file (`~/.rcsclient.json` or path from `--config`)

**models.py** - Plain data classes representing RCS message types: text
messages, rich cards, carousel cards, carousel messages, media messages,
suggested replies, and suggested actions (dial, open URL, share location,
view location, create calendar event).

**output.py** - Formats results for display. Supports two modes: human-readable
text (default for terminals) and JSON (default for pipes, or via `--json`).

## API Mapping

The client targets the Google RCS Business Messaging API v1.

| Command             | HTTP Method | Endpoint                                                    |
|---------------------|-------------|-------------------------------------------------------------|
| `send text`         | POST        | `/v1/phones/{E.164}/agentMessages`                          |
| `send richcard`     | POST        | `/v1/phones/{E.164}/agentMessages`                          |
| `send carousel`     | POST        | `/v1/phones/{E.164}/agentMessages`                          |
| `send media`        | POST        | `/v1/phones/{E.164}/agentMessages`                          |
| `status`            | GET         | `/v1/phones/{E.164}/agentMessages/{messageId}`              |
| `revoke`            | DELETE      | `/v1/phones/{E.164}/agentMessages/{messageId}`              |
| `capability`        | GET         | `/v1/phones/{E.164}/capabilities:requestCapabilityCallback` |
| `event`             | POST        | `/v1/phones/{E.164}/agentEvents`                            |
| `tester invite`     | POST        | `/v1/phones/{E.164}/testers`                                |
| `tester remove`     | DELETE      | `/v1/phones/{E.164}/testers`                                |

Base URL: `https://rcsbusinessmessaging.googleapis.com`

## Authentication

The client authenticates using a Google Cloud service account JSON key file.
The path to the key file is provided via:
- `--credentials /path/to/key.json`
- `RCS_CREDENTIALS` environment variable
- `credentials_file` field in the config file

The client uses the `google-auth` library to obtain OAuth2 access tokens
with scope `https://www.googleapis.com/auth/rcsbusinessmessaging`.

## CLI Interface

### Global Flags

| Flag                  | Env Variable      | Description                          |
|-----------------------|-------------------|--------------------------------------|
| `--agent_id ID`       | `RCS_AGENT_ID`    | RBM agent identifier                 |
| `--credentials PATH`  | `RCS_CREDENTIALS` | Path to service account key file     |
| `--config PATH`       |                   | Config file path                     |
| `--json`              |                   | Force JSON output                    |
| `--quiet`             |                   | Suppress non-error output            |
| `--timeout SECS`      | `RCS_TIMEOUT`     | HTTP request timeout (default: 30)   |
| `--base_url URL`      | `RCS_BASE_URL`    | API base URL override                |

### Commands

```
# Text messages
rcsclient send text --to +14155551234 --message "Hello"
rcsclient send text --to +14155551234 --message "Pick one" \
    --reply "Yes" --reply "No"

# Rich cards
rcsclient send richcard --to +14155551234 --title "Order Update" \
    --description "Your order shipped" --image_url https://example.com/img.jpg

# Carousel messages
rcsclient send carousel --to +14155551234 \
    --card "Sale" "50% off everything" "https://example.com/sale.jpg" \
    --card "New Arrivals" "Check out new items"

# Media files
rcsclient send media --to +14155551234 \
    --file_url "https://example.com/photo.jpg" --content_type image/jpeg

# Suggested actions (all message types)
rcsclient send text --to +14155551234 --message "Need help?" \
    --dial "Call Support" "+18005551234" \
    --url "Visit Website" "https://example.com" \
    --share_location "Share your location" \
    --location "Our Office" 37.7749 -122.4194 "HQ" \
    --calendar "Add meeting" "Team Sync" 2025-01-15T10:00:00Z 2025-01-15T11:00:00Z

# Message management
rcsclient status --to +14155551234 --message_id MSG_ID
rcsclient revoke --to +14155551234 --message_id MSG_ID

# Capability check
rcsclient capability --to +14155551234

# Agent events
rcsclient event --to +14155551234 --type IS_TYPING
rcsclient event --to +14155551234 --type READ --message_id MSG_ID

# Tester management
rcsclient tester invite --phone +14155551234
rcsclient tester remove --phone +14155551234
```

### Exit Codes

| Code | Meaning                                    |
|------|--------------------------------------------|
| 0    | Success                                    |
| 1    | General / unknown error                    |
| 2    | Invalid arguments or configuration         |
| 3    | Authentication failure                     |
| 4    | API error (4xx from server)                |
| 5    | Network / connectivity error               |
| 6    | Timeout                                    |

## Configuration File

`~/.rcsclient.json`:
```json
{
  "agent_id": "my-rbm-agent",
  "credentials_file": "/path/to/service-account.json",
  "timeout": 30,
  "base_url": "https://rcsbusinessmessaging.googleapis.com"
}
```

## Message Types

### Text Message
Plain text with optional suggested replies and actions.

### Rich Card
A standalone card with title, description, optional image (with configurable
height: SHORT, MEDIUM, TALL), and optional suggestions. Rendered as a vertical
card with left-aligned thumbnail.

### Carousel
A horizontally scrollable sequence of 2+ rich cards. Each card has its own
title, description, optional image, and per-card suggestions. The carousel
itself can also have top-level suggestions. Card width is configurable
(SMALL, MEDIUM).

### Media Message
A standalone media file (image, video, audio, PDF) sent via URL. Supports
optional MIME type hint, thumbnail URL, and force-refresh flag.

## Suggested Actions

All message types support suggested replies and actions:

| Action Type     | CLI Flag            | Behavior                              |
|-----------------|---------------------|---------------------------------------|
| Reply           | `--reply TEXT`      | Quick reply chip                      |
| Dial            | `--dial LABEL NUM`  | Opens dialer with phone number        |
| Open URL        | `--url LABEL URL`   | Opens browser to URL                  |
| Share Location  | `--share_location`  | Prompts user to share their location  |
| View Location   | `--location`        | Opens map at lat/long                 |
| Calendar Event  | `--calendar`        | Creates calendar event                |

## Agent Events

The client can send agent events to indicate presence:

- **IS_TYPING**: Shows a typing indicator to the user. No message ID required.
- **READ**: Marks a specific message as read. Requires the message ID of
  the message being acknowledged.

Events are sent via `POST /v1/phones/{E.164}/agentEvents`.

## Tester Management

During development, phone numbers must be invited as testers before they can
receive messages from the agent. The client supports:

- **invite**: Register a phone number as a tester (`POST /testers`).
- **remove**: Remove a tester (`DELETE /testers`).

## Retry Strategy

The client automatically retries requests that fail due to transient errors:

- **Retried**: HTTP 429 (rate limit), 5xx (server errors), connection errors,
  and timeouts.
- **Not retried**: HTTP 4xx client errors (400, 404, etc.) and authentication
  errors (401, 403).
- **Max retries**: 3 (4 total attempts).
- **Backoff**: Exponential — 1s, 2s, 4s between retries.

## Message Flow

```
User
 │
 ▼
cli.py (parse args, load config)
 │
 ▼
models.py (build message object)
 │
 ▼
client.py (authenticate, send request, retry on failure)
 │
 ▼
output.py (format response)
 │
 ▼
stdout + exit code
```

## Error Handling

- Configuration errors (missing agent ID, bad credentials path) are caught
  early and reported with exit code 2.
- Authentication errors (invalid key, expired token) produce exit code 3.
- API errors include the HTTP status and error body in the output.
- Network errors and timeouts are retried automatically, then reported.
- All errors are written to stderr. Normal output goes to stdout.

## Testing Strategy

- **Unit tests**: Mock HTTP responses to test client.py logic (including retry
  behavior), test config loading with temp files, test model serialization
  for all message and action types.
- **No integration tests in CI**: Real API calls require credentials and a
  registered agent. Integration testing is manual.

## Dependencies

- `requests` >= 2.28 - HTTP client
- `google-auth` >= 2.0 - OAuth2 authentication

Dev dependencies:
- `pytest` >= 7.0

## Future Considerations

- Interactive mode with readline support
- Webhook receiver companion tool for inbound messages
- Support for additional RCS API providers
