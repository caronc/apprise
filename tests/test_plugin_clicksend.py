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

from apprise.plugins.clicksend import NotifyClickSend

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "clicksend://",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "clicksend://:@/",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "clicksend://user:pass@{}/{}/{}".format("1" * 9, "2" * 15, "a" * 13),
        {
            # invalid target numbers; we'll fail to notify anyone
            "instance": NotifyClickSend,
            "notify_response": False,
        },
    ),
    (
        "clicksend://user:pass@{}?batch=yes".format("3" * 14),
        {
            # valid number
            "instance": NotifyClickSend,
        },
    ),
    (
        "clicksend://user:pass@{}?batch=yes&to={}".format("3" * 14, "6" * 14),
        {
            # valid number but using the to= variable
            "instance": NotifyClickSend,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "clicksend://user:****",
        },
    ),
    (
        "clicksend://user:pass@{}?batch=no".format("3" * 14),
        {
            # valid number - no batch
            "instance": NotifyClickSend,
        },
    ),
    (
        "clicksend://user@{}?batch=no&key=abc123".format("3" * 14),
        {
            # valid number - no batch
            "instance": NotifyClickSend,
        },
    ),
    (
        "clicksend://user:pass@{}".format("3" * 14),
        {
            "instance": NotifyClickSend,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "clicksend://user:pass@{}".format("3" * 14),
        {
            "instance": NotifyClickSend,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_clicksend_urls():
    """NotifyClickSend() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
