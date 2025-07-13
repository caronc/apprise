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
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise.plugins.threema import NotifyThreema

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "threema://",
        {
            # No user/secret specified
            "instance": TypeError,
        },
    ),
    (
        "threema://@:",
        {
            # Invalid url
            "instance": TypeError,
        },
    ),
    (
        "threema://user@secret",
        {
            # gateway id must be 8 characters in len
            "instance": TypeError,
        },
    ),
    (
        "threema://*THEGWID@secret/{targets}/".format(
            targets="/".join(["2222"])
        ),
        {
            # Invalid target phone number
            "instance": NotifyThreema,
            "notify_response": False,
            "privacy_url": "threema://%2ATHEGWID@****/2222",
        },
    ),
    (
        "threema://*THEGWID@secret/{targets}/".format(
            targets="/".join(["16134442222"])
        ),
        {
            # Valid
            "instance": NotifyThreema,
            "privacy_url": "threema://%2ATHEGWID@****/16134442222",
        },
    ),
    (
        "threema://*THEGWID@secret/{targets}/".format(
            targets="/".join(["16134442222", "16134443333"])
        ),
        {
            # Valid multiple targets
            "instance": NotifyThreema,
            "privacy_url": "threema://%2ATHEGWID@****/16134442222/16134443333",
        },
    ),
    (
        "threema:///?secret=secret&from=*THEGWID&to={targets}".format(
            targets=",".join(["16134448888", "user1@gmail.com", "abcd1234"])
        ),
        {
            # Valid
            "instance": NotifyThreema,
        },
    ),
    (
        "threema:///?secret=secret&gwid=*THEGWID&to={targets}".format(
            targets=",".join(["16134448888", "user2@gmail.com", "abcd1234"])
        ),
        {
            # Valid
            "instance": NotifyThreema,
        },
    ),
    (
        "threema://*THEGWID@secret",
        {
            "instance": NotifyThreema,
            # No targets specified
            "notify_response": False,
        },
    ),
    (
        "threema://*THEGWID@secret/16134443333",
        {
            "instance": NotifyThreema,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "threema://*THEGWID@secret/16134443333",
        {
            "instance": NotifyThreema,
            # Throws a series of errors
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_threema():
    """NotifyThreema() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_threema_edge_cases(mock_post):
    """NotifyThreema() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    gwid = "*THEGWID"
    secret = "mysecret"
    targets = "+1 (555) 123-9876"

    # No email specified
    with pytest.raises(TypeError):
        NotifyThreema(user=gwid, secret=None, targets=targets)

    results = NotifyThreema.parse_url(
        f"threema://?gwid={gwid}&secret={secret}&to={targets}"
    )

    assert isinstance(results, dict)
    assert results["user"] == gwid
    assert results["secret"] == secret
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == ""
    assert results["fullpath"] == "/"
    assert results["path"] == "/"
    assert results["query"] is None
    assert results["schema"] == "threema"
    assert results["url"] == "threema:///"
    assert isinstance(results["targets"], list)
    assert len(results["targets"]) == 1
    assert results["targets"][0] == targets

    instance = NotifyThreema(**results)
    assert len(instance.targets) == 1
    assert instance.targets[0] == ("phone", "15551239876")
    assert isinstance(instance, NotifyThreema)

    response = instance.send(title="title", body="body 😊")
    assert response is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == "https://msgapi.threema.ch/send_simple"
    assert details[1]["headers"]["User-Agent"] == "Apprise"
    assert details[1]["headers"]["Accept"] == "*/*"
    assert (
        details[1]["headers"]["Content-Type"]
        == "application/x-www-form-urlencoded; charset=utf-8"
    )
    assert details[1]["params"]["secret"] == secret
    assert details[1]["params"]["from"] == gwid
    assert details[1]["params"]["phone"] == "15551239876"
    assert details[1]["params"]["text"] == "body 😊".encode()
