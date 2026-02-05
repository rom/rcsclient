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

            with pytest.raises(NetworkError):
                client.send_message("+14155551234", msg)

    def test_timeout_error(self, config, mock_auth):
        client = RCSClient(config)
        msg = TextMessage(text="Hello", message_id="test-msg-005")

        with patch.object(client._session, "request") as mock_req:
            mock_req.side_effect = requests.exceptions.Timeout("timed out")

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
