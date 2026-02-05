"""RCS Business Messaging API client."""

import time
from typing import Optional

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from .config import Config

RBM_SCOPE = "https://www.googleapis.com/auth/rcsbusinessmessaging"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1  # seconds


class RCSError(Exception):
    """Base exception for API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class AuthenticationError(RCSError):
    """Raised when authentication fails."""
    pass


class APIError(RCSError):
    """Raised when the API returns a 4xx/5xx response."""
    pass


class NetworkError(RCSError):
    """Raised on connectivity or timeout failures."""
    pass


class RCSClient:
    """Client for the Google RCS Business Messaging API."""

    def __init__(self, config: Config):
        self.config = config
        self._credentials = None
        self._session = requests.Session()

    def _get_credentials(self) -> service_account.Credentials:
        if self._credentials is None or not self._credentials.valid:
            try:
                self._credentials = service_account.Credentials.from_service_account_file(
                    self.config.credentials_file,
                    scopes=[RBM_SCOPE],
                )
                self._credentials.refresh(Request())
            except Exception as e:
                raise AuthenticationError(f"authentication failed: {e}")
        return self._credentials

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}{path}"

    def _headers(self) -> dict:
        creds = self._get_credentials()
        return {
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        url = self._url(path)
        last_exception = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._session.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=body,
                    timeout=self.config.timeout,
                )
            except requests.exceptions.Timeout:
                last_exception = NetworkError("request timed out", status_code=None)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                    continue
                raise last_exception
            except requests.exceptions.ConnectionError as e:
                last_exception = NetworkError(f"connection failed: {e}", status_code=None)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                    continue
                raise last_exception

            if resp.status_code in (401, 403):
                raise AuthenticationError(
                    f"authentication error ({resp.status_code})",
                    status_code=resp.status_code,
                    body=resp.text,
                )

            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
                    continue
                raise APIError(
                    f"API error ({resp.status_code})",
                    status_code=resp.status_code,
                    body=resp.text,
                )

            if resp.status_code >= 400:
                raise APIError(
                    f"API error ({resp.status_code})",
                    status_code=resp.status_code,
                    body=resp.text,
                )

            if resp.status_code == 204 or not resp.text:
                return {}
            return resp.json()

        if last_exception:
            raise last_exception
        return {}

    def _phone_path(self, phone: str) -> str:
        return f"/v1/phones/{phone}"

    def send_message(self, phone: str, message) -> dict:
        """Send a message (text, rich card, carousel, or media).

        Args:
            phone: Recipient phone number in E.164 format (e.g. +14155551234).
            message: A message instance with to_api_payload() and message_id.

        Returns:
            API response dict containing the message resource.
        """
        path = f"{self._phone_path(phone)}/agentMessages"
        payload = message.to_api_payload()
        payload["messageId"] = message.message_id
        return self._request("POST", path, payload)

    def get_message_status(self, phone: str, message_id: str) -> dict:
        """Get delivery status of a previously sent message.

        Args:
            phone: Recipient phone number in E.164 format.
            message_id: The message ID returned when the message was sent.

        Returns:
            API response dict containing message status.
        """
        path = f"{self._phone_path(phone)}/agentMessages/{message_id}"
        return self._request("GET", path)

    def revoke_message(self, phone: str, message_id: str) -> dict:
        """Revoke (delete) a previously sent message.

        Args:
            phone: Recipient phone number in E.164 format.
            message_id: The message ID to revoke.

        Returns:
            Empty dict on success.
        """
        path = f"{self._phone_path(phone)}/agentMessages/{message_id}"
        return self._request("DELETE", path)

    def check_capability(self, phone: str) -> dict:
        """Check if a phone number is RCS-capable.

        Args:
            phone: Phone number in E.164 format.

        Returns:
            API response dict with capability information.
        """
        path = f"{self._phone_path(phone)}/capabilities:requestCapabilityCallback"
        return self._request("GET", path)

    def send_event(self, phone: str, event_type: str, message_id: str = "") -> dict:
        """Send an agent event (typing indicator or read receipt).

        Args:
            phone: Recipient phone number in E.164 format.
            event_type: "IS_TYPING" or "READ".
            message_id: Required for READ events — the message being marked read.

        Returns:
            API response dict (usually empty).
        """
        path = f"{self._phone_path(phone)}/agentEvents"
        payload = {
            "eventType": event_type,
        }
        if message_id:
            payload["messageId"] = message_id
        return self._request("POST", path, payload)

    def invite_tester(self, phone: str) -> dict:
        """Invite a phone number as a tester for the agent.

        Args:
            phone: Phone number in E.164 format.

        Returns:
            API response dict with tester resource.
        """
        path = f"{self._phone_path(phone)}/testers"
        return self._request("POST", path, {})

    def remove_tester(self, phone: str) -> dict:
        """Remove a phone number from the agent's testers.

        Args:
            phone: Phone number in E.164 format.

        Returns:
            Empty dict on success.
        """
        path = f"{self._phone_path(phone)}/testers"
        return self._request("DELETE", path)
