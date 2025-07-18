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

from apprise.plugins.kumulos import NotifyKumulos

logging.disable(logging.CRITICAL)

# a test UUID we can use
UUID4 = "8b799edf-6f98-4d3a-9be7-2862fb4e5752"

# Our Testing URLs
apprise_url_tests = (
    (
        "kumulos://",
        {
            # No API or Server Key specified
            "instance": TypeError,
        },
    ),
    (
        "kumulos://:@/",
        {
            # No API or Server Key specified
            # We don't have strict host checking on for kumulos, so this URL
            # actually becomes parseable and :@ becomes a hostname.
            # The below errors because a second token wasn't found
            "instance": TypeError,
        },
    ),
    (
        f"kumulos://{UUID4}/",
        {
            # No server key was specified
            "instance": TypeError,
        },
    ),
    (
        "kumulos://{}/{}/".format(UUID4, "w" * 36),
        {
            # Everything is okay
            "instance": NotifyKumulos,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "kumulos://8...2/w...w/",
        },
    ),
    (
        "kumulos://{}/{}/".format(UUID4, "x" * 36),
        {
            "instance": NotifyKumulos,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "kumulos://8...2/x...x/",
        },
    ),
    (
        "kumulos://{}/{}/".format(UUID4, "y" * 36),
        {
            "instance": NotifyKumulos,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "kumulos://8...2/y...y/",
        },
    ),
    (
        "kumulos://{}/{}/".format(UUID4, "z" * 36),
        {
            "instance": NotifyKumulos,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_kumulos_urls():
    """NotifyKumulos() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_kumulos_edge_cases():
    """NotifyKumulos() Edge Cases."""

    # Invalid API Key
    with pytest.raises(TypeError):
        NotifyKumulos(None, None)
    with pytest.raises(TypeError):
        NotifyKumulos("     ", None)

    # Invalid Server Key
    with pytest.raises(TypeError):
        NotifyKumulos("abcd", None)
    with pytest.raises(TypeError):
        NotifyKumulos("abcd", "       ")
