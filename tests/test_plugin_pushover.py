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

from json import dumps

# Disable logging for a cleaner testing output
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

import apprise
from apprise.plugins.pushover import NotifyPushover, PushoverPriority

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "pover://",
        {
            "instance": TypeError,
        },
    ),
    # bad url
    (
        "pover://:@/",
        {
            "instance": TypeError,
        },
    ),
    # APIkey; no user
    (
        "pover://%s" % ("a" * 30),
        {
            "instance": TypeError,
        },
    ),
    # API Key + custom sound setting
    (
        "pover://{}@{}?sound=mysound".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + valid alternate sound picked
    (
        "pover://{}@{}?sound=spacealarm".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + valid url_title with url
    (
        "pover://{}@{}?url=my-url&url_title=title".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + Valid User
    (
        "pover://{}@{}".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
            # don't include an image by default
            "include_image": False,
        },
    ),
    # API Key + Valid User + 1 Device
    (
        "pover://{}@{}/DEVICE".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + Valid User + 1 Device (via to=)
    (
        "pover://{}@{}?to=DEVICE".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + Valid User + 2 Devices
    (
        "pover://{}@{}/DEVICE1/Device-with-dash/".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pover://u...u@a...a",
        },
    ),
    # API Key + Valid User + invalid device
    (
        "pover://{}@{}/{}/".format("u" * 30, "a" * 30, "d" * 30),
        {
            "instance": NotifyPushover,
            # Notify will return False since there is a bad device in our list
            "response": False,
        },
    ),
    # API Key + Valid User + device + invalid device
    (
        "pover://{}@{}/DEVICE1/{}/".format("u" * 30, "a" * 30, "d" * 30),
        {
            "instance": NotifyPushover,
            # Notify will return False since there is a bad device in our list
            "response": False,
        },
    ),
    # API Key + Valid User + 1 Group key (percent-encoded)
    (
        "pover://{}@{}/%23{}".format("u" * 30, "a" * 30, "g" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + Valid User + 1 Group key (literal #)
    (
        "pover://{}@{}/#{}/".format("u" * 30, "a" * 30, "g" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + Valid User + Group key (via to= percent-encoded)
    (
        "pover://{}@{}?to=%23{}".format("u" * 30, "a" * 30, "g" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + Valid User + 2 Group keys (percent-encoded)
    (
        "pover://{}@{}/%23{}/%23{}".format(
            "u" * 30, "a" * 30, "g" * 30, "h" * 30
        ),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + Valid User + 2 Group keys (literal #)
    (
        "pover://{}@{}/#{}/#{}/".format(
            "u" * 30, "a" * 30, "g" * 30, "h" * 30
        ),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + Valid User + 1 Device + 1 Group key (percent-encoded)
    (
        "pover://{}@{}/DEVICE/%23{}".format("u" * 30, "a" * 30, "g" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + Valid User + 1 Device + 1 Group key (literal #)
    (
        "pover://{}@{}/DEVICE/#{}".format("u" * 30, "a" * 30, "g" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + Valid User + invalid group (contains invalid chars)
    (
        "pover://{}@{}/%23invalid-group/".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
            # Notify will return False since the group key is invalid
            # (contains a dash which is not alphanumeric)
            "response": False,
        },
    ),
    # API Key + priority setting
    (
        "pover://{}@{}?priority=high".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + priority setting + html mode
    (
        "pover://{}@{}?priority=high&format=html".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + priority setting + markdown mode
    (
        "pover://{}@{}?priority=high&format=markdown".format(
            "u" * 30, "a" * 30
        ),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + invalid priority setting
    (
        "pover://{}@{}?priority=invalid".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + emergency(2) priority setting
    (
        "pover://{}@{}?priority=emergency".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + emergency(2) priority setting (via numeric value
    (
        "pover://{}@{}?priority=2".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + emergency priority setting with retry and expire
    (
        "pover://{}@{}?priority=emergency&{}&{}".format(
            "u" * 30, "a" * 30, "retry=30", "expire=300"
        ),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + emergency priority setting with text retry
    (
        "pover://{}@{}?priority=emergency&{}&{}".format(
            "u" * 30, "a" * 30, "retry=invalid", "expire=300"
        ),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + emergency priority setting with text expire
    (
        "pover://{}@{}?priority=emergency&{}&{}".format(
            "u" * 30, "a" * 30, "retry=30", "expire=invalid"
        ),
        {
            "instance": NotifyPushover,
        },
    ),
    # API Key + emergency priority setting with invalid expire
    (
        "pover://{}@{}?priority=emergency&{}".format(
            "u" * 30, "a" * 30, "expire=100000"
        ),
        {
            "instance": TypeError,
        },
    ),
    # API Key + emergency priority setting with invalid retry
    (
        "pover://{}@{}?priority=emergency&{}".format(
            "u" * 30, "a" * 30, "retry=15"
        ),
        {
            "instance": TypeError,
        },
    ),
    # API Key + priority setting (empty)
    (
        "pover://{}@{}?priority=".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
        },
    ),
    (
        "pover://{}@{}".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "pover://{}@{}".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "pover://{}@{}".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_pushover_urls():
    """NotifyPushover() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_pushover_attachments(mock_post, tmpdir):
    """NotifyPushover() Attachment Checks."""

    # Initialize some generic (but valid) tokens
    user_key = "u" * 30
    api_token = "a" * 30

    # Prepare a good response
    response = mock.Mock()
    response.content = dumps(
        {"status": 1, "request": "647d2300-702c-4b38-8b2f-d56326ae460b"}
    )
    response.status_code = requests.codes.ok

    # Prepare a bad response
    bad_response = mock.Mock()
    bad_response.content = dumps(
        {"status": 1, "request": "647d2300-702c-4b38-8b2f-d56326ae460b"}
    )
    bad_response.status_code = requests.codes.internal_server_error

    # Assign our good response
    mock_post.return_value = response

    # prepare our attachment
    attach = apprise.AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    )

    # Instantiate our object
    obj = apprise.Apprise.instantiate(f"pover://{user_key}@{api_token}/")
    assert isinstance(obj, NotifyPushover)

    # Test our attachment
    assert obj.notify(body="test", attach=attach) is True

    # Test our call count
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.pushover.net/1/messages.json"
    )

    # Reset our mock object for multiple tests
    mock_post.reset_mock()

    # Test multiple attachments
    assert attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))
    assert obj.notify(body="test", attach=attach) is True

    # Test our call count
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.pushover.net/1/messages.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.pushover.net/1/messages.json"
    )

    # Reset our mock object for multiple tests
    mock_post.reset_mock()

    image = tmpdir.mkdir("pover_image").join("test.jpg")
    image.write("a" * NotifyPushover.attach_max_size_bytes)

    attach = apprise.AppriseAttachment.instantiate(str(image))
    assert obj.notify(body="test", attach=attach) is True

    # Test our call count
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.pushover.net/1/messages.json"
    )

    # Reset our mock object for multiple tests
    mock_post.reset_mock()

    # Add 1 more byte to the file (putting it over the limit)
    image.write("a" * (NotifyPushover.attach_max_size_bytes + 1))

    attach = apprise.AppriseAttachment.instantiate(str(image))
    assert obj.notify(body="test", attach=attach) is False

    # Test our call count
    assert mock_post.call_count == 0

    # Test case when file is missing
    attach = apprise.AppriseAttachment.instantiate(
        f"file://{image!s}?cache=False"
    )
    os.unlink(str(image))
    assert obj.notify(body="body", title="title", attach=attach) is False

    # Test our call count
    assert mock_post.call_count == 0

    # Test unsuported files:
    image = tmpdir.mkdir("pover_unsupported").join("test.doc")
    image.write("a" * 256)
    attach = apprise.AppriseAttachment.instantiate(str(image))

    # Content is silently ignored
    assert obj.notify(body="test", attach=attach) is True

    # prepare our attachment
    attach = apprise.AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    )

    # Throw an exception on the first call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = [side_effect, side_effect]

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

        # Same case without an attachment
        assert obj.send(body="test") is False


@mock.patch("requests.post")
def test_plugin_pushover_edge_cases(mock_post):
    """NotifyPushover() Edge Cases."""

    # No token
    with pytest.raises(TypeError):
        NotifyPushover(token=None)

    # Initialize some generic (but valid) tokens
    token = "a" * 30
    user_key = "u" * 30

    invalid_device = "d" * 35

    # Support strings
    devices = f"device1,device2,,,,{invalid_device}"

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # No webhook id specified
    with pytest.raises(TypeError):
        NotifyPushover(user_key=user_key, webhook_id=None)

    obj = NotifyPushover(user_key=user_key, token=token, targets=devices)
    assert isinstance(obj, NotifyPushover)
    # Our invalid device is ignored; 2 valid devices remain
    assert len(obj.devices) == 2
    assert len(obj.groups) == 0

    # We notify the 2 devices loaded
    assert (
        obj.notify(
            body="body", title="title", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = NotifyPushover(user_key=user_key, token=token)
    assert isinstance(obj, NotifyPushover)
    # Default is to send to all devices (sentinel placed in devices list)
    assert len(obj.devices) == 1
    assert len(obj.groups) == 0
    assert len(obj) == 1

    # This call succeeds because all of the devices are valid
    assert (
        obj.notify(
            body="body", title="title", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = NotifyPushover(user_key=user_key, token=token, targets=set())
    assert isinstance(obj, NotifyPushover)
    # Default is to send to all devices (sentinel placed in devices list)
    assert len(obj.devices) == 1
    assert len(obj.groups) == 0
    assert len(obj) == 1

    # Group targets
    group_key = "g" * 30
    obj = NotifyPushover(
        user_key=user_key, token=token, targets=f"#{group_key}"
    )
    assert isinstance(obj, NotifyPushover)
    assert len(obj.devices) == 0
    assert len(obj.groups) == 1
    assert obj.groups[0] == group_key
    assert len(obj) == 1

    # Verify notification to a group succeeds (separate API call per group)
    assert (
        obj.notify(
            body="body", title="title", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    # Mix of device and group → 2 HTTP calls (1 device batch + 1 group)
    obj = NotifyPushover(
        user_key=user_key, token=token, targets=["device1", f"#{group_key}"]
    )
    assert isinstance(obj, NotifyPushover)
    assert len(obj.devices) == 1
    assert len(obj.groups) == 1
    assert len(obj) == 2

    # Invalid group key (contains dash — not alphanumeric)
    obj = NotifyPushover(
        user_key=user_key, token=token, targets="#invalid-group"
    )
    assert isinstance(obj, NotifyPushover)
    # Invalid target is rejected; both lists empty → send() returns False
    assert len(obj.devices) == 0
    assert len(obj.groups) == 0

    # Always 1 is returned as minimum
    assert len(obj) == 1

    # No User Key specified
    with pytest.raises(TypeError):
        NotifyPushover(user_key=None, token="abcd")

    # No Access Token specified
    with pytest.raises(TypeError):
        NotifyPushover(user_key="abcd", token=None)

    with pytest.raises(TypeError):
        NotifyPushover(user_key="abcd", token="  ")


@mock.patch("requests.post")
def test_plugin_pushover_config_files(mock_post):
    """NotifyPushover() Config File Cases."""
    content = """
    urls:
      - pover://USER@TOKEN:
          - priority: -2
            tag: pushover_int low
          - priority: "-2"
            tag: pushover_str_int low
          - priority: low
            tag: pushover_str low

          # This will take on normal (default) priority
          - priority: invalid
            tag: pushover_invalid

      - pover://USER2@TOKEN2:
          - priority: 2
            tag: pushover_int emerg
          - priority: "2"
            tag: pushover_str_int emerg
          - priority: emergency
            tag: pushover_str emerg
    """

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 7 servers from that
    # 3x low
    # 3x emerg
    # 1x invalid (so takes on normal priority)
    assert len(ac.servers()) == 7
    assert len(aobj) == 7
    assert len(list(aobj.find(tag="low"))) == 3
    for s in aobj.find(tag="low"):
        assert s.priority == PushoverPriority.LOW

    assert len(list(aobj.find(tag="emerg"))) == 3
    for s in aobj.find(tag="emerg"):
        assert s.priority == PushoverPriority.EMERGENCY

    assert len(list(aobj.find(tag="pushover_str"))) == 2
    assert len(list(aobj.find(tag="pushover_str_int"))) == 2
    assert len(list(aobj.find(tag="pushover_int"))) == 2

    assert len(list(aobj.find(tag="pushover_invalid"))) == 1
    assert (
        next(aobj.find(tag="pushover_invalid")).priority
        == PushoverPriority.NORMAL
    )

    # Notifications work
    # We test 'pushover_str_int' and 'low' which only matches 1 end point
    assert (
        aobj.notify(
            title="title", body="body", tag=[("pushover_str_int", "low")]
        )
        is True
    )

    # Notify everything loaded
    assert aobj.notify(title="title", body="body") is True


@mock.patch("requests.post")
def test_plugin_pushover_group_request_exception(mock_post):
    """NotifyPushover() group RequestException must not raise KeyError."""
    user_key = "u" * 30
    token = "a" * 30
    group_key = "g" * 30

    mock_post.side_effect = requests.RequestException("connection error")

    obj = NotifyPushover(
        user_key=user_key, token=token, targets=f"#{group_key}"
    )
    assert isinstance(obj, NotifyPushover)
    assert len(obj.groups) == 1
    assert len(obj.devices) == 0

    # Must return False cleanly -- no KeyError from payload["device"]
    assert obj.send(body="test") is False


@mock.patch("requests.post")
def test_plugin_pushover_url_roundtrip(mock_post):
    """NotifyPushover() url() must preserve sound, url, and url_title."""
    from apprise.plugins.pushover import NotifyPushover

    user_key = "u" * 30
    token = "a" * 30

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok

    # Instantiate with all three round-trip fields set
    obj = NotifyPushover(
        user_key=user_key,
        token=token,
        sound="bike",
        supplemental_url="https://example.com",
        supplemental_url_title="Click Here",
    )
    assert isinstance(obj, NotifyPushover)
    assert obj.sound == "bike"
    assert obj.supplemental_url == "https://example.com"
    assert obj.supplemental_url_title == "Click Here"

    # Round-trip via url() -> parse_url() -> re-instantiate
    generated_url = obj.url()
    assert "sound=bike" in generated_url
    assert "url=" in generated_url
    assert "url_title=" in generated_url

    parsed = NotifyPushover.parse_url(generated_url)
    assert parsed is not None
    assert parsed["sound"] == "bike"
    assert parsed["supplemental_url"] == "https://example.com"
    assert parsed["supplemental_url_title"] == "Click Here"

    obj2 = NotifyPushover(**parsed)
    assert obj2.sound == "bike"
    assert obj2.supplemental_url == "https://example.com"
    assert obj2.supplemental_url_title == "Click Here"


def test_plugin_pushover_parse_url_title_unquote():
    """NotifyPushover() parse_url() unquote url_title like other fields."""
    user_key = "u" * 30
    token = "a" * 30

    # url_title with percent-encoded spaces and special chars
    url = "pover://{}@{}/?url_title=Hello%20World".format(user_key, token)
    parsed = NotifyPushover.parse_url(url)
    assert parsed is not None
    # Must be decoded, not raw percent-encoded
    assert parsed["supplemental_url_title"] == "Hello World"

    # Spacing is fine too
    url = "pover://{}@{}/?url_title=Hello World".format(user_key, token)
    parsed = NotifyPushover.parse_url(url)
    assert parsed is not None
    # Must be decoded, not raw percent-encoded
    assert parsed["supplemental_url_title"] == "Hello World"


@mock.patch("requests.post")
def test_plugin_pushover_attach_memory(mock_post):
    """Regression: AttachMemory must be sendable without OSError."""
    from apprise.attachment.memory import AttachMemory

    user_key = "u" * 30
    api_token = "a" * 30

    response = mock.Mock()
    response.content = dumps(
        {"status": 1, "request": "647d2300-702c-4b38-8b2f-d56326ae460b"}
    )
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = apprise.Apprise.instantiate(f"pover://{user_key}@{api_token}/")
    assert isinstance(obj, NotifyPushover)

    mem = AttachMemory(
        content=b"<html><body><h1>Test</h1></body></html>",
        name="report.html",
        mimetype="text/html",
    )

    assert obj.notify(body="Test", attach=mem) is True
    assert mock_post.call_count == 1
