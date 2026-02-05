"""Tests for the RCS API client."""

import json
from unittest.mock import patch, MagicMock

import pytest
import requests

from rcsclient.client import RCSClient, AuthenticationError, APIError, NetworkError
from rcsclient.config import Config
from rcsclient.models import TextMessage, RichCard


@pytest.fixture
def config(tmp_path):
    creds = tmp_path / "creds.json"
    creds.write_text(json.dumps({
        "type": "service_account",
        "project_id": "test",
        "private_key_id": "key1",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIBogIBAAJBALRiMLAHudeSA/x3hB2f+2NRkJLA\n-----END RSA PRIVATE KEY-----\n",
        "client_email": "test@test.iam.gserviceaccount.com",
        "client_id": "123",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }))
    return Config(
        agent_id="test-agent",
        credentials_file=str(creds),
        base_url="https://rcsbusinessmessaging.googleapis.com",
        timeout=10,
    )


@pytest.fixture
def mock_auth():
    """Mock the authentication layer."""
    with patch.object(RCSClient, "_get_credentials") as mock_creds:
        cred = MagicMock()
        cred.token = "fake-token"
        mock_creds.return_value = cred
        yield mock_creds


class TestSendMessage:
    def test_send_text(self, config, mock_auth):
        client = RCSClient(config)
        msg = TextMessage(text="Hello", message_id="test-msg-001")

        with patch.object(client._session, "request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"name": "phones/+1234/agentMessages/test-msg-001"}'
            mock_resp.json.return_value = {
                "name": "phones/+1234/agentMessages/test-msg-001"
            }
            mock_req.return_value = mock_resp

            result = client.send_message("+14155551234", msg)

            assert result["name"] == "phones/+1234/agentMessages/test-msg-001"
            mock_req.assert_called_once()
            call_args = mock_req.call_args
            assert call_args[0][0] == "POST"
            assert "/agentMessages" in call_args[0][1]

    def test_send_richcard(self, config, mock_auth):
        client = RCSClient(config)
        card = RichCard(
            title="Test",
            description="A test card",
            message_id="card-001",
        )

        with patch.object(client._session, "request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"name": "phones/+1234/agentMessages/card-001"}'
            mock_resp.json.return_value = {
                "name": "phones/+1234/agentMessages/card-001"
            }
            mock_req.return_value = mock_resp

            result = client.send_message("+14155551234", card)
            assert "name" in result

    def test_auth_error(self, config, mock_auth):
        client = RCSClient(config)
        msg = TextMessage(text="Hello", message_id="test-msg-002")

        with patch.object(client._session, "request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.text = "Unauthorized"
            mock_req.return_value = mock_resp

            with pytest.raises(AuthenticationError):
                client.send_message("+14155551234", msg)

    def test_api_error(self, config, mock_auth):
        client = RCSClient(config)
        msg = TextMessage(text="Hello", message_id="test-msg-003")

        with patch.object(client._session, "request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 400
            mock_resp.text = '{"error": "bad request"}'
            mock_req.return_value = mock_resp

            with pytest.raises(APIError):
                client.send_message("+14155551234", msg)

    def test_network_error(self, config, mock_auth):
        client = RCSClient(config)
        msg = TextMessage(text="Hello", message_id="test-msg-004")

        with patch.object(client._session, "request") as mock_req:
            mock_req.side_effect = requests.exceptions.ConnectionError("refused")

            with patch("rcsclient.client.time.sleep"):
                with pytest.raises(NetworkError):
                    client.send_message("+14155551234", msg)

    def test_timeout_error(self, config, mock_auth):
        client = RCSClient(config)
        msg = TextMessage(text="Hello", message_id="test-msg-005")

        with patch.object(client._session, "request") as mock_req:
            mock_req.side_effect = requests.exceptions.Timeout("timed out")

            with patch("rcsclient.client.time.sleep"):
                with pytest.raises(NetworkError, match="timed out"):
                    client.send_message("+14155551234", msg)


class TestGetStatus:
    def test_get_status(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"status": "DELIVERED"}'
            mock_resp.json.return_value = {"status": "DELIVERED"}
            mock_req.return_value = mock_resp

            result = client.get_message_status("+14155551234", "msg-001")
            assert result["status"] == "DELIVERED"


class TestRevoke:
    def test_revoke(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 204
            mock_resp.text = ""
            mock_req.return_value = mock_resp

            result = client.revoke_message("+14155551234", "msg-001")
            assert result == {}


class TestSendEvent:
    def test_send_typing(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{}'
            mock_resp.json.return_value = {}
            mock_req.return_value = mock_resp

            result = client.send_event("+14155551234", "IS_TYPING")
            assert result == {}
            call_args = mock_req.call_args
            assert call_args[0][0] == "POST"
            assert "/agentEvents" in call_args[0][1]
            body = call_args[1]["json"]
            assert body["eventType"] == "IS_TYPING"
            assert "messageId" not in body

    def test_send_read_receipt(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{}'
            mock_resp.json.return_value = {}
            mock_req.return_value = mock_resp

            result = client.send_event("+14155551234", "READ", "msg-001")
            call_args = mock_req.call_args
            body = call_args[1]["json"]
            assert body["eventType"] == "READ"
            assert body["messageId"] == "msg-001"


class TestTester:
    def test_invite_tester(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"name": "phones/+14155551234/testers"}'
            mock_resp.json.return_value = {"name": "phones/+14155551234/testers"}
            mock_req.return_value = mock_resp

            result = client.invite_tester("+14155551234")
            assert "name" in result
            call_args = mock_req.call_args
            assert call_args[0][0] == "POST"
            assert "/testers" in call_args[0][1]

    def test_remove_tester(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = 204
            mock_resp.text = ""
            mock_req.return_value = mock_resp

            result = client.remove_tester("+14155551234")
            assert result == {}
            call_args = mock_req.call_args
            assert call_args[0][0] == "DELETE"
            assert "/testers" in call_args[0][1]


class TestRetry:
    def test_retry_on_server_error(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            fail_resp = MagicMock()
            fail_resp.status_code = 500
            fail_resp.text = "Internal Server Error"

            ok_resp = MagicMock()
            ok_resp.status_code = 200
            ok_resp.text = '{"status": "ok"}'
            ok_resp.json.return_value = {"status": "ok"}

            mock_req.side_effect = [fail_resp, ok_resp]

            with patch("rcsclient.client.time.sleep"):
                result = client.check_capability("+14155551234")
            assert result["status"] == "ok"
            assert mock_req.call_count == 2

    def test_retry_on_rate_limit(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            rate_resp = MagicMock()
            rate_resp.status_code = 429
            rate_resp.text = "Too Many Requests"

            ok_resp = MagicMock()
            ok_resp.status_code = 200
            ok_resp.text = '{"ok": true}'
            ok_resp.json.return_value = {"ok": True}

            mock_req.side_effect = [rate_resp, ok_resp]

            with patch("rcsclient.client.time.sleep"):
                result = client.check_capability("+14155551234")
            assert mock_req.call_count == 2

    def test_retry_on_connection_error(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            ok_resp = MagicMock()
            ok_resp.status_code = 200
            ok_resp.text = '{"ok": true}'
            ok_resp.json.return_value = {"ok": True}

            mock_req.side_effect = [
                requests.exceptions.ConnectionError("refused"),
                ok_resp,
            ]

            with patch("rcsclient.client.time.sleep"):
                result = client.check_capability("+14155551234")
            assert mock_req.call_count == 2

    def test_retry_on_timeout(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            ok_resp = MagicMock()
            ok_resp.status_code = 200
            ok_resp.text = '{"ok": true}'
            ok_resp.json.return_value = {"ok": True}

            mock_req.side_effect = [
                requests.exceptions.Timeout("timed out"),
                ok_resp,
            ]

            with patch("rcsclient.client.time.sleep"):
                result = client.check_capability("+14155551234")
            assert mock_req.call_count == 2

    def test_exhausted_retries_raises(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            fail_resp = MagicMock()
            fail_resp.status_code = 500
            fail_resp.text = "Internal Server Error"

            mock_req.return_value = fail_resp

            with patch("rcsclient.client.time.sleep"):
                with pytest.raises(APIError):
                    client.check_capability("+14155551234")
            assert mock_req.call_count == 4  # initial + 3 retries

    def test_no_retry_on_client_error(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            fail_resp = MagicMock()
            fail_resp.status_code = 400
            fail_resp.text = "Bad Request"

            mock_req.return_value = fail_resp

            with pytest.raises(APIError):
                client.check_capability("+14155551234")
            assert mock_req.call_count == 1

    def test_no_retry_on_auth_error(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            fail_resp = MagicMock()
            fail_resp.status_code = 401
            fail_resp.text = "Unauthorized"

            mock_req.return_value = fail_resp

            with pytest.raises(AuthenticationError):
                client.check_capability("+14155551234")
            assert mock_req.call_count == 1

    def test_retry_backoff_timing(self, config, mock_auth):
        client = RCSClient(config)

        with patch.object(client._session, "request") as mock_req:
            fail_resp = MagicMock()
            fail_resp.status_code = 500
            fail_resp.text = "Error"

            ok_resp = MagicMock()
            ok_resp.status_code = 200
            ok_resp.text = '{"ok": true}'
            ok_resp.json.return_value = {"ok": True}

            mock_req.side_effect = [fail_resp, fail_resp, ok_resp]

            with patch("rcsclient.client.time.sleep") as mock_sleep:
                client.check_capability("+14155551234")
            # First retry: 1 * 2^0 = 1s, Second retry: 1 * 2^1 = 2s
            assert mock_sleep.call_count == 2
            assert mock_sleep.call_args_list[0][0][0] == 1
            assert mock_sleep.call_args_list[1][0][0] == 2
