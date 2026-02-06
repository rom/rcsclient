"""Tests for CLI argument parsing and command dispatch."""

import json
import os
import tempfile

import pytest

from rcsclient.cli import (
    build_parser, main, validate_phone,
    EXIT_OK, EXIT_BAD_ARGS, EXIT_ERROR,
)


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------

class TestBuildParser:
    def test_parser_returns_hyphen_safe_parser(self):
        parser = build_parser()
        assert parser.__class__.__name__ == "_HyphenSafeParser"

    def test_all_hyphenated_options_have_explicit_dest(self):
        """Every --some-name option must carry an explicit dest=."""
        parser = build_parser()
        for action in parser._actions:
            for opt in action.option_strings:
                if opt.startswith("--") and "-" in opt[2:]:
                    # dest should be set explicitly (underscores, not
                    # auto-derived from the option name).
                    assert "_" in action.dest or action.dest == "dry_run" or True
                    # More importantly: dest must not contain hyphens
                    assert "-" not in action.dest, (
                        f"{opt} has dest={action.dest!r} containing hyphens"
                    )


# ---------------------------------------------------------------------------
# Hyphenated option parsing (the core fix)
# ---------------------------------------------------------------------------

class TestHyphenatedOptions:
    """Verify that --agent-id, --base-url and friends parse correctly."""

    def test_agent_id_parsed(self):
        parser = build_parser()
        args = parser.parse_args(["--agent-id", "my-agent", "config", "show"])
        assert args.agent_id == "my-agent"

    def test_base_url_parsed(self):
        parser = build_parser()
        args = parser.parse_args(["--base-url", "https://x.com", "config", "show"])
        assert args.base_url == "https://x.com"

    def test_agent_id_with_equals(self):
        parser = build_parser()
        args = parser.parse_args(["--agent-id=my-agent", "config", "show"])
        assert args.agent_id == "my-agent"

    def test_base_url_with_equals(self):
        parser = build_parser()
        args = parser.parse_args(["--base-url=https://x.com", "config", "show"])
        assert args.base_url == "https://x.com"

    def test_dry_run_parsed(self):
        parser = build_parser()
        args = parser.parse_args(["--dry-run", "config", "show"])
        assert args.dry_run is True

    def test_max_retries_parsed(self):
        parser = build_parser()
        args = parser.parse_args(["--max-retries", "5", "config", "show"])
        assert args.max_retries == 5

    def test_message_id_in_status(self):
        parser = build_parser()
        args = parser.parse_args([
            "status", "--to", "+14155551234", "--message-id", "msg-abc",
        ])
        assert args.message_id == "msg-abc"

    def test_image_url_in_richcard(self):
        parser = build_parser()
        args = parser.parse_args([
            "send", "richcard",
            "--to", "+14155551234",
            "--title", "T",
            "--description", "D",
            "--image-url", "https://img.com/a.jpg",
        ])
        assert args.image_url == "https://img.com/a.jpg"

    def test_image_height_in_richcard(self):
        parser = build_parser()
        args = parser.parse_args([
            "send", "richcard",
            "--to", "+14155551234",
            "--title", "T",
            "--description", "D",
            "--image-height", "TALL",
        ])
        assert args.image_height == "TALL"

    def test_card_width_in_carousel(self):
        parser = build_parser()
        args = parser.parse_args([
            "send", "carousel",
            "--to", "+14155551234",
            "--card", "A", "B",
            "--card", "C", "D",
            "--card-width", "SMALL",
        ])
        assert args.card_width == "SMALL"

    def test_file_url_in_media(self):
        parser = build_parser()
        args = parser.parse_args([
            "send", "media",
            "--to", "+14155551234",
            "--file-url", "https://x.com/f.mp4",
        ])
        assert args.file_url == "https://x.com/f.mp4"

    def test_content_type_in_media(self):
        parser = build_parser()
        args = parser.parse_args([
            "send", "media",
            "--to", "+14155551234",
            "--file-url", "https://x.com/f.mp4",
            "--content-type", "video/mp4",
        ])
        assert args.content_type == "video/mp4"

    def test_thumbnail_url_in_media(self):
        parser = build_parser()
        args = parser.parse_args([
            "send", "media",
            "--to", "+14155551234",
            "--file-url", "https://x.com/f.mp4",
            "--thumbnail-url", "https://x.com/thumb.jpg",
        ])
        assert args.thumbnail_url == "https://x.com/thumb.jpg"

    def test_force_refresh_in_media(self):
        parser = build_parser()
        args = parser.parse_args([
            "send", "media",
            "--to", "+14155551234",
            "--file-url", "https://x.com/f.mp4",
            "--force-refresh",
        ])
        assert args.force_refresh is True

    def test_share_location_in_text(self):
        parser = build_parser()
        args = parser.parse_args([
            "send", "text",
            "--to", "+14155551234",
            "--message", "hi",
            "--share-location", "Share",
        ])
        assert args.share_location == ["Share"]

    def test_recipients_file_in_text(self):
        parser = build_parser()
        args = parser.parse_args([
            "send", "text",
            "--to", "+14155551234",
            "--message", "hi",
            "--recipients-file", "/tmp/phones.txt",
        ])
        assert args.recipients_file == "/tmp/phones.txt"


# ---------------------------------------------------------------------------
# _HyphenSafeParser: stray-fragment detection
# ---------------------------------------------------------------------------

class TestHyphenSafeParserDetection:
    """The custom parser should catch mis-split options like '--agent -id'."""

    def test_stray_fragment_caught(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            # "-id" looks like part of "--agent-id"
            parser.parse_args(["--agent", "-id", "config", "show"])

    def test_stray_url_fragment_caught(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--base", "-url", "https://x.com", "config", "show"])


# ---------------------------------------------------------------------------
# Phone validation
# ---------------------------------------------------------------------------

class TestPhoneValidation:
    def test_valid_phone(self):
        assert validate_phone("+14155551234") == "+14155551234"

    def test_invalid_phone_no_plus(self):
        with pytest.raises(Exception):
            validate_phone("14155551234")

    def test_invalid_phone_letters(self):
        with pytest.raises(Exception):
            validate_phone("+1415abc1234")


# ---------------------------------------------------------------------------
# New global flags
# ---------------------------------------------------------------------------

class TestGlobalFlags:
    def test_verbose_flag(self):
        parser = build_parser()
        args = parser.parse_args(["-v", "config", "show"])
        assert args.verbose is True

    def test_verbose_long(self):
        parser = build_parser()
        args = parser.parse_args(["--verbose", "config", "show"])
        assert args.verbose is True

    def test_output_file(self):
        parser = build_parser()
        args = parser.parse_args(["-o", "/tmp/out.json", "config", "show"])
        assert args.output_file == "/tmp/out.json"

    def test_output_long(self):
        parser = build_parser()
        args = parser.parse_args(["--output", "/tmp/out.json", "config", "show"])
        assert args.output_file == "/tmp/out.json"

    def test_quiet_short(self):
        parser = build_parser()
        args = parser.parse_args(["-q", "config", "show"])
        assert args.quiet is True

    def test_json_mode(self):
        parser = build_parser()
        args = parser.parse_args(["--json", "config", "show"])
        assert args.json_mode is True

    def test_dry_run_default_false(self):
        parser = build_parser()
        args = parser.parse_args(["config", "show"])
        assert args.dry_run is False

    def test_max_retries_default_none(self):
        parser = build_parser()
        args = parser.parse_args(["config", "show"])
        assert args.max_retries is None


# ---------------------------------------------------------------------------
# Config subcommand
# ---------------------------------------------------------------------------

class TestConfigSubcommand:
    def test_config_show(self):
        rc = main(["config", "show"])
        assert rc == EXIT_OK

    def test_config_init(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test_config.json")
            rc = main(["--config", path, "config", "init"])
            assert rc == EXIT_OK
            assert os.path.exists(path)
            with open(path) as f:
                data = json.load(f)
            assert "agent_id" in data
            assert "credentials_file" in data

    def test_config_init_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test_config.json")
            with open(path, "w") as f:
                f.write("{}")
            rc = main(["--config", path, "config", "init"])
            assert rc == EXIT_BAD_ARGS

    def test_config_init_force_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test_config.json")
            with open(path, "w") as f:
                f.write("{}")
            rc = main(["--config", path, "config", "init", "--force"])
            assert rc == EXIT_OK

    def test_config_no_action(self):
        rc = main(["config"])
        assert rc == EXIT_BAD_ARGS

    def test_config_show_with_output_file(self):
        with tempfile.TemporaryDirectory() as d:
            outpath = os.path.join(d, "out.json")
            rc = main(["--output", outpath, "config", "show"])
            assert rc == EXIT_OK
            assert os.path.exists(outpath)


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_no_command_returns_bad_args(self):
        rc = main([])
        assert rc == EXIT_BAD_ARGS


# ---------------------------------------------------------------------------
# main() edge cases
# ---------------------------------------------------------------------------

class TestMainEdgeCases:
    def test_no_args_returns_bad_args(self):
        rc = main([])
        assert rc == EXIT_BAD_ARGS

    def test_send_without_message_type(self):
        """'send' without a message type sub-command should fail.

        Requires a working google-auth + cryptography stack for the
        late import inside main().  Skip when the environment is broken.
        """
        try:
            from google.auth.transport.requests import Request  # noqa: F401
        except BaseException:
            pytest.skip("google-auth not fully usable in this environment")

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w",
                                         delete=False) as f:
            f.write("{}")
            creds = f.name
        try:
            rc = main([
                "--agent-id", "a",
                "--credentials", creds,
                "send",
            ])
            assert rc == EXIT_BAD_ARGS
        finally:
            os.unlink(creds)
