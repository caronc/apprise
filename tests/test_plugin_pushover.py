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
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "pover://{}@{}".format("u" * 30, "a" * 30),
        {
            "instance": NotifyPushover,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
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
    response.content = dumps(
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
    # Our invalid device is ignored
    assert len(obj.targets) == 2

    # We notify the 2 devices loaded
    assert (
        obj.notify(
            body="body", title="title", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = NotifyPushover(user_key=user_key, token=token)
    assert isinstance(obj, NotifyPushover)
    # Default is to send to all devices, so there will be a
    # device defined here
    assert len(obj.targets) == 1

    # This call succeeds because all of the devices are valid
    assert (
        obj.notify(
            body="body", title="title", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = NotifyPushover(user_key=user_key, token=token, targets=set())
    assert isinstance(obj, NotifyPushover)
    # Default is to send to all devices, so there will be a
    # device defined here
    assert len(obj.targets) == 1

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
