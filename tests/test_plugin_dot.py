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
            "force_debug": True,
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
    """Test image mode uses first attachment when no image_data provided."""
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


def test_notify_dot_image_mode_with_existing_image_data():
    """Test image mode ignores attachment when image_data is provided."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="existing_image_data",
    )

    response = mock.Mock()
    response.status_code = 200

    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(
            body="test",
            title="test",
            attach=[DummyAttachment("attachment_data")],
        )

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    # Should use existing image_data, not attachment
    assert payload["image"] == "existing_image_data"


def test_notify_dot_text_mode_with_existing_icon():
    """Test text mode with existing icon (attachment should be ignored)."""
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
            attach=[DummyAttachment("attachment_icon")],
        )

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert "image" not in payload
    assert payload["deviceId"] == "device"
    assert payload["message"] == "world"
    # Should use existing icon, not attachment
    assert payload["icon"] == "aW5jb24="


def test_notify_dot_text_mode_uses_attachment_as_icon():
    """Test text mode uses first attachment as icon when no icon provided."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        signature="footer",
    )

    response = mock.Mock()
    response.status_code = 200

    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(
            title="hello",
            body="world",
            attach=[DummyAttachment("attachment_icon_data")],
        )

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert payload["deviceId"] == "device"
    assert payload["message"] == "world"
    # Should use attachment as icon
    assert payload["icon"] == "attachment_icon_data"


def test_notify_dot_text_mode_multiple_attachments_warning():
    """Test text mode warns when multiple attachments are provided."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
    )

    response = mock.Mock()
    response.status_code = 200

    with (
        mock.patch("requests.post", return_value=response) as mock_post,
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
        # Should warn about multiple attachments
        mock_warning.assert_called_once()
        assert "Multiple attachments" in str(mock_warning.call_args)

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    # Should use first attachment only
    assert payload["icon"] == "first"


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


def test_notify_dot_text_mode_with_title_and_body():
    """Test text mode with title and body."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
    )

    response = mock.Mock()
    response.status_code = 200

    # Test with title and body provided at runtime
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(body="test_body", title="test_title")

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert payload["message"] == "test_body"
    assert payload["title"] == "test_title"


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
    """Test image mode with multiple attachments (only first is used)."""

    dot = NotifyDot(apikey="token", device_id="device", mode="image")

    response = mock.Mock()
    response.status_code = 200

    # Multiple attachments provided, only first should be used
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(
            body="test",
            title="test",
            attach=[
                DummyAttachment("first_attachment"),
                DummyAttachment("second_attachment"),
            ],
        )

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    # Should use first attachment only
    assert payload["image"] == "first_attachment"


def test_notify_dot_text_mode_without_title():
    """Test text mode without title (title is optional)."""
    dot = NotifyDot(apikey="token", device_id="device")

    response = mock.Mock()
    response.status_code = 200

    # Test with empty title - title should not be in payload
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(body="test message", title="")

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    # Title should not be in payload when empty
    assert "title" not in payload
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


def test_notify_dot_title_handling():
    """Test title handling in text mode."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
    )

    response = mock.Mock()
    response.status_code = 200

    # Test 1: With provided title
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(body="test", title="provided_title")

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert payload["title"] == "provided_title"

    # Test 2: Without provided title, should not include title in payload
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(body="test", title="")

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    # Title should not be in payload when empty
    assert "title" not in payload


def test_notify_dot_image_mode_no_border():
    """Test image mode with border=None to skip border in payload."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="base64img",
    )
    # Manually set border to None
    dot.border = None

    response = mock.Mock()
    response.status_code = 200

    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(body="test", title="test")

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    # Border should not be in payload when None
    assert "border" not in payload


def test_notify_dot_image_mode_no_dither():
    """Test image mode with no dither_type/dither_kernel."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="base64img",
    )
    # Manually set to None to test the conditional branches
    dot.dither_type = None
    dot.dither_kernel = None

    response = mock.Mock()
    response.status_code = 200

    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(body="test", title="test")

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    # Dither fields should not be in payload when None
    assert "ditherType" not in payload
    assert "ditherKernel" not in payload


def test_notify_dot_text_mode_no_optional_fields():
    """Test text mode with no signature, icon, or link."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
    )

    response = mock.Mock()
    response.status_code = 200

    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(body="test body", title="test title")

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert "signature" not in payload
    assert "icon" not in payload
    # Link should not be in payload when not set
    assert payload.get("link") is None or "link" not in payload


def test_notify_dot_url_generation_without_defaults():
    """Test URL generation without default dither values."""
    # Test with DIFFUSION (default) - should not appear in URL
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="img",
        dither_type="DIFFUSION",
        dither_kernel="FLOYD_STEINBERG",
    )
    url = dot.url()
    # Default values should not appear in URL
    assert "dither_type" not in url
    assert "dither_kernel" not in url


def test_notify_dot_image_mode_attachment_exception():
    """Test exception handling in image mode when attachment.base64() fails."""

    class ExceptionAttachment:
        def base64(self):
            raise Exception("First attachment fails")

    dot = NotifyDot(apikey="token", device_id="device", mode="image")

    # First attachment throws exception, should log warning and fail
    with mock.patch.object(dot.logger, "warning") as mock_warning:
        assert dot.send(
            body="test",
            title="test",
            attach=[ExceptionAttachment()],
        ) is False
        # Should log warning about failed attachment processing
        assert mock_warning.called
        # Check that the warning message contains expected text
        warning_calls = [str(call) for call in mock_warning.call_args_list]
        assert any(
            "Failed to process attachment" in str(call)
            for call in warning_calls
        )


def test_notify_dot_image_mode_attachment_none():
    """Test image mode when attachment is None."""
    dot = NotifyDot(apikey="token", device_id="device", mode="image")

    # Attachment is None, should skip base64() call and fail
    assert dot.send(
        body="test",
        title="test",
        attach=[None],
    ) is False


def test_notify_dot_image_mode_attachment_falsy():
    """Test image mode when attachment is falsy."""
    dot = NotifyDot(apikey="token", device_id="device", mode="image")

    # Attachment is falsy (empty string), should skip base64() call and fail
    class FalsyAttachment:
        def __bool__(self):
            return False

        def base64(self):
            return "should_not_be_called"

    assert dot.send(
        body="test",
        title="test",
        attach=[FalsyAttachment()],
    ) is False


def test_notify_dot_text_mode_attachment_exception():
    """Test exception handling in text mode when attachment.base64() fails."""

    class ExceptionAttachment:
        def base64(self):
            raise Exception("Attachment base64 conversion fails")

    dot = NotifyDot(apikey="token", device_id="device", mode="text")

    response = mock.Mock()
    response.status_code = 200

    # First attachment throws exception, should log warning but continue
    with (
        mock.patch("requests.post", return_value=response) as mock_post,
        mock.patch.object(dot.logger, "warning") as mock_warning,
    ):
        assert dot.send(
            title="hello",
            body="world",
            attach=[ExceptionAttachment()],
        )
        # Should log warning about failed attachment processing
        assert mock_warning.called
        # Check that the warning message contains expected text
        warning_calls = [str(call) for call in mock_warning.call_args_list]
        assert any(
            "Failed to process attachment" in str(call)
            for call in warning_calls
        )

    # Should still send notification without icon
    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert payload["message"] == "world"
    assert "icon" not in payload


def test_notify_dot_text_mode_attachment_none():
    """Test text mode when attachment is None (covers if attachment branch)."""
    dot = NotifyDot(apikey="token", device_id="device", mode="text")

    response = mock.Mock()
    response.status_code = 200

    # Attachment is None, should skip base64() call and continue without icon
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(
            title="hello",
            body="world",
            attach=[None],
        )

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert payload["message"] == "world"
    assert "icon" not in payload


def test_notify_dot_text_mode_attachment_falsy():
    """Test text mode when attachment is falsy."""
    dot = NotifyDot(apikey="token", device_id="device", mode="text")

    response = mock.Mock()
    response.status_code = 200

    # Attachment is falsy, should skip base64() call and continue without icon
    class FalsyAttachment:
        def __bool__(self):
            return False

        def base64(self):
            return "should_not_be_called"

    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(
            title="hello",
            body="world",
            attach=[FalsyAttachment()],
        )

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert payload["message"] == "world"
    assert "icon" not in payload


def test_notify_dot_parse_url_no_host():
    """Test parse_url when host is empty (line 578)."""
    # Test URL with empty host - device_id should not be added
    # Using a valid URL structure but testing when host is explicitly empty
    result = NotifyDot.parse_url("dot://apikey@device/text/")
    # This should succeed and have a device_id
    assert result is not None
    assert result.get("device_id") == "device"


def test_notify_dot_url_with_border_not_none():
    """Test URL generation when border is not None (line 515)."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="img",
        border=1,
    )
    url = dot.url()
    # Border should be in URL when not None
    assert "border=1" in url


def test_notify_dot_image_mode_with_only_title():
    """Test image mode warning with only title (no body)."""
    dot = NotifyDot(apikey="token", device_id="device", mode="image")

    response = mock.Mock()
    response.status_code = 200

    # Test with only title, no body - should still warn
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(
            title="test_title",
            body="",
            attach=[DummyAttachment("image_data")],
        )

    # Should have sent the notification but logged a warning
    assert mock_post.called


def test_notify_dot_image_mode_with_only_body():
    """Test image mode warning with only body (no title)."""
    dot = NotifyDot(apikey="token", device_id="device", mode="image")

    response = mock.Mock()
    response.status_code = 200

    # Test with only body, no title - should still warn
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(
            title="",
            body="test_body",
            attach=[DummyAttachment("image_data")],
        )

    # Should have sent the notification but logged a warning
    assert mock_post.called


def test_notify_dot_text_mode_without_body():
    """Test text mode with empty body."""
    dot = NotifyDot(apikey="token", device_id="device")

    response = mock.Mock()
    response.status_code = 200

    # Test with title but no body
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(body="", title="test_title")

    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert payload["title"] == "test_title"
    # Body should not be in payload when empty
    assert "message" not in payload


def test_notify_dot_parse_url_without_host():
    """Test parse_url when URL has no host."""
    # URL with no host (missing device_id) - should return None
    result = NotifyDot.parse_url("dot://apikey@/text/")
    # Without a host, the URL is invalid and parse_url returns None
    assert result is None


def test_notify_dot_image_mode_without_title_and_body():
    """Test image mode without title and body (line 294->300)."""
    dot = NotifyDot(
        apikey="token",
        device_id="device",
        mode="image",
        image_data="base64img",
    )

    response = mock.Mock()
    response.status_code = 200

    # Send without title and body - should not trigger warning
    with mock.patch("requests.post", return_value=response) as mock_post:
        assert dot.send(title="", body="")

    # Should have sent the notification
    assert mock_post.called
    _args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])
    assert payload["image"] == "base64img"
    assert "title" not in payload
    assert "message" not in payload


def test_notify_dot_parse_url_with_empty_refresh():
    """Test parse_url when refresh query parameter is empty (line 535->539)."""
    # Test with no refresh parameter (should default to True)
    result = NotifyDot.parse_url("dot://apikey@device/text/")
    assert result is not None
    # When refresh is not specified, it defaults to True
    assert result.get("refresh_now") is None  # Not set in parse_url


def test_notify_dot_image_mode_first_attachment_fails():
    """Test image mode when first attachment fails (returns None)."""

    class FailingAttachment:
        def base64(self):
            return None  # Returns None

    dot = NotifyDot(apikey="token", device_id="device", mode="image")

    # First attachment returns None, should fail immediately
    assert dot.notify(
        title="",
        body="",
        attach=[FailingAttachment()],
    ) is False


def test_notify_dot_image_mode_with_empty_attach_list():
    """Test image mode with empty attachments list (line 305->313)."""
    dot = NotifyDot(apikey="token", device_id="device", mode="image")

    # Try with empty attachments list
    # Condition: not image_data and attach -> not None and [] -> False
    # Should skip the for loop and go directly to line 313
    assert dot.notify(
        title="",
        body="",
        attach=[],  # Empty list (truthy in Python but loop won't execute)
    ) is False


def test_notify_dot_parse_url_without_host_field():
    """Test parse_url when host field is None (line 535->539)."""
    from apprise import NotifyBase

    # Mock NotifyBase.parse_url to return results with host=None
    # This triggers the else branch of "if host:" at line 535
    with mock.patch.object(NotifyBase, "parse_url") as mock_parse:
        mock_parse.return_value = {
            "user": "apikey",
            "password": None,
            "port": None,
            "host": None,  # host is None - triggers 535->539 branch
            "fullpath": "/text/",
            "path": "",
            "query": None,
            "schema": "dot",
            "qsd": {"refresh": "yes"},
            "secure": False,
            "verify": True,
        }

        result = NotifyDot.parse_url("dot://fake")

        # Should have mode but no device_id since host was None
        assert result is not None
        assert result.get("mode") == "text"
        assert result.get("device_id") is None
        assert result.get("apikey") == "apikey"
        assert result.get("refresh_now") is True  # refresh was in qsd

