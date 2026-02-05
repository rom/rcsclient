"""Tests for RCS message models."""

from rcsclient.models import (
    TextMessage, RichCard, CarouselCard, Carousel, MediaMessage,
    SuggestedReply, SuggestedAction, ViewLocationAction, CreateCalendarEventAction,
)


# --- TextMessage ---

def test_text_message_payload():
    msg = TextMessage(text="Hello", message_id="test-123")
    payload = msg.to_api_payload()
    assert payload == {
        "contentMessage": {
            "text": "Hello",
        }
    }


def test_text_message_with_suggestions():
    msg = TextMessage(
        text="Pick one",
        suggestions=[
            SuggestedReply(text="Yes"),
            SuggestedReply(text="No"),
        ],
        message_id="test-456",
    )
    payload = msg.to_api_payload()
    suggestions = payload["contentMessage"]["suggestions"]
    assert len(suggestions) == 2
    assert suggestions[0]["reply"]["text"] == "Yes"
    assert suggestions[1]["reply"]["text"] == "No"


def test_text_message_generates_id():
    msg = TextMessage(text="Hello")
    assert msg.message_id.startswith("msg-")
    assert len(msg.message_id) == 20  # "msg-" + 16 hex chars


# --- RichCard ---

def test_rich_card_payload():
    card = RichCard(
        title="Order Update",
        description="Your order has shipped.",
        message_id="card-001",
    )
    payload = card.to_api_payload()
    content = payload["contentMessage"]["richCard"]["standaloneCard"]["cardContent"]
    assert content["title"] == "Order Update"
    assert content["description"] == "Your order has shipped."
    assert "media" not in content


def test_rich_card_with_image():
    card = RichCard(
        title="Photo",
        description="A nice photo",
        image_url="https://example.com/img.jpg",
        image_height="TALL",
        message_id="card-002",
    )
    payload = card.to_api_payload()
    content = payload["contentMessage"]["richCard"]["standaloneCard"]["cardContent"]
    assert content["media"]["height"] == "TALL"
    assert content["media"]["contentInfo"]["fileUrl"] == "https://example.com/img.jpg"


# --- SuggestedReply ---

def test_suggested_reply_dict():
    reply = SuggestedReply(text="Yes")
    d = reply.to_dict()
    assert d == {"reply": {"text": "Yes", "postbackData": "Yes"}}


def test_suggested_reply_custom_postback():
    reply = SuggestedReply(text="Yes", postback_data="confirm_yes")
    d = reply.to_dict()
    assert d["reply"]["postbackData"] == "confirm_yes"


# --- SuggestedAction (dial, openUrl, shareLocation) ---

def test_suggested_action_dial():
    action = SuggestedAction(text="Call us", action_type="dial", value="+14155551234")
    d = action.to_dict()
    assert d["action"]["dialAction"]["phoneNumber"] == "+14155551234"


def test_suggested_action_url():
    action = SuggestedAction(text="Visit site", action_type="openUrl", value="https://example.com")
    d = action.to_dict()
    assert d["action"]["openUrlAction"]["url"] == "https://example.com"


def test_suggested_action_share_location():
    action = SuggestedAction(text="Share location", action_type="shareLocation")
    d = action.to_dict()
    assert d["action"]["shareLocationAction"] == {}
    assert d["action"]["text"] == "Share location"
    assert d["action"]["postbackData"] == "Share location"


# --- ViewLocationAction ---

def test_view_location_action():
    action = ViewLocationAction(
        text="View on map", latitude=37.7749, longitude=-122.4194, label="San Francisco",
    )
    d = action.to_dict()
    loc = d["action"]["viewLocationAction"]
    assert loc["latitude"] == 37.7749
    assert loc["longitude"] == -122.4194
    assert loc["label"] == "San Francisco"
    assert d["action"]["text"] == "View on map"


def test_view_location_action_no_label():
    action = ViewLocationAction(text="View", latitude=0.0, longitude=0.0)
    d = action.to_dict()
    assert "label" not in d["action"]["viewLocationAction"]


# --- CreateCalendarEventAction ---

def test_create_calendar_event_action():
    action = CreateCalendarEventAction(
        text="Add to calendar",
        title="Meeting",
        start_time="2025-01-15T10:00:00Z",
        end_time="2025-01-15T11:00:00Z",
        description="Team sync",
    )
    d = action.to_dict()
    event = d["action"]["createCalendarEventAction"]
    assert event["title"] == "Meeting"
    assert event["startTime"] == "2025-01-15T10:00:00Z"
    assert event["endTime"] == "2025-01-15T11:00:00Z"
    assert event["description"] == "Team sync"


def test_create_calendar_event_no_description():
    action = CreateCalendarEventAction(
        text="Add",
        title="Event",
        start_time="2025-01-15T10:00:00Z",
        end_time="2025-01-15T11:00:00Z",
    )
    d = action.to_dict()
    assert "description" not in d["action"]["createCalendarEventAction"]


# --- CarouselCard ---

def test_carousel_card_content():
    card = CarouselCard(title="T", description="D")
    content = card.to_card_content()
    assert content["title"] == "T"
    assert content["description"] == "D"
    assert "media" not in content


def test_carousel_card_with_image():
    card = CarouselCard(
        title="A", description="A desc",
        image_url="https://img.com/a.jpg", image_height="TALL",
    )
    content = card.to_card_content()
    assert content["media"]["height"] == "TALL"
    assert content["media"]["contentInfo"]["fileUrl"] == "https://img.com/a.jpg"


def test_carousel_card_with_suggestions():
    card = CarouselCard(
        title="X", description="Y",
        suggestions=[SuggestedReply(text="Pick me")],
    )
    content = card.to_card_content()
    assert len(content["suggestions"]) == 1
    assert content["suggestions"][0]["reply"]["text"] == "Pick me"


# --- Carousel ---

def test_carousel_payload():
    cards = [
        CarouselCard(title="Card 1", description="Desc 1"),
        CarouselCard(title="Card 2", description="Desc 2"),
    ]
    carousel = Carousel(cards=cards, card_width="MEDIUM", message_id="car-001")
    payload = carousel.to_api_payload()
    carousel_card = payload["contentMessage"]["richCard"]["carouselCard"]
    assert carousel_card["cardWidth"] == "MEDIUM"
    assert len(carousel_card["cardContents"]) == 2
    assert carousel_card["cardContents"][0]["cardContent"]["title"] == "Card 1"
    assert carousel_card["cardContents"][1]["cardContent"]["title"] == "Card 2"


def test_carousel_with_images():
    cards = [
        CarouselCard(title="A", description="A desc",
                     image_url="https://img.com/a.jpg", image_height="TALL"),
        CarouselCard(title="B", description="B desc"),
    ]
    carousel = Carousel(cards=cards, message_id="car-002")
    payload = carousel.to_api_payload()
    contents = payload["contentMessage"]["richCard"]["carouselCard"]["cardContents"]
    assert "media" in contents[0]["cardContent"]
    assert contents[0]["cardContent"]["media"]["contentInfo"]["fileUrl"] == "https://img.com/a.jpg"
    assert "media" not in contents[1]["cardContent"]


def test_carousel_with_suggestions():
    cards = [
        CarouselCard(title="A", description="A"),
        CarouselCard(title="B", description="B"),
    ]
    carousel = Carousel(
        cards=cards,
        suggestions=[SuggestedReply(text="More")],
        message_id="car-003",
    )
    payload = carousel.to_api_payload()
    assert len(payload["contentMessage"]["suggestions"]) == 1


def test_carousel_generates_id():
    cards = [
        CarouselCard(title="A", description="A"),
        CarouselCard(title="B", description="B"),
    ]
    carousel = Carousel(cards=cards)
    assert carousel.message_id.startswith("msg-")


# --- MediaMessage ---

def test_media_message_payload():
    msg = MediaMessage(file_url="https://example.com/photo.jpg", message_id="media-001")
    payload = msg.to_api_payload()
    assert payload["contentMessage"]["contentInfo"]["fileUrl"] == "https://example.com/photo.jpg"
    assert "contentType" not in payload["contentMessage"]["contentInfo"]
    assert "thumbnailUrl" not in payload["contentMessage"]["contentInfo"]
    assert "forceRefresh" not in payload["contentMessage"]["contentInfo"]


def test_media_message_full():
    msg = MediaMessage(
        file_url="https://example.com/video.mp4",
        content_type="video/mp4",
        thumbnail_url="https://example.com/thumb.jpg",
        force_refresh=True,
        message_id="media-002",
    )
    payload = msg.to_api_payload()
    info = payload["contentMessage"]["contentInfo"]
    assert info["fileUrl"] == "https://example.com/video.mp4"
    assert info["contentType"] == "video/mp4"
    assert info["thumbnailUrl"] == "https://example.com/thumb.jpg"
    assert info["forceRefresh"] is True


def test_media_message_with_suggestions():
    msg = MediaMessage(
        file_url="https://example.com/doc.pdf",
        suggestions=[SuggestedReply(text="Thanks")],
        message_id="media-003",
    )
    payload = msg.to_api_payload()
    assert len(payload["contentMessage"]["suggestions"]) == 1


def test_media_message_generates_id():
    msg = MediaMessage(file_url="https://example.com/img.png")
    assert msg.message_id.startswith("msg-")
