"""Data models for RCS messages."""

from dataclasses import dataclass, field
from typing import List, Optional
import uuid


def _generate_message_id() -> str:
    return f"msg-{uuid.uuid4().hex[:16]}"


@dataclass
class SuggestedReply:
    """A suggested reply chip shown below the message."""
    text: str
    postback_data: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "reply": {
                "text": self.text,
                "postbackData": self.postback_data or self.text,
            }
        }


@dataclass
class SuggestedAction:
    """A suggested action chip (dial or open URL)."""
    text: str
    action_type: str  # "dial" or "openUrl"
    value: str  # phone number or URL

    def to_dict(self) -> dict:
        if self.action_type == "dial":
            return {
                "action": {
                    "text": self.text,
                    "postbackData": self.text,
                    "dialAction": {"phoneNumber": self.value},
                }
            }
        return {
            "action": {
                "text": self.text,
                "postbackData": self.text,
                "openUrlAction": {"url": self.value},
            }
        }


@dataclass
class TextMessage:
    """A plain text RCS message."""
    text: str
    suggestions: List = field(default_factory=list)
    message_id: str = field(default_factory=_generate_message_id)

    def to_api_payload(self) -> dict:
        payload = {
            "contentMessage": {
                "text": self.text,
            }
        }
        if self.suggestions:
            payload["contentMessage"]["suggestions"] = [
                s.to_dict() for s in self.suggestions
            ]
        return payload


@dataclass
class RichCard:
    """A standalone rich card message."""
    title: str
    description: str
    image_url: Optional[str] = None
    image_height: str = "MEDIUM"  # SHORT, MEDIUM, TALL
    suggestions: List = field(default_factory=list)
    message_id: str = field(default_factory=_generate_message_id)

    def to_api_payload(self) -> dict:
        card_content = {
            "title": self.title,
            "description": self.description,
        }
        if self.image_url:
            card_content["media"] = {
                "height": self.image_height,
                "contentInfo": {
                    "fileUrl": self.image_url,
                },
            }
        if self.suggestions:
            card_content["suggestions"] = [
                s.to_dict() for s in self.suggestions
            ]
        return {
            "contentMessage": {
                "richCard": {
                    "standaloneCard": {
                        "thumbnailImageAlignment": "LEFT",
                        "cardOrientation": "VERTICAL",
                        "cardContent": card_content,
                    }
                }
            }
        }
