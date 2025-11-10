# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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
            # No API key
            "instance": NotifyDot,
            # Expected notify() response False (because we won't be able
            # to actually notify anything if no api key was specified
            "notify_response": False,
        },
    ),
    (
        "dot://apikey@device_id/text/",
        {
            # Everything is okay (text mode)
            "instance": NotifyDot,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "dot://****@device_id/text/",
        },
    ),
    (
        "dot://apikey@device_id/text/?refresh=no",
        {
            # Disable refresh now
            "instance": NotifyDot,
        },
    ),
    (
        "dot://apikey@device_id/text/?signature=test_signature",
        {
            # With signature
            "instance": NotifyDot,
        },
    ),
    (
        "dot://apikey@device_id/text/?link=https://example.com",
        {
            # With link
            "instance": NotifyDot,
        },
    ),
    (
        "dot://apikey@device_id/image/?link=https://example.com&border=1&dither_type=ORDERED&dither_kernel=ATKINSON",
        {
            # Image mode without payload should fail
            "instance": NotifyDot,
            "notify_response": False,
            "attach_response": True,
        },
    ),
    (
        "dot://apikey@device_id/image/?image=ZmFrZUJhc2U2NA==&link=https://example.com&border=1&dither_type=DIFFUSION&dither_kernel=FLOYD_STEINBERG",
        {
            # Image mode with provided image data
            "instance": NotifyDot,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "dot://****@device_id/image/",
        },
    ),
    (
        "dot://apikey@device_id/text/",
        {
            "instance": NotifyDot,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "dot://apikey@device_id/text/",
        {
            "instance": NotifyDot,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "dot://apikey@device_id/unknown/",
        {
            # Unknown mode defaults back to text
            "instance": NotifyDot,
            "privacy_url": "dot://****@device_id/text/",
        },
    ),
)


def test_plugin_dot_urls():
    """NotifyDot() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_notify_dot_image_mode_requires_image():
    dot = NotifyDot(apikey="token", device_id="device", mode="image")
    assert dot.notify(title="x", body="y") is False


def test_notify_dot_image_mode_with_attachment():
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        link="https://example.com",
        border=1,
        dither_type="ORDERED",
        dither_kernel="ATKINSON",
    )

    response = mock.Mock()
    response.status_code = 200

    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(
            body="payload", title="title", attach=[DummyAttachment("YmFzZTY0")]
        )

    assert mock_post.called
    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert payload["image"] == "YmFzZTY0"
    assert payload["deviceId"] == "device"


def test_notify_dot_text_mode_ignores_attachment():
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        signature="footer",
        icon="aW5jb24=",
    )

    response = mock.Mock()
    response.status_code = 200

    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(
            title="hello",
            body="world",
            attach=[DummyAttachment()],
        )

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert "image" not in payload
    assert payload["deviceId"] == "device"
    assert payload["message"] == "world"


def test_notify_dot_url_generation():
    text_dot = NotifyDot(
        apikey="token",
        device_id="device",
        signature="sig",
        icon="aW5jb24=",
    )
    text_url = text_dot.url()
    parsed = urlparse(text_url)
    assert parsed.path.endswith("/text/")
    query = parse_qs(parsed.query)
    assert query["refresh"] == ["yes"]
    assert query["signature"] == ["sig"]

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
    parsed_image = urlparse(image_url)
    assert parsed_image.path.endswith("/image/")
    image_query = parse_qs(parsed_image.query)
    assert image_query["image"] == ["aW1hZ2U="]
    assert image_query["border"] == ["1"]


def test_notify_dot_parse_url_mode_and_image():
    result = NotifyDot.parse_url(
        "dot://token@device/image/?image=Zm9vYmFy&link=https://example.com"
    )
    assert result["mode"] == "image"
    assert result["image_data"] == "Zm9vYmFy"
    assert result["link"] == "https://example.com"

    fallback = NotifyDot.parse_url("dot://token@device/unknown/?refresh=no")
    assert fallback["mode"] == "text"
    assert fallback["refresh_now"] is False


def test_notify_dot_invalid_border():
    """Test invalid border values."""
    # Invalid border value should default to 0
    dot = NotifyDot(apikey="token", device_id="device", border=5)
    assert dot.border == 0

    dot = NotifyDot(apikey="token", device_id="device", border="invalid")
    assert dot.border == 0


def test_notify_dot_invalid_mode():
    """Test invalid mode handling."""
    dot = NotifyDot(apikey="token", device_id="device", mode="invalid_mode")
    assert dot.mode == "text"

    dot = NotifyDot(apikey="token", device_id="device", mode=123)
    assert dot.mode == "text"


def test_notify_dot_image_data_in_text_mode():
    """Test that image_data is ignored in text mode."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="text",
        image_data="somebase64",
    )
    assert dot.image_data is None


def test_notify_dot_default_title_message():
    """Test default title and message fallback."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        title="default_title",
        message="default_message",
    )

    response = mock.Mock()
    response.status_code = 200

    # Test with empty body and title
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(body="", title="")

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    # Should use default message when body is empty
    assert payload["message"] == "default_message"


def test_notify_dot_no_device_id():
    """Test behavior when device_id is missing."""
    dot = NotifyDot(apikey="token", device_id=None)
    assert dot.notify(title="test", body="test") is False
    assert len(dot) == 0


def test_notify_dot_parse_url_with_all_params():
    """Test parse_url with all parameters."""
    result = NotifyDot.parse_url(
        "dot://apikey@device/image/?refresh=yes&signature=sig&icon=icon_b64"
        "&link=https://example.com&border=1&dither_type=ORDERED"
        "&dither_kernel=ATKINSON&image=img_b64&title=test_title&message=test_msg"
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
    assert result["title"] == "test_title"
    assert result["message"] == "test_msg"


def test_notify_dot_url_identifier():
    """Test url_identifier property."""
    dot = NotifyDot(apikey="token", device_id="device", mode="image")
    identifier = dot.url_identifier
    assert identifier == ("dot", "token", "device", "image")


def test_notify_dot_image_mode_with_failed_attachment():
    """Test image mode when attachment fails to convert."""

    class FailedAttachment:
        def base64(self):
            raise Exception("Conversion failed")

    dot = NotifyDot(apikey="token", device_id="device", mode="image")
    # Should fail when no valid image data is available
    assert dot.notify(
        title="test", body="test", attach=[FailedAttachment()]
    ) is False


def test_notify_dot_url_generation_defaults():
    """Test URL generation with default values."""
    dot = NotifyDot(apikey="token", device_id="device")
    url = dot.url()
    assert "refresh=yes" in url
    assert "/text/" in url

    # Test image mode URL with non-default values
    dot_image = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="img",
        dither_type="ORDERED",
        dither_kernel="ATKINSON",
    )
    url_image = dot_image.url()
    assert "/image/" in url_image
    assert "dither_type=ORDERED" in url_image
    assert "dither_kernel=ATKINSON" in url_image


def test_notify_dot_image_mode_with_multiple_attachments():
    """Test image mode with multiple attachments where some fail."""

    class EmptyAttachment:
        def base64(self):
            return None

    dot = NotifyDot(apikey="token", device_id="device", mode="image")

    response = mock.Mock()
    response.status_code = 200

    # First attachment returns None, second returns valid data
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(
            body="test",
            title="test",
            attach=[EmptyAttachment(), DummyAttachment("validbase64")],
        )

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert payload["image"] == "validbase64"


def test_notify_dot_text_mode_fallback_to_app_desc():
    """Test text mode fallback to app_desc when title is empty."""
    dot = NotifyDot(apikey="token", device_id="device")

    response = mock.Mock()
    response.status_code = 200

    # Test with empty title, should fallback to app_desc
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(body="test message", title="")

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    # Should have app_desc as title
    assert "title" in payload
    assert payload["message"] == "test message"


def test_notify_dot_url_generation_with_link():
    """Test URL generation with link in text mode."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        link="https://example.com",
    )
    url = dot.url()
    assert "link=" in url

    # Test image mode with border=0 (should not appear in URL for default)
    dot_image = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="img",
        border=0,
    )
    url_image = dot_image.url()
    assert "border=0" in url_image

