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

from apprise.plugins.line import NotifyLine

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "line://",
        {
            # No Access Token
            "instance": TypeError,
        },
    ),
    (
        "line://%20/",
        {
            # invalid Access Token; no Integration/Routing Key
            "instance": TypeError,
        },
    ),
    (
        "line://token",
        {
            # no target specified
            "instance": NotifyLine,
            # Expected notify() response
            "notify_response": False,
        },
    ),
    (
        "line://token=/target",
        {
            # minimum requirements met
            "instance": NotifyLine,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "line://****/t...t?",
        },
    ),
    (
        "line://token/target?image=no",
        {
            # minimum requirements met; no icon display
            "instance": NotifyLine,
        },
    ),
    (
        "line://a/very/long/token=/target?image=no",
        {
            # minimum requirements met; no icon display
            "instance": NotifyLine,
        },
    ),
    (
        "line://?token=token&to=target1",
        {
            # minimum requirements met
            "instance": NotifyLine,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "line://****/t...1?",
        },
    ),
    (
        "line://token/target",
        {
            "instance": NotifyLine,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "line://token/target",
        {
            "instance": NotifyLine,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_line_urls():
    """NotifyLine() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
