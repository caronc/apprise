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
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise.plugins.clickatell import NotifyClickatell

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "clickatell://",
        {
            # only schema provided
            "instance": TypeError,
        },
    ),
    (
        "clickatell:///",
        {
            # invalid apikey
            "instance": TypeError,
        },
    ),
    (
        "clickatell://@/",
        {
            # invalid apikey
            "instance": TypeError,
        },
    ),
    (
        "clickatell://{}@/".format("1" * 10),
        {
            # no api key provided
            "instance": TypeError,
        },
    ),
    (
        "clickatell://{}@{}/".format("1" * 3, "a" * 32),
        {
            # invalid From/Source
            "instance": TypeError
        },
    ),
    (
        "clickatell://{}/".format("a" * 32),
        {
            # no targets provided
            "instance": NotifyClickatell,
            # We have no one to notify
            "notify_response": False,
        },
    ),
    (
        "clickatell://{}@{}/".format("1" * 10, "a" * 32),
        {
            # no targets provided (no one to notify)
            "instance": NotifyClickatell,
            # We have no one to notify
            "notify_response": False,
        },
    ),
    (
        "clickatell://{}@{}/123/{}/abcd".format("1" * 10, "a" * 32, "3" * 15),
        {
            # valid everything but target numbers
            "instance": NotifyClickatell,
            # We have no one to notify
            "notify_response": False,
        },
    ),
    (
        "clickatell://{}/{}".format("1" * 10, "a" * 32),
        {
            # everything valid (no source defined)
            "instance": NotifyClickatell,
            # We have no one to notify
            "notify_response": False,
        },
    ),
    (
        "clickatell://{}@{}/{}".format("1" * 10, "a" * 32, "1" * 10),
        {
            # everything valid
            "instance": NotifyClickatell,
        },
    ),
    (
        "clickatell://{}/{}".format("a" * 32, "1" * 10),
        {
            # everything valid (no source)
            "instance": NotifyClickatell,
        },
    ),
    (
        "clickatell://_?apikey={}&from={}&to={},{}".format(
            "a" * 32, "1" * 10, "1" * 10, "1" * 10
        ),
        {
            # use get args to accomplish the same thing
            "instance": NotifyClickatell,
        },
    ),
    (
        "clickatell://_?apikey={}".format("a" * 32),
        {
            # use get args
            "instance": NotifyClickatell,
            "notify_response": False,
        },
    ),
    (
        "clickatell://_?apikey={}&from={}".format("a" * 32, "1" * 10),
        {
            # use get args
            "instance": NotifyClickatell,
            "notify_response": False,
        },
    ),
    (
        "clickatell://{}@{}/{}".format("1" * 10, "a" * 32, "1" * 10),
        {
            "instance": NotifyClickatell,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "clickatell://{}@{}/{}".format("1" * 10, "a" * 32, "1" * 10),
        {
            "instance": NotifyClickatell,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_clickatell_urls():
    """NotifyClickatell() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_clickatell_edge_cases(mock_post):
    """NotifyClickatell() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) apikeys
    apikey = "b" * 32
    from_phone = "+1 (555) 123-3456"

    # No apikey specified
    with pytest.raises(TypeError):
        NotifyClickatell(apikey=None, from_phone=from_phone)

    # a error response
    response.status_code = 400
    response.content = dumps({
        "code": 21211,
        "message": "The 'To' number +1234567 is not a valid phone number.",
    })
    mock_post.return_value = response

    # Initialize our object
    obj = NotifyClickatell(apikey=apikey, from_phone=from_phone)

    # We will fail with the above error code
    assert obj.notify("title", "body", "info") is False
