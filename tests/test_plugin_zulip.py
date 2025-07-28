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

from helpers import AppriseURLTester
import pytest
import requests

from apprise.plugins.zulip import NotifyZulip

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "zulip://",
        {
            "instance": TypeError,
        },
    ),
    (
        "zulip://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "zulip://apprise",
        {
            # Just org provided (no token or botname)
            "instance": TypeError,
        },
    ),
    (
        "zulip://botname@apprise",
        {
            # Just org and botname provided (no token)
            "instance": TypeError,
        },
    ),
    # invalid token
    (
        "zulip://botname@apprise/{}".format("a" * 24),
        {
            "instance": TypeError,
        },
    ),
    # invalid botname
    (
        "zulip://....@apprise/{}".format("a" * 32),
        {
            "instance": TypeError,
        },
    ),
    # Valid everything - botname with a dash
    (
        "zulip://bot-name@apprise/{}".format("a" * 32),
        {
            "instance": NotifyZulip,
            "privacy_url": "zulip://bot-name@apprise/a...a/",
        },
    ),
    # Valid everything - no target so default is used
    (
        "zulip://botname@apprise/{}".format("a" * 32),
        {
            "instance": NotifyZulip,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "zulip://botname@apprise/a...a/",
        },
    ),
    # Valid everything - organization as hostname
    (
        "zulip://botname@apprise.zulipchat.com/{}".format("a" * 32),
        {
            "instance": NotifyZulip,
        },
    ),
    # Valid everything - 2 streams specified
    (
        "zulip://botname@apprise/{}/channel1/channel2".format("a" * 32),
        {
            "instance": NotifyZulip,
        },
    ),
    # Valid everything - 2 streams specified (using to=)
    (
        "zulip://botname@apprise/{}/?to=channel1/channel2".format("a" * 32),
        {
            "instance": NotifyZulip,
        },
    ),
    # Test token=
    (
        "zulip://botname@apprise/?token={}&to=channel1".format("a" * 32),
        {
            "instance": NotifyZulip,
        },
    ),
    # Valid everything - 2 emails specified
    (
        "zulip://botname@apprise/{}/user@example.com/user2@example.com".format(
            "a" * 32
        ),
        {
            "instance": NotifyZulip,
        },
    ),
    (
        "zulip://botname@apprise/{}".format("a" * 32),
        {
            "instance": NotifyZulip,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "zulip://botname@apprise/{}".format("a" * 32),
        {
            "instance": NotifyZulip,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "zulip://botname@apprise/{}".format("a" * 32),
        {
            "instance": NotifyZulip,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "zulip://botname@apprise/{}".format("a" * 32),
        {
            "instance": NotifyZulip,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_zulip_urls():
    """NotifyZulip() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_zulip_edge_cases():
    """NotifyZulip() Edge Cases."""

    # must be 32 characters long
    token = "a" * 32

    # Invalid organization
    with pytest.raises(TypeError):
        NotifyZulip(botname="test", organization="#", token=token)
