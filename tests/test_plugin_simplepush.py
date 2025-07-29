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

import json

# Disable logging for a cleaner testing output
import logging
import sys
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.simplepush import NotifySimplePush

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "spush://",
        {
            # No api key
            "instance": TypeError,
        },
    ),
    (
        "spush://{}".format("A" * 14),
        {
            # API Key specified however expected server response
            # didn't have 'OK' in JSON response
            "instance": NotifySimplePush,
            # Expected notify() response
            "notify_response": False,
        },
    ),
    (
        "spush://{}".format("Y" * 14),
        {
            # API Key valid and expected response was valid
            "instance": NotifySimplePush,
            # Set our response to OK
            "requests_response_text": {
                "status": "OK",
            },
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "spush://Y...Y/",
        },
    ),
    (
        "spush://{}?event=Not%20So%20Good".format("X" * 14),
        {
            # API Key valid and expected response was valid
            "instance": NotifySimplePush,
            # Set our response to something that is not okay
            "requests_response_text": {
                "status": "NOT-OK",
            },
            # Expected notify() response
            "notify_response": False,
        },
    ),
    (
        "spush://salt:pass@{}".format("X" * 14),
        {
            # Now we'll test encrypted messages with new salt
            "instance": NotifySimplePush,
            # Set our response to OK
            "requests_response_text": {
                "status": "OK",
            },
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "spush://****:****@X...X/",
        },
    ),
    (
        "spush://{}".format("Y" * 14),
        {
            "instance": NotifySimplePush,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
            # Set a failing message too
            "requests_response_text": {
                "status": "BadRequest",
                "message": "Title or message too long",
            },
        },
    ),
    (
        "spush://{}".format("Z" * 14),
        {
            "instance": NotifySimplePush,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_simplepush_urls():
    """NotifySimplePush() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@pytest.mark.skipif(
    "cryptography" in sys.modules,
    reason="Requires that cryptography NOT be installed")
def test_plugin_simpepush_cryptography_import_error():
    """
    NotifySimplePush() Cryptography loading failure
    """

    # Attempt to instantiate our object
    obj = Apprise.instantiate("spush://{}".format("Y" * 14))

    # It's not possible because our cryptography depedancy is missing
    assert obj is None


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography")
def test_plugin_simplepush_edge_cases():
    """
    NotifySimplePush() Edge Cases

    """

    # No token
    with pytest.raises(TypeError):
        NotifySimplePush(apikey=None)

    with pytest.raises(TypeError):
        NotifySimplePush(apikey="  ")

    # Bad event
    with pytest.raises(TypeError):
        NotifySimplePush(apikey="abc", event=object)

    with pytest.raises(TypeError):
        NotifySimplePush(apikey="abc", event="  ")


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@mock.patch("requests.post")
def test_plugin_simplepush_general(mock_post):
    """NotifySimplePush() General Tests."""

    # Prepare a good response
    response = mock.Mock()
    response.content = json.dumps({
        "status": "OK",
    })
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = Apprise.instantiate("spush://{}".format("Y" * 14))

    # Verify our content works as expected
    assert obj.notify(title="test", body="test") is True
