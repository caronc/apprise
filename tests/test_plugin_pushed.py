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

from apprise.plugins.pushed import NotifyPushed

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "pushed://",
        {
            "instance": TypeError,
        },
    ),
    # Application Key Only
    (
        "pushed://%s" % ("a" * 32),
        {
            "instance": TypeError,
        },
    ),
    # Invalid URL
    (
        "pushed://:@/",
        {
            "instance": TypeError,
        },
    ),
    # Application Key+Secret
    (
        "pushed://{}/{}".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
        },
    ),
    # Application Key+Secret + channel
    (
        "pushed://{}/{}/#channel/".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
        },
    ),
    # Application Key+Secret + channel (via to=)
    (
        "pushed://{}/{}?to=channel".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pushed://a...a/****/",
        },
    ),
    # Application Key+Secret + dropped entry
    (
        "pushed://{}/{}/dropped_value/".format("a" * 32, "a" * 64),
        {
            # No entries validated is a fail
            "instance": TypeError,
        },
    ),
    # Application Key+Secret + 2 channels
    (
        "pushed://{}/{}/#channel1/#channel2".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
        },
    ),
    # Application Key+Secret + User Pushed ID
    (
        "pushed://{}/{}/@ABCD/".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
        },
    ),
    # Application Key+Secret + 2 devices
    (
        "pushed://{}/{}/@ABCD/@DEFG/".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
        },
    ),
    # Application Key+Secret + Combo
    (
        "pushed://{}/{}/@ABCD/#channel".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
        },
    ),
    # ,
    (
        "pushed://{}/{}".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "pushed://{}/{}".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "pushed://{}/{}".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "pushed://{}/{}".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "pushed://{}/{}".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "pushed://{}/{}/#channel".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "pushed://{}/{}/@user".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "pushed://{}/{}".format("a" * 32, "a" * 64),
        {
            "instance": NotifyPushed,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_pushed_urls():
    """NotifyPushed() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_pushed_edge_cases(mock_post, mock_get):
    """NotifyPushed() Edge Cases."""

    # Chat ID
    recipients = "@ABCDEFG, @DEFGHIJ, #channel, #channel2"

    # Some required input
    app_key = "ABCDEFG"
    app_secret = "ABCDEFG"

    # Prepare Mock
    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok

    # No application Key specified
    with pytest.raises(TypeError):
        NotifyPushed(
            app_key=None,
            app_secret=app_secret,
            recipients=None,
        )

    with pytest.raises(TypeError):
        NotifyPushed(
            app_key="  ",
            app_secret=app_secret,
            recipients=None,
        )
    # No application Secret specified
    with pytest.raises(TypeError):
        NotifyPushed(
            app_key=app_key,
            app_secret=None,
            recipients=None,
        )

    with pytest.raises(TypeError):
        NotifyPushed(
            app_key=app_key,
            app_secret="   ",
        )

    # recipients list set to (None) is perfectly fine; in this case it will
    # notify the App
    obj = NotifyPushed(
        app_key=app_key,
        app_secret=app_secret,
        recipients=None,
    )
    assert isinstance(obj, NotifyPushed) is True
    assert len(obj.channels) == 0
    assert len(obj.users) == 0

    obj = NotifyPushed(
        app_key=app_key,
        app_secret=app_secret,
        targets=recipients,
    )
    assert isinstance(obj, NotifyPushed) is True
    assert len(obj.channels) == 2
    assert len(obj.users) == 2

    # Prepare Mock to fail
    mock_post.return_value.status_code = requests.codes.internal_server_error
    mock_get.return_value.status_code = requests.codes.internal_server_error
