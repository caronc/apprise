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

from apprise.plugins.flock import NotifyFlock

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "flock://",
        {
            "instance": TypeError,
        },
    ),
    # An invalid url
    (
        "flock://:@/",
        {
            "instance": TypeError,
        },
    ),
    # Provide a token
    (
        "flock://%s" % ("t" * 24),
        {
            "instance": NotifyFlock,
        },
    ),
    # Image handling
    (
        "flock://%s?image=True" % ("t" * 24),
        {
            "instance": NotifyFlock,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "flock://t...t",
        },
    ),
    (
        "flock://%s?image=False" % ("t" * 24),
        {
            "instance": NotifyFlock,
        },
    ),
    (
        "flock://%s?image=True" % ("t" * 24),
        {
            "instance": NotifyFlock,
            # Run test when image is set to True, but one couldn't actually be
            # loaded from the Asset Object.
            "include_image": False,
        },
    ),
    # Test to=
    (
        "flock://{}?to=u:{}&format=markdown".format("i" * 24, "u" * 12),
        {
            "instance": NotifyFlock,
        },
    ),
    # Provide markdown format
    (
        "flock://%s?format=markdown" % ("i" * 24),
        {
            "instance": NotifyFlock,
        },
    ),
    # Provide text format
    (
        "flock://%s?format=text" % ("i" * 24),
        {
            "instance": NotifyFlock,
        },
    ),
    # Native URL Support, take the slack URL and still build from it
    (
        "https://api.flock.com/hooks/sendMessage/{}/".format("i" * 24),
        {
            "instance": NotifyFlock,
        },
    ),
    # Native URL Support with arguments
    (
        "https://api.flock.com/hooks/sendMessage/{}/?format=markdown".format(
            "i" * 24
        ),
        {
            "instance": NotifyFlock,
        },
    ),
    # Bot API presumed if one or more targets are specified
    # Provide markdown format
    (
        "flock://{}/u:{}?format=markdown".format("i" * 24, "u" * 12),
        {
            "instance": NotifyFlock,
        },
    ),
    # Bot API presumed if one or more targets are specified
    # Provide text format
    (
        "flock://{}/u:{}?format=html".format("i" * 24, "u" * 12),
        {
            "instance": NotifyFlock,
        },
    ),
    # Bot API presumed if one or more targets are specified
    # u: is optional
    (
        "flock://{}/{}?format=text".format("i" * 24, "u" * 12),
        {
            "instance": NotifyFlock,
        },
    ),
    # Bot API presumed if one or more targets are specified
    # Multi-entries
    (
        "flock://{}/g:{}/u:{}?format=text".format(
            "i" * 24, "g" * 12, "u" * 12
        ),
        {
            "instance": NotifyFlock,
        },
    ),
    # Bot API presumed if one or more targets are specified
    # Multi-entries using @ for user and # for channel
    (
        "flock://{}/#{}/@{}?format=text".format("i" * 24, "g" * 12, "u" * 12),
        {
            "instance": NotifyFlock,
        },
    ),
    # Bot API presumed if one or more targets are specified
    # has bad entry
    (
        "flock://{}/g:{}/u:{}?format=text".format(
            "i" * 24, "g" * 12, "u" * 10
        ),
        {
            "instance": NotifyFlock,
        },
    ),
    # Invalid user/group defined
    (
        "flock://%s/g:/u:?format=text" % ("i" * 24),
        {
            "instance": TypeError,
        },
    ),
    # we don't focus on the invalid length of the user/group fields.
    # As a result, the following will load and pass the data upstream
    (
        "flock://{}/g:{}/u:{}?format=text".format(
            "i" * 24, "g" * 14, "u" * 10
        ),
        {
            # We will still instantiate the object
            "instance": NotifyFlock,
        },
    ),
    # Error Testing
    (
        "flock://{}/g:{}/u:{}?format=text".format(
            "i" * 24, "g" * 12, "u" * 10
        ),
        {
            "instance": NotifyFlock,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "flock://%s/" % ("t" * 24),
        {
            "instance": NotifyFlock,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "flock://%s/" % ("t" * 24),
        {
            "instance": NotifyFlock,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "flock://%s/" % ("t" * 24),
        {
            "instance": NotifyFlock,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_flock_urls():
    """NotifyFlock() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_flock_edge_cases(mock_post, mock_get):
    """NotifyFlock() Edge Cases."""

    # Initializes the plugin with an invalid token
    with pytest.raises(TypeError):
        NotifyFlock(token=None)
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyFlock(token="   ")
