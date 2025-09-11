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

from inspect import cleandoc
from json import loads

# Disable logging for a cleaner testing output
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.config import ConfigBase
from apprise.plugins.signal_api import NotifySignalAPI

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")


@pytest.fixture
def request_mock(mocker):
    """Prepare requests mock."""
    mock_post = mocker.patch("requests.post")
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = ""
    return mock_post


# Our Testing URLs
apprise_url_tests = (
    (
        "signal://",
        {
            # No host specified
            "instance": TypeError,
        },
    ),
    (
        "signal://:@/",
        {
            # invalid host
            "instance": TypeError,
        },
    ),
    (
        "signal://localhost",
        {
            # Just a host provided
            "instance": TypeError,
        },
    ),
    (
        "signal://localhost",
        {
            # key and secret provided and from but invalid from no
            "instance": TypeError,
        },
    ),
    (
        "signal://localhost/123",
        {
            # invalid from phone
            "instance": TypeError,
        },
    ),
    (
        "signal://localhost/{}/123/".format("1" * 11),
        {
            # invalid 'to' phone number
            "instance": NotifySignalAPI,
            # Notify will fail because it couldn't send to anyone
            "response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "signal://localhost/+{}/123".format("1" * 11),
        },
    ),
    (
        "signal://localhost:8080/{}/".format("1" * 11),
        {
            # one phone number will notify ourselves
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signal://localhost:8082/+{}/@group.abcd/".format("2" * 11),
        {
            # a valid group
            "instance": NotifySignalAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "signal://localhost:8082/+{}/@abcd".format(
                "2" * 11
            ),
        },
    ),
    (
        "signal://localhost:8080/+{}/group.abcd/".format("1" * 11),
        {
            # another valid group (without @ symbol)
            "instance": NotifySignalAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "signal://localhost:8080/+{}/@abcd".format(
                "1" * 11
            ),
        },
    ),
    (
        "signal://localhost:8080/?from={}&to={},{}".format(
            "1" * 11, "2" * 11, "3" * 11
        ),
        {
            # use get args to acomplish the same thing
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signal://localhost:8080/?from={}&to={},{},{}".format(
            "1" * 11, "2" * 11, "3" * 11, "5" * 3
        ),
        {
            # 2 good targets and one invalid one
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signal://localhost:8080/{}/{}/?from={}".format(
            "1" * 11, "2" * 11, "3" * 11
        ),
        {
            # If we have from= specified, then all elements take on the to=
            # value
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signals://user@localhost/{}/{}".format("1" * 11, "3" * 11),
        {
            # use get args to acomplish the same thing (use source instead of
            # from)
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signals://user:password@localhost/{}/{}".format("1" * 11, "3" * 11),
        {
            # use get args to acomplish the same thing (use source instead of
            # from)
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signals://user:password@localhost/{}/{}".format("1" * 11, "3" * 11),
        {
            "instance": NotifySignalAPI,
            # Test that a 201 response code is still accepted
            "requests_response_code": 201,
        },
    ),
    (
        "signals://localhost/{}/{}/{}?batch=True".format(
            "1" * 11, "3" * 11, "4" * 11
        ),
        {
            # test batch mode
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signals://localhost/{}/{}/{}?status=True".format(
            "1" * 11, "3" * 11, "4" * 11
        ),
        {
            # test status switch
            "instance": NotifySignalAPI,
        },
    ),
    (
        "signal://localhost/{}/{}".format("1" * 11, "4" * 11),
        {
            "instance": NotifySignalAPI,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "signal://localhost/{}/{}".format("1" * 11, "4" * 11),
        {
            "instance": NotifySignalAPI,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_signal_urls():
    """NotifySignalAPI() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_signal_edge_cases(request_mock):
    """NotifySignalAPI() Edge Cases."""
    # Initialize some generic (but valid) tokens
    source = "+1 (555) 123-3456"
    target = "+1 (555) 987-5432"
    body = "test body"
    title = "My Title"

    # No apikey specified
    with pytest.raises(TypeError):
        NotifySignalAPI(source=None)

    aobj = Apprise()
    assert aobj.add(f"signals://localhost:231/{source}/{target}")
    assert aobj.notify(title=title, body=body)

    assert request_mock.call_count == 1

    details = request_mock.call_args_list[0]
    assert details[0][0] == "https://localhost:231/v2/send"
    payload = loads(details[1]["data"])
    assert payload["message"] == "My Title\r\ntest body"

    # Reset our mock object
    request_mock.reset_mock()

    aobj = Apprise()
    assert aobj.add(
        f"signals://user@localhost:231/{source}/{target}?status=True"
    )
    assert aobj.notify(title=title, body=body)

    assert request_mock.call_count == 1

    details = request_mock.call_args_list[0]
    assert details[0][0] == "https://localhost:231/v2/send"
    payload = loads(details[1]["data"])
    # Status flag is set
    assert payload["message"] == "[i] My Title\r\ntest body"


def test_plugin_signal_yaml_config(request_mock):
    """NotifySignalAPI() YAML Configuration."""

    # Load our configuration
    result, _ = ConfigBase.config_parse_yaml(cleandoc("""
    urls:
      - signal://signal:8080/+1234567890:
         - to: +0987654321
           tag: signal
    """))

    # Verify we loaded correctly
    assert isinstance(result, list)
    assert len(result) == 1
    assert len(result[0].tags) == 1
    assert "signal" in result[0].tags

    # Let's get our plugin
    plugin = result[0]
    assert len(plugin.targets) == 1
    assert plugin.source == "+1234567890"
    assert "+0987654321" in plugin.targets

    #
    # Test another way to get the same results
    #

    # Load our configuration
    result, _config = ConfigBase.config_parse_yaml(cleandoc("""
    urls:
      - signal://signal:8080/+1234567890/+0987654321:
         - tag: signal
    """))

    # Verify we loaded correctly
    assert isinstance(result, list)
    assert len(result) == 1
    assert len(result[0].tags) == 1
    assert "signal" in result[0].tags

    # Let's get our plugin
    plugin = result[0]
    assert len(plugin.targets) == 1
    assert plugin.source == "+1234567890"
    assert "+0987654321" in plugin.targets


def test_plugin_signal_based_on_feedback(request_mock):
    """NotifySignalAPI() User Feedback Test."""
    body = "test body"
    title = "My Title"

    aobj = Apprise()
    aobj.add(
        "signal://10.0.0.112:8080/+12512222222/+12513333333/"
        "12514444444?batch=yes"
    )

    assert aobj.notify(title=title, body=body)

    # If a batch, there is only 1 post
    assert request_mock.call_count == 1

    details = request_mock.call_args_list[0]
    assert details[0][0] == "http://10.0.0.112:8080/v2/send"
    payload = loads(details[1]["data"])
    assert payload["message"] == "My Title\r\ntest body"
    assert payload["number"] == "+12512222222"
    assert len(payload["recipients"]) == 2
    assert "+12513333333" in payload["recipients"]
    # The + is appended
    assert "+12514444444" in payload["recipients"]

    # Reset our test and turn batch mode off
    request_mock.reset_mock()

    aobj = Apprise()
    aobj.add(
        "signal://10.0.0.112:8080/+12512222222/+12513333333/"
        "12514444444?batch=no"
    )

    assert aobj.notify(title=title, body=body)

    # If a batch, there is only 1 post
    assert request_mock.call_count == 2

    details = request_mock.call_args_list[0]
    assert details[0][0] == "http://10.0.0.112:8080/v2/send"
    payload = loads(details[1]["data"])
    assert payload["message"] == "My Title\r\ntest body"
    assert payload["number"] == "+12512222222"
    assert len(payload["recipients"]) == 1
    assert "+12513333333" in payload["recipients"]

    details = request_mock.call_args_list[1]
    assert details[0][0] == "http://10.0.0.112:8080/v2/send"
    payload = loads(details[1]["data"])
    assert payload["message"] == "My Title\r\ntest body"
    assert payload["number"] == "+12512222222"
    assert len(payload["recipients"]) == 1

    # The + is appended
    assert "+12514444444" in payload["recipients"]

    request_mock.reset_mock()

    # Test group names
    aobj = Apprise()
    aobj.add(
        "signal://10.0.0.112:8080/+12513333333/@group1/@group2/"
        "12514444444?batch=yes"
    )

    assert aobj.notify(title=title, body=body)

    # If a batch, there is only 1 post
    assert request_mock.call_count == 1

    details = request_mock.call_args_list[0]
    assert details[0][0] == "http://10.0.0.112:8080/v2/send"
    payload = loads(details[1]["data"])
    assert payload["message"] == "My Title\r\ntest body"
    assert payload["number"] == "+12513333333"
    assert len(payload["recipients"]) == 3
    assert "+12514444444" in payload["recipients"]
    # our groups
    assert "group.group1" in payload["recipients"]
    assert "group.group2" in payload["recipients"]
    # Groups are stored properly
    assert "/@group1" in aobj[0].url()
    assert "/@group2" in aobj[0].url()
    # Our target phone number is also in the path
    assert "/+12514444444" in aobj[0].url()


def test_notify_signal_plugin_attachments(request_mock):
    """NotifySignalAPI() Attachments."""

    obj = Apprise.instantiate(
        "signal://10.0.0.112:8080/+12512222222/+12513333333/"
        "12514444444?batch=no"
    )
    assert isinstance(obj, NotifySignalAPI)

    # Test Valid Attachment
    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Test invalid attachment
    path = os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=path,
        )
        is False
    )

    # Test Valid Attachment (load 3)
    path = (
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
    )
    attach = AppriseAttachment(path)

    # Return our good configuration
    with mock.patch("builtins.open", side_effect=OSError()):
        # We can't send the message we can't open the attachment for reading
        assert (
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
            is False
        )

    # test the handling of our batch modes
    obj = Apprise.instantiate(
        "signal://10.0.0.112:8080/+12512222222/+12513333333/"
        "12514444444?batch=yes"
    )
    assert isinstance(obj, NotifySignalAPI)

    # Now send an attachment normally without issues
    request_mock.reset_mock()
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )
    assert request_mock.call_count == 1
