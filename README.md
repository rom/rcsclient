# rcsclient

A command-line client for sending RCS (Rich Communication Services) messages
via the Google RCS Business Messaging API. Designed for use by people at a
terminal or by scripts and programs that need to send messages.

## Features

- Send plain text RCS messages
- Send rich cards with titles, descriptions, and images
- Attach suggested replies and actions (dial, open URL) to messages
- Check message delivery status
- Revoke previously sent messages
- Check RCS capability of phone numbers
- Configuration via file, environment variables, or CLI flags
- JSON output mode for scripting
- Deterministic exit codes for programmatic use

## Requirements

- Python 3.8+
- A Google RCS Business Messaging agent and service account key file

## Installation

```bash
pip install requests google-auth
```

Clone the repository and run directly:

```bash
git clone <repo-url> rcsclient
cd rcsclient
python -m rcsclient --help
```

Or install as a package:

```bash
pip install -e .
rcsclient --help
```

## Configuration

The client reads configuration from three sources (highest priority first):

1. **CLI flags** (`--agent-id`, `--credentials`, etc.)
2. **Environment variables** (`RCS_AGENT_ID`, `RCS_CREDENTIALS`, `RCS_TIMEOUT`, `RCS_BASE_URL`)
3. **Config file** (`~/.rcsclient.json`)

### Config file example

Create `~/.rcsclient.json`:

```json
{
  "agent_id": "my-rbm-agent",
  "credentials_file": "/path/to/service-account.json",
  "timeout": 30
}
```

### Environment variables

```bash
export RCS_AGENT_ID="my-rbm-agent"
export RCS_CREDENTIALS="/path/to/service-account.json"
```

## Usage

### Send a text message

```bash
rcsclient send text --to +14155551234 --message "Hello from RCS"
```

### Send a text message with suggested replies

```bash
rcsclient send text --to +14155551234 \
  --message "Would you like to continue?" \
  --reply "Yes" --reply "No"
```

### Send a text message with action buttons

```bash
rcsclient send text --to +14155551234 \
  --message "Need help?" \
  --dial "Call Support" "+18005551234" \
  --url "Visit Website" "https://example.com"
```

### Send a rich card

```bash
rcsclient send richcard --to +14155551234 \
  --title "Order Shipped" \
  --description "Your order #1234 has been shipped and is on the way." \
  --image-url "https://example.com/tracking.png" \
  --image-height TALL
```

### Check message delivery status

```bash
rcsclient status --to +14155551234 --message-id msg-abc123
```

### Revoke a sent message

```bash
rcsclient revoke --to +14155551234 --message-id msg-abc123
```

### Check RCS capability

```bash
rcsclient capability --to +14155551234
```

### JSON output for scripting

```bash
rcsclient --json send text --to +14155551234 --message "Hello"
```

When stdout is not a terminal (e.g., piped to another program), JSON output is
used automatically.

### Quiet mode

```bash
rcsclient --quiet send text --to +14155551234 --message "Hello"
```

Suppresses all non-error output. The exit code still indicates success or
failure.

## Exit Codes

| Code | Meaning                       |
|------|-------------------------------|
| 0    | Success                       |
| 1    | General error                 |
| 2    | Invalid arguments or config   |
| 3    | Authentication failure        |
| 4    | API error (4xx from server)   |
| 5    | Network / connectivity error  |
| 6    | Timeout                       |

## Project Structure

```
rcsclient/
├── rcsclient/
│   ├── __init__.py      # Package version
│   ├── __main__.py      # python -m rcsclient entry point
│   ├── cli.py           # Argument parsing and command dispatch
│   ├── client.py        # RCS Business Messaging API client
│   ├── config.py        # Configuration loading
│   ├── models.py        # Message data models
│   └── output.py        # Output formatting
├── tests/
│   ├── test_client.py   # API client tests (mocked HTTP)
│   ├── test_config.py   # Configuration loading tests
│   └── test_models.py   # Message model tests
├── DESIGN.md            # Architecture and design decisions
├── requirements.txt     # Runtime dependencies
└── setup.py             # Package installation
```

## Running Tests

```bash
pip install pytest responses
python -m pytest tests/ -v
```

## Design

See [DESIGN.md](DESIGN.md) for architecture details, API mapping, and design
decisions.
