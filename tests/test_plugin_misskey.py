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
import os

from helpers import AppriseURLTester

from apprise.plugins.misskey import NotifyMisskey

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyMisskey
    ##################################
    (
        "misskey://",
        {
            # Missing Everything :)
            "instance": None,
        },
    ),
    (
        "misskey://:@/",
        {
            "instance": None,
        },
    ),
    (
        "misskey://hostname",
        {
            # Missing Access Token
            "instance": TypeError,
        },
    ),
    (
        "misskey://access_token@hostname",
        {
            # We're good; it's a simple notification
            "instance": NotifyMisskey,
        },
    ),
    (
        "misskeys://access_token@hostname",
        {
            # We're good; it's another simple notification
            "instance": NotifyMisskey,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "misskeys://a...n@hostname/",
        },
    ),
    (
        "misskey://hostname/?token=abcd123",
        {
            # Our access token can be provided as a token= variable
            "instance": NotifyMisskey,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "misskey://a...3@hostname",
        },
    ),
    (
        "misskeys://access_token@hostname:8443",
        {
            # A custom port specified
            "instance": NotifyMisskey,
        },
    ),
    (
        "misskey://access_token@hostname?visibility=invalid",
        {
            # An invalid visibility
            "instance": TypeError,
        },
    ),
    (
        "misskeys://access_token@hostname?visibility=specified",
        {
            # Specified a different visiblity
            "instance": NotifyMisskey,
        },
    ),
    (
        "misskeys://access_token@hostname",
        {
            "instance": NotifyMisskey,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "misskeys://access_token@hostname",
        {
            "instance": NotifyMisskey,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_misskey_urls():
    """NotifyMisskey() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
