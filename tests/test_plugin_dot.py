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
import logging
import json

from helpers import AppriseURLTester

from apprise.plugins.dot import NotifyDot

from unittest import mock
from urllib.parse import urlparse, parse_qs


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
    args, kwargs = mock_post.call_args
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

    args, kwargs = mock_post.call_args
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

