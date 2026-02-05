"""Tests for RCS message models."""

from rcsclient.models import TextMessage, RichCard, SuggestedReply, SuggestedAction


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


def test_suggested_reply_dict():
    reply = SuggestedReply(text="Yes")
    d = reply.to_dict()
    assert d == {"reply": {"text": "Yes", "postbackData": "Yes"}}


def test_suggested_reply_custom_postback():
    reply = SuggestedReply(text="Yes", postback_data="confirm_yes")
    d = reply.to_dict()
    assert d["reply"]["postbackData"] == "confirm_yes"


def test_suggested_action_dial():
    action = SuggestedAction(text="Call us", action_type="dial", value="+14155551234")
    d = action.to_dict()
    assert d["action"]["dialAction"]["phoneNumber"] == "+14155551234"


def test_suggested_action_url():
    action = SuggestedAction(text="Visit site", action_type="openUrl", value="https://example.com")
    d = action.to_dict()
    assert d["action"]["openUrlAction"]["url"] == "https://example.com"
