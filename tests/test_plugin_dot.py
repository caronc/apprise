# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Disable logging for a cleaner testing output
import json
import logging
from unittest import mock
from urllib.parse import parse_qs, urlparse

from helpers import AppriseURLTester

from apprise.plugins.dot import NotifyDot


class DummyAttachment:
    def __init__(self, payload="ZmFjZQ=="):
        self._payload = payload

    def base64(self):
        return self._payload


logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "dot://",
        {
            # No API key or device ID
            "instance": None,
        },
    ),
    (
        "dot://@",
        {
            # No device ID
            "instance": None,
        },
    ),
    (
        "dot://apikey@",
        {
            # No device ID
            "instance": None,
        },
    ),
    (
        "dot://@device_id",
        {
            # No API key — loads but notify() returns False
            "instance": NotifyDot,
            "notify_response": False,
        },
    ),
    (
        "dot://apikey@device_id/",
        {
            # Default text mode
            "instance": NotifyDot,
            "privacy_url": "dot://****@device_id/?",
        },
    ),
    (
        "dot://apikey@device_id/?refresh=no",
        {
            # Disable refresh now
            "instance": NotifyDot,
        },
    ),
    (
        "dot://apikey@device_id/?signature=test_signature",
        {
            # With signature (text mode default)
            "instance": NotifyDot,
        },
    ),
    (
        "dot://apikey@device_id/?link=https://example.com",
        {
            # With link (text mode default)
            "instance": NotifyDot,
        },
    ),
    (
        "dot://apikey@device_id/?mode=text",
        {
            # Explicit text mode (same as default)
            "instance": NotifyDot,
            "privacy_url": "dot://****@device_id/?",
        },
    ),
    (
        # Backward-compat: /text/ path still parsed as text mode
        "dot://apikey@device_id/text/",
        {
            "instance": NotifyDot,
            "privacy_url": "dot://****@device_id/?",
        },
    ),
    (
        "dot://apikey@device_id/?mode=image&image=ZmFrZUJhc2U2NA==",
        {
            # Explicit image mode via ?mode= query param
            "instance": NotifyDot,
            "privacy_url": "dot://****@device_id/?",
        },
    ),
    (
        "dot://apikey@device_id/?image=ZmFrZUJhc2U2NA==",
        {
            # image= without mode= stays in default text mode (dual-send)
            "instance": NotifyDot,
            "privacy_url": "dot://****@device_id/?",
        },
    ),
    (
        "dot://apikey@device_id/image/?link=https://example.com"
        "&border=1&dither_type=ORDERED&dither_kernel=ATKINSON",
        {
            # Backward-compat /image/ path; no image payload -> fail
            "instance": NotifyDot,
            "notify_response": False,
            "attach_response": True,
        },
    ),
    (
        "dot://apikey@device_id/image/?image=ZmFrZUJhc2U2NA=="
        "&link=https://example.com&border=1"
        "&dither_type=DIFFUSION&dither_kernel=FLOYD_STEINBERG",
        {
            # Backward-compat /image/ path with image data
            "instance": NotifyDot,
            "privacy_url": "dot://****@device_id/?",
        },
    ),
    (
        "dot://apikey@device_id/",
        {
            "instance": NotifyDot,
            # Throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "dot://apikey@device_id/",
        {
            "instance": NotifyDot,
            # Throws a series of i/o exceptions
            "test_requests_exceptions": True,
        },
    ),
    (
        "dot://apikey@device_id/unknown/",
        {
            # Unknown path token defaults to text mode
            "instance": NotifyDot,
            "privacy_url": "dot://****@device_id/?",
        },
    ),
)


def test_plugin_dot_urls():
    """NotifyDot() Apprise URLs."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


# ---------------------------------------------------------------------------
# Mode and initialization
# ---------------------------------------------------------------------------


def test_notify_dot_default_mode():
    """Default mode is text."""
    dot = NotifyDot(apikey="key", device_id="dev")
    assert dot.mode == "text"


def test_notify_dot_invalid_mode():
    """Invalid mode falls back to text."""
    dot = NotifyDot(apikey="token", device_id="device", mode="invalid_mode")
    assert dot.mode == "text"

    dot = NotifyDot(apikey="token", device_id="device", mode=123)
    assert dot.mode == "text"


def test_notify_dot_explicit_text_mode():
    """Explicit text mode is honoured."""
    dot = NotifyDot(apikey="key", device_id="dev", mode="text")
    assert dot.mode == "text"


def test_notify_dot_explicit_image_mode():
    """Explicit image mode is honoured."""
    dot = NotifyDot(apikey="key", device_id="dev", mode="image")
    assert dot.mode == "image"


def test_notify_dot_image_data_kept_in_text_mode():
    """image_data is preserved in text mode for dual-send."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="text",
        image_data="somebase64",
    )
    assert dot.image_data == "somebase64"


# ---------------------------------------------------------------------------
# Text mode (default) — send logic
# ---------------------------------------------------------------------------


def test_notify_dot_auto_text_only():
    """Default text mode sends text only when no image is available."""
    dot = NotifyDot(apikey="token", device_id="device")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="hello", title="world")

    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    assert "/text" in url
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "hello"
    assert payload["title"] == "world"


def test_notify_dot_auto_image_only_from_image_data():
    """Auto mode sends image only when image_data set but no body/title."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        image_data="base64img",
    )
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="", title="")

    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    assert "/image" in url
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["image"] == "base64img"


def test_notify_dot_auto_dual_send_text_then_image():
    """Auto mode sends text first, then image, when both are present."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        image_data="base64img",
    )
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="hello", title="world")

    assert mock_post.call_count == 2
    first_url = mock_post.call_args_list[0][0][0]
    second_url = mock_post.call_args_list[1][0][0]
    assert "/text" in first_url
    assert "/image" in second_url


def test_notify_dot_auto_dual_send_with_attachment():
    """Auto mode sends text first then attachment as image."""
    dot = NotifyDot(apikey="token", device_id="device")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(
            body="hello",
            title="world",
            attach=[DummyAttachment("imgdata")],
        )

    assert mock_post.call_count == 2
    first_url = mock_post.call_args_list[0][0][0]
    second_url = mock_post.call_args_list[1][0][0]
    assert "/text" in first_url
    assert "/image" in second_url
    payload = json.loads(mock_post.call_args_list[1][1]["data"])
    assert payload["image"] == "imgdata"


def test_notify_dot_auto_image_from_attachment_no_body():
    """Auto mode sends image-only when attachment given but no body."""
    dot = NotifyDot(apikey="token", device_id="device")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="", title="", attach=[DummyAttachment("imgdata")])

    assert mock_post.call_count == 1
    assert "/image" in mock_post.call_args[0][0]


def test_notify_dot_auto_nothing_to_send():
    """Auto mode returns False when nothing is available to send."""
    dot = NotifyDot(apikey="token", device_id="device")
    assert dot.send(body="", title="") is False


def test_notify_dot_auto_partial_failure():
    """Auto mode returns False when text succeeds but image fails."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        image_data="base64img",
    )

    def side_effect(*args, **kwargs):
        resp = mock.Mock()
        url = args[0]
        resp.status_code = 200 if "/text" in url else 500
        resp.content = b""
        return resp

    with mock.patch("requests.post", side_effect=side_effect):
        assert dot.send(body="hello", title="") is False


def test_notify_dot_auto_icon_passthrough():
    """Auto mode passes self.icon to the text API call."""
    dot = NotifyDot(apikey="token", device_id="device", icon="aW1h")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="hello", title="")

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["icon"] == "aW1h"


# ---------------------------------------------------------------------------
# Explicit image mode
# ---------------------------------------------------------------------------


def test_notify_dot_image_mode_requires_image():
    """Explicit image mode fails without image data."""
    dot = NotifyDot(apikey="token", device_id="device", mode="image")
    assert dot.notify(title="x", body="y") is False


def test_notify_dot_image_mode_with_attachment():
    """Image mode uses first attachment when no image_data provided."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        link="https://example.com",
        border=1,
        dither_type="ORDERED",
        dither_kernel="ATKINSON",
    )
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(
            body="payload",
            title="title",
            attach=[DummyAttachment("YmFzZTY0")],
        )

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["image"] == "YmFzZTY0"
    assert "deviceId" not in payload


def test_notify_dot_image_mode_with_existing_image_data():
    """Image mode ignores attachment when image_data is already set."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="existing_image_data",
    )
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(
            body="test",
            title="test",
            attach=[DummyAttachment("attachment_data")],
        )

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["image"] == "existing_image_data"


def test_notify_dot_image_mode_multiple_attachments():
    """Image mode uses only the first attachment."""
    dot = NotifyDot(apikey="token", device_id="device", mode="image")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(
            body="test",
            title="test",
            attach=[
                DummyAttachment("first_attachment"),
                DummyAttachment("second_attachment"),
            ],
        )

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["image"] == "first_attachment"


def test_notify_dot_image_mode_with_failed_attachment():
    """Image mode warns and fails when attachment.base64() raises."""

    class FailedAttachment:
        def base64(self):
            raise Exception("Conversion failed")

    dot = NotifyDot(apikey="token", device_id="device", mode="image")
    assert (
        dot.notify(title="test", body="test", attach=[FailedAttachment()])
        is False
    )


def test_notify_dot_image_mode_attachment_none():
    """Image mode fails when attachment is None."""
    dot = NotifyDot(apikey="token", device_id="device", mode="image")
    assert dot.send(body="test", title="test", attach=[None]) is False


def test_notify_dot_image_mode_attachment_falsy():
    """Image mode fails when attachment is falsy."""

    class FalsyAttachment:
        def __bool__(self):
            return False

        def base64(self):
            return "should_not_be_called"

    dot = NotifyDot(apikey="token", device_id="device", mode="image")
    assert (
        dot.send(body="test", title="test", attach=[FalsyAttachment()])
        is False
    )


def test_notify_dot_image_mode_no_border():
    """Image mode omits border from payload when None."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="base64img",
    )
    dot.border = None
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="test", title="test")

    payload = json.loads(mock_post.call_args[1]["data"])
    assert "border" not in payload


def test_notify_dot_image_mode_no_dither():
    """Image mode omits dither fields from payload when None."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="base64img",
    )
    dot.dither_type = None
    dot.dither_kernel = None
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="test", title="test")

    payload = json.loads(mock_post.call_args[1]["data"])
    assert "ditherType" not in payload
    assert "ditherKernel" not in payload


def test_notify_dot_image_mode_title_body_ignored():
    """Image mode warns when title or body are provided."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="base64img",
    )
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(title="ignored", body="also ignored")

    payload = json.loads(mock_post.call_args[1]["data"])
    assert "title" not in payload
    assert "message" not in payload


# ---------------------------------------------------------------------------
# Explicit text mode
# ---------------------------------------------------------------------------


def test_notify_dot_text_mode_with_existing_icon():
    """Text mode: icon= param with Text API; attachment goes to Image API."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="text",
        signature="footer",
        icon="aW5jb24=",
    )
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(
            title="hello",
            body="world",
            attach=[DummyAttachment("attachment_image")],
        )

    # Two POSTs: text API first, image API second
    assert mock_post.call_count == 2
    text_payload = json.loads(mock_post.call_args_list[0][1]["data"])
    image_payload = json.loads(mock_post.call_args_list[1][1]["data"])
    assert text_payload["message"] == "world"
    assert text_payload["icon"] == "aW5jb24="
    assert "image" not in text_payload
    assert image_payload["image"] == "attachment_image"


def test_notify_dot_text_mode_uses_attachment_as_image():
    """Text mode sends attachment to Image API when no icon= is set."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="text",
        signature="footer",
    )
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(
            title="hello",
            body="world",
            attach=[DummyAttachment("attachment_image_data")],
        )

    assert mock_post.call_count == 2
    text_payload = json.loads(mock_post.call_args_list[0][1]["data"])
    image_payload = json.loads(mock_post.call_args_list[1][1]["data"])
    assert text_payload["message"] == "world"
    assert "icon" not in text_payload
    assert image_payload["image"] == "attachment_image_data"


def test_notify_dot_text_mode_multiple_attachments_warning():
    """Text mode warns when multiple attachments are provided."""
    dot = NotifyDot(apikey="token", device_id="device", mode="text")
    resp = mock.Mock()
    resp.status_code = 200

    with (
        mock.patch("requests.post", return_value=resp) as mock_post,
        mock.patch.object(dot.logger, "warning") as mock_warning,
    ):
        assert dot.send(
            title="hello",
            body="world",
            attach=[
                DummyAttachment("first"),
                DummyAttachment("second"),
            ],
        )
        mock_warning.assert_called_once()
        assert "Multiple attachments" in str(mock_warning.call_args)

    # First attachment sent as image to Image API (second POST)
    assert mock_post.call_count == 2
    image_payload = json.loads(mock_post.call_args_list[1][1]["data"])
    assert image_payload["image"] == "first"


def test_notify_dot_text_mode_no_optional_fields():
    """Text mode omits optional fields when not set."""
    dot = NotifyDot(apikey="token", device_id="device", mode="text")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="test body", title="test title")

    payload = json.loads(mock_post.call_args[1]["data"])
    assert "signature" not in payload
    assert "icon" not in payload
    assert payload.get("link") is None or "link" not in payload


def test_notify_dot_text_mode_with_title_and_body():
    """Text mode sends title and body correctly."""
    dot = NotifyDot(apikey="token", device_id="device", mode="text")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="test_body", title="test_title")

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "test_body"
    assert payload["title"] == "test_title"


def test_notify_dot_text_mode_without_title():
    """Text mode omits title from payload when empty."""
    dot = NotifyDot(apikey="token", device_id="device", mode="text")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="test message", title="")

    payload = json.loads(mock_post.call_args[1]["data"])
    assert "title" not in payload
    assert payload["message"] == "test message"


def test_notify_dot_text_mode_without_body():
    """Text mode omits message from payload when body is empty."""
    dot = NotifyDot(apikey="token", device_id="device", mode="text")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="", title="test_title")

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["title"] == "test_title"
    assert "message" not in payload


def test_notify_dot_text_mode_attachment_exception():
    """Text mode warns on attachment error; text still sends without image."""

    class ExceptionAttachment:
        def base64(self):
            raise Exception("Attachment base64 conversion fails")

    dot = NotifyDot(apikey="token", device_id="device", mode="text")
    resp = mock.Mock()
    resp.status_code = 200

    with (
        mock.patch("requests.post", return_value=resp) as mock_post,
        mock.patch.object(dot.logger, "warning") as mock_warning,
    ):
        assert dot.send(
            title="hello",
            body="world",
            attach=[ExceptionAttachment()],
        )
        assert mock_warning.called
        assert any(
            "Failed to process attachment" in str(c)
            for c in mock_warning.call_args_list
        )

    # Only text API called (image_data resolved to None on exception)
    assert mock_post.call_count == 1
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "world"
    assert "icon" not in payload


def test_notify_dot_text_mode_attachment_none():
    """Text mode sends only text when attachment is None."""
    dot = NotifyDot(apikey="token", device_id="device", mode="text")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(title="hello", body="world", attach=[None])

    assert mock_post.call_count == 1
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "world"
    assert "icon" not in payload


def test_notify_dot_text_mode_attachment_falsy():
    """Text mode sends only text when attachment is falsy."""

    class FalsyAttachment:
        def __bool__(self):
            return False

        def base64(self):
            return "should_not_be_called"

    dot = NotifyDot(apikey="token", device_id="device", mode="text")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(
            title="hello",
            body="world",
            attach=[FalsyAttachment()],
        )

    assert mock_post.call_count == 1
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "world"
    assert "icon" not in payload


def test_notify_dot_title_handling():
    """Text mode omits title from payload when empty."""
    dot = NotifyDot(apikey="token", device_id="device", mode="text")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="test", title="provided_title")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["title"] == "provided_title"

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send(body="test", title="")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert "title" not in payload


# ---------------------------------------------------------------------------
# URL generation
# ---------------------------------------------------------------------------


def test_notify_dot_url_generation():
    """URL generation for text (default) and image modes."""
    # text mode (default) — no mode param emitted
    text_dot = NotifyDot(
        apikey="token",
        device_id="device",
        signature="sig",
        icon="aW5jb24=",
    )
    text_url = text_dot.url()
    parsed = urlparse(text_url)
    assert parsed.path == "/"
    query = parse_qs(parsed.query)
    assert query["refresh"] == ["yes"]
    assert query["signature"] == ["sig"]
    assert "mode" not in query

    # Explicit image mode — mode=image in params
    image_dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="aW1hZ2U=",
        link="https://example.com",
        border=1,
        dither_type="ORDERED",
        dither_kernel="ATKINSON",
    )
    image_url = image_dot.url()
    image_query = parse_qs(urlparse(image_url).query)
    assert image_query["mode"] == ["image"]
    assert image_query["image"] == ["aW1hZ2U="]
    assert image_query["border"] == ["1"]


def test_notify_dot_url_generation_defaults():
    """Default text mode omits mode param; image mode includes it."""
    dot = NotifyDot(apikey="token", device_id="device")
    url = dot.url()
    assert "refresh=yes" in url
    assert "mode=" not in url

    dot_image = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="img",
        dither_type="ORDERED",
        dither_kernel="ATKINSON",
    )
    url_image = dot_image.url()
    assert "mode=image" in url_image
    assert "dither_type=ORDERED" in url_image
    assert "dither_kernel=ATKINSON" in url_image


def test_notify_dot_url_generation_defaults_no_dither():
    """Default dither values are omitted from URL."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="img",
        dither_type="DIFFUSION",
        dither_kernel="FLOYD_STEINBERG",
    )
    url = dot.url()
    assert "dither_type" not in url
    assert "dither_kernel" not in url


def test_notify_dot_url_with_border():
    """URL includes border when set."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="img",
        border=1,
    )
    assert "border=1" in dot.url()


def test_notify_dot_url_with_link():
    """URL includes link when set."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        link="https://example.com",
    )
    assert "link=" in dot.url()


def test_notify_dot_url_with_task_key():
    """URL includes task_key when set."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        task_key="url_task",
    )
    assert "task_key=url_task" in dot.url()


# ---------------------------------------------------------------------------
# parse_url
# ---------------------------------------------------------------------------


def test_notify_dot_parse_url_mode_and_image():
    """parse_url handles image mode via path and query param."""
    # Backward-compat: /image/ path selects image mode
    result = NotifyDot.parse_url(
        "dot://token@device/image/?image=Zm9vYmFy&link=https://example.com"
    )
    assert result["mode"] == "image"
    assert result["image_data"] == "Zm9vYmFy"
    assert result["link"] == "https://example.com"

    # New-style: ?mode= query param
    result2 = NotifyDot.parse_url(
        "dot://token@device/?mode=image&image=Zm9vYmFy"
    )
    assert result2["mode"] == "image"
    assert result2["image_data"] == "Zm9vYmFy"

    # image= without mode= stays as default text mode (dual-send)
    result3 = NotifyDot.parse_url("dot://token@device/?image=Zm9vYmFy")
    assert result3["mode"] == "text"
    assert result3["image_data"] == "Zm9vYmFy"

    # Invalid ?mode= falls back to text (default)
    result4 = NotifyDot.parse_url("dot://token@device/?mode=invalid")
    assert result4["mode"] == "text"

    # Unknown path token falls back to text (default)
    fallback = NotifyDot.parse_url("dot://token@device/unknown/?refresh=no")
    assert fallback["mode"] == "text"
    assert fallback["refresh_now"] is False


def test_notify_dot_parse_url_with_all_params():
    """parse_url handles all parameters."""
    result = NotifyDot.parse_url(
        "dot://apikey@device/image/?refresh=yes&signature=sig&icon=icon_b64"
        "&link=https://example.com&border=1&dither_type=ORDERED"
        "&dither_kernel=ATKINSON&image=img_b64"
    )
    assert result["mode"] == "image"
    assert result["refresh_now"] is True
    assert result["signature"] == "sig"
    assert result["icon"] == "icon_b64"
    assert result["link"] == "https://example.com"
    assert result["border"] == 1
    assert result["dither_type"] == "ORDERED"
    assert result["dither_kernel"] == "ATKINSON"
    assert result["image_data"] == "img_b64"


def test_notify_dot_parse_url_no_host():
    """parse_url succeeds when host provides device_id."""
    result = NotifyDot.parse_url("dot://apikey@device/text/")
    assert result is not None
    assert result.get("device_id") == "device"


def test_notify_dot_parse_url_without_host():
    """parse_url returns None when host is empty."""
    assert NotifyDot.parse_url("dot://apikey@/text/") is None


def test_notify_dot_parse_url_with_empty_refresh():
    """parse_url omits refresh_now when not specified."""
    result = NotifyDot.parse_url("dot://apikey@device/text/")
    assert result is not None
    assert result.get("refresh_now") is None


def test_notify_dot_parse_url_task_key():
    """parse_url extracts task_key."""
    result = NotifyDot.parse_url("dot://apikey@device_id/?task_key=parsed")
    assert result is not None
    assert result["task_key"] == "parsed"


def test_notify_dot_parse_url_without_host_field():
    """parse_url with host=None sets no device_id."""
    from apprise import NotifyBase

    with mock.patch.object(NotifyBase, "parse_url") as mock_parse:
        mock_parse.return_value = {
            "user": "apikey",
            "password": None,
            "port": None,
            "host": None,
            "fullpath": "/text/",
            "path": "",
            "query": None,
            "schema": "dot",
            "qsd": {"refresh": "yes"},
            "secure": False,
            "verify": True,
        }
        result = NotifyDot.parse_url("dot://fake")
        assert result is not None
        assert result.get("mode") == "text"
        assert result.get("device_id") is None
        assert result.get("apikey") == "apikey"
        assert result.get("refresh_now") is True


# ---------------------------------------------------------------------------
# url_identifier
# ---------------------------------------------------------------------------


def test_notify_dot_url_identifier():
    """url_identifier includes mode."""
    dot = NotifyDot(apikey="token", device_id="device", mode="image")
    assert dot.url_identifier == ("dot", "token", "device", "image")

    dot_text = NotifyDot(apikey="token", device_id="device")
    assert dot_text.url_identifier == ("dot", "token", "device", "text")


# ---------------------------------------------------------------------------
# URL round-trip
# ---------------------------------------------------------------------------


def test_notify_dot_url_roundtrip_with_task_key():
    """parse_url -> NotifyDot -> url() preserves task_key and signature."""
    original = "dot://apikey@device123/text/?task_key=test&signature=sig"
    result = NotifyDot.parse_url(original)
    dot = NotifyDot(**result)
    reconstructed = dot.url(privacy=False)

    assert "device123" in reconstructed
    # text is the default mode; mode= is not emitted
    assert "mode=" not in reconstructed
    assert "task_key=test" in reconstructed
    assert "signature=sig" in reconstructed


# ---------------------------------------------------------------------------
# Missing credentials
# ---------------------------------------------------------------------------


def test_notify_dot_no_device_id():
    """send() returns False when device_id is missing."""
    dot = NotifyDot(apikey="token", device_id=None)
    assert dot.notify(title="test", body="test") is False
    assert len(dot) == 0


# ---------------------------------------------------------------------------
# API v2 endpoint construction
# ---------------------------------------------------------------------------


def test_notify_dot_api_v2_endpoints():
    """API v2 endpoints embed device_id in URL path."""
    dot = NotifyDot(apikey="test_key", device_id="DEVICE123", mode="text")
    assert dot.text_api_url == (
        "https://dot.mindreset.tech/api/authV2/open/device/DEVICE123/text"
    )

    dot_img = NotifyDot(apikey="test_key", device_id="DEVICE456", mode="image")
    assert dot_img.image_api_url == (
        "https://dot.mindreset.tech/api/authV2/open/device/DEVICE456/image"
    )


def test_notify_dot_deviceid_not_in_payload():
    """deviceId is NOT in text or image payload (API v2)."""
    dot = NotifyDot(apikey="test_key", device_id="12345", mode="text")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send("test body", "test title")
        payload = json.loads(mock_post.call_args[1]["data"])
        assert "deviceId" not in payload
        assert "/device/12345/text" in mock_post.call_args[0][0]

    dot_img = NotifyDot(
        apikey="test_key",
        device_id="67890",
        mode="image",
        image_data="base64data",
    )
    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot_img.send("", "")
        payload = json.loads(mock_post.call_args[1]["data"])
        assert "deviceId" not in payload
        assert "/device/67890/image" in mock_post.call_args[0][0]


# ---------------------------------------------------------------------------
# task_key
# ---------------------------------------------------------------------------


def test_notify_dot_task_key_in_text_payload():
    """taskKey appears in text API payload."""
    dot = NotifyDot(apikey="k", device_id="d", mode="text", task_key="my_task")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send("body", "title")
    assert json.loads(mock_post.call_args[1]["data"])["taskKey"] == "my_task"


def test_notify_dot_task_key_in_image_payload():
    """taskKey appears in image API payload."""
    dot = NotifyDot(
        apikey="k",
        device_id="d",
        mode="image",
        task_key="img_task",
        image_data="base64",
    )
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send("", "")
    assert json.loads(mock_post.call_args[1]["data"])["taskKey"] == "img_task"


def test_notify_dot_task_key_none_not_in_payload():
    """taskKey is absent from payload when None."""
    dot = NotifyDot(apikey="k", device_id="d", mode="text", task_key=None)
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send("test", "title")
    assert "taskKey" not in json.loads(mock_post.call_args[1]["data"])


# ---------------------------------------------------------------------------
# refresh_now
# ---------------------------------------------------------------------------


def test_notify_dot_refresh_now_defaults():
    """refreshNow defaults to True and appears correctly in payload."""
    for refresh_now, expected in ((None, True), (True, True), (False, False)):
        dot = NotifyDot(
            apikey="k",
            device_id="d",
            mode="text",
            refresh_now=refresh_now,
        )
        resp = mock.Mock()
        resp.status_code = 200

        with mock.patch("requests.post", return_value=resp) as mock_post:
            assert dot.send("test", "title")
        payload = json.loads(mock_post.call_args[1]["data"])
        assert payload["refreshNow"] is expected


def test_notify_dot_refresh_now_in_url():
    """refresh=yes appears in URL when refresh_now is None (defaults True)."""
    dot = NotifyDot(apikey="key", device_id="id", refresh_now=None)
    assert "refresh=yes" in dot.url()


# ---------------------------------------------------------------------------
# Authorization header
# ---------------------------------------------------------------------------


def test_notify_dot_authorization_header():
    """Authorization header uses Bearer format."""
    dot = NotifyDot(apikey="MY_SECRET_KEY", device_id="12345", mode="text")
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send("test", "title")
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer MY_SECRET_KEY"


# ---------------------------------------------------------------------------
# Special-character device_id
# ---------------------------------------------------------------------------


def test_notify_dot_device_id_encoding():
    """Device IDs with special characters are URL-encoded."""
    cases = [
        ("device/id", "device%2Fid"),
        ("device?id", "device%3Fid"),
        ("device#id", "device%23id"),
        ("device%id", "device%25id"),
        ("device id", "device%20id"),
        ("device@id", "device%40id"),
    ]
    for device_id, expected in cases:
        dot = NotifyDot(apikey="test_key", device_id=device_id)
        assert expected in dot.url(), (
            f"device_id '{device_id}' should encode as '{expected}'"
        )


# ---------------------------------------------------------------------------
# Combined parameter tests
# ---------------------------------------------------------------------------


def test_notify_dot_combined_text_params():
    """Text mode sends all configured parameters correctly."""
    dot = NotifyDot(
        apikey="key",
        device_id="device",
        mode="text",
        task_key="combined_task",
        refresh_now=False,
        signature="test_sig",
        link="https://example.com",
    )
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send("body", "title")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert "deviceId" not in payload
    assert payload["taskKey"] == "combined_task"
    assert payload["refreshNow"] is False
    assert payload["signature"] == "test_sig"
    assert payload["link"] == "https://example.com"
    assert payload["title"] == "title"
    assert payload["message"] == "body"


def test_notify_dot_combined_image_params():
    """Image mode sends all configured parameters correctly."""
    dot = NotifyDot(
        apikey="key",
        device_id="img_device",
        mode="image",
        image_data="base64image",
        task_key="img_task",
        refresh_now=True,
        link="https://example.com",
        border=1,
        dither_type="ORDERED",
        dither_kernel="ATKINSON",
    )
    resp = mock.Mock()
    resp.status_code = 200

    with mock.patch("requests.post", return_value=resp) as mock_post:
        assert dot.send("", "")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert "deviceId" not in payload
    assert payload["image"] == "base64image"
    assert payload["taskKey"] == "img_task"
    assert payload["refreshNow"] is True
    assert payload["link"] == "https://example.com"
    assert payload["border"] == 1
    assert payload["ditherType"] == "ORDERED"
    assert payload["ditherKernel"] == "ATKINSON"
    assert "/device/img_device/image" in mock_post.call_args[0][0]


def test_notify_dot_debug_logging_branch():
    """Exercise the isEnabledFor(DEBUG) branch inside _post."""
    dot = NotifyDot(apikey="key", device_id="dev123", mode="text")
    resp = mock.Mock()
    resp.status_code = 200

    with (
        mock.patch.object(dot.logger, "isEnabledFor", return_value=True),
        mock.patch("requests.post", return_value=resp),
    ):
        assert dot.send("body", "title")
