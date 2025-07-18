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

from apprise.plugins.dingtalk import NotifyDingTalk

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "dingtalk://",
        {
            # No Access Token specified
            "instance": TypeError,
        },
    ),
    (
        "dingtalk://a_bd_/",
        {
            # invalid Access Token
            "instance": TypeError,
        },
    ),
    (
        "dingtalk://12345678",
        {
            # access token
            "instance": NotifyDingTalk,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "dingtalk://1...8",
        },
    ),
    (
        "dingtalk://{}/{}".format("a" * 8, "1" * 14),
        {
            # access token + phone number
            "instance": NotifyDingTalk,
        },
    ),
    (
        "dingtalk://{}/{}/invalid".format("a" * 8, "1" * 3),
        {
            # access token + 2 invalid phone numbers
            "instance": NotifyDingTalk,
        },
    ),
    (
        "dingtalk://{}/?to={}".format("a" * 8, "1" * 14),
        {
            # access token + phone number using 'to'
            "instance": NotifyDingTalk,
        },
    ),
    # Test secret via user@
    (
        "dingtalk://secret@{}/?to={}".format("a" * 8, "1" * 14),
        {
            # access token + phone number using 'to'
            "instance": NotifyDingTalk,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "dingtalk://****@a...a",
        },
    ),
    # Test secret via secret= and token=
    (
        "dingtalk://?token={}&to={}&secret={}".format(
            "b" * 8, "1" * 14, "a" * 15
        ),
        {
            # access token + phone number using 'to'
            "instance": NotifyDingTalk,
            "privacy_url": "dingtalk://****@b...b",
        },
    ),
    # Invalid secret
    (
        "dingtalk://{}/?to={}&secret=_".format("a" * 8, "1" * 14),
        {
            "instance": TypeError,
        },
    ),
    (
        "dingtalk://{}?format=markdown".format("a" * 8),
        {
            # access token
            "instance": NotifyDingTalk,
        },
    ),
    (
        "dingtalk://{}".format("a" * 8),
        {
            "instance": NotifyDingTalk,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "dingtalk://{}".format("a" * 8),
        {
            "instance": NotifyDingTalk,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_dingtalk_urls():
    """NotifyDingTalk() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
