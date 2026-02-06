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
    """A suggested action chip (dial, open URL, or share location)."""
    text: str
    action_type: str  # "dial", "openUrl", or "shareLocation"
    value: str = ""   # phone number or URL (unused for shareLocation)

    def to_dict(self) -> dict:
        action = {
            "text": self.text,
            "postbackData": self.text,
        }
        if self.action_type == "dial":
            action["dialAction"] = {"phoneNumber": self.value}
        elif self.action_type == "openUrl":
            action["openUrlAction"] = {"url": self.value}
        elif self.action_type == "shareLocation":
            action["shareLocationAction"] = {}
        return {"action": action}


@dataclass
class ViewLocationAction:
    """A suggested action that opens a map at a specific location."""
    text: str
    latitude: float
    longitude: float
    label: str = ""

    def to_dict(self) -> dict:
        location = {
            "latitude": self.latitude,
            "longitude": self.longitude,
        }
        if self.label:
            location["label"] = self.label
        return {
            "action": {
                "text": self.text,
                "postbackData": self.text,
                "viewLocationAction": location,
            }
        }


@dataclass
class CreateCalendarEventAction:
    """A suggested action that creates a calendar event."""
    text: str
    title: str
    start_time: str  # ISO 8601 format
    end_time: str    # ISO 8601 format
    description: str = ""

    def to_dict(self) -> dict:
        event = {
            "title": self.title,
            "startTime": self.start_time,
            "endTime": self.end_time,
        }
        if self.description:
            event["description"] = self.description
        return {
            "action": {
                "text": self.text,
                "postbackData": self.text,
                "createCalendarEventAction": event,
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


@dataclass
class CarouselCard:
    """A single card within a carousel."""
    title: str
    description: str
    image_url: Optional[str] = None
    image_height: str = "MEDIUM"
    suggestions: List = field(default_factory=list)

    def to_card_content(self) -> dict:
        content = {
            "title": self.title,
            "description": self.description,
        }
        if self.image_url:
            content["media"] = {
                "height": self.image_height,
                "contentInfo": {"fileUrl": self.image_url},
            }
        if self.suggestions:
            content["suggestions"] = [s.to_dict() for s in self.suggestions]
        return content


@dataclass
class Carousel:
    """A carousel message containing multiple rich cards."""
    cards: List[CarouselCard]
    card_width: str = "MEDIUM"  # SMALL, MEDIUM
    suggestions: List = field(default_factory=list)
    message_id: str = field(default_factory=_generate_message_id)

    def to_api_payload(self) -> dict:
        card_contents = [
            {"cardContent": card.to_card_content()} for card in self.cards
        ]
        payload = {
            "contentMessage": {
                "richCard": {
                    "carouselCard": {
                        "cardWidth": self.card_width,
                        "cardContents": card_contents,
                    }
                }
            }
        }
        if self.suggestions:
            payload["contentMessage"]["suggestions"] = [
                s.to_dict() for s in self.suggestions
            ]
        return payload


@dataclass
class MediaMessage:
    """A standalone media file message (image, video, PDF, etc.)."""
    file_url: str
    content_type: str = ""
    thumbnail_url: str = ""
    force_refresh: bool = False
    suggestions: List = field(default_factory=list)
    message_id: str = field(default_factory=_generate_message_id)

    def to_api_payload(self) -> dict:
        content_info = {"fileUrl": self.file_url}
        if self.content_type:
            content_info["contentType"] = self.content_type
        if self.thumbnail_url:
            content_info["thumbnailUrl"] = self.thumbnail_url
        if self.force_refresh:
            content_info["forceRefresh"] = True
        payload = {
            "contentMessage": {
                "contentInfo": content_info,
            }
        }
        if self.suggestions:
            payload["contentMessage"]["suggestions"] = [
                s.to_dict() for s in self.suggestions
            ]
        return payload
