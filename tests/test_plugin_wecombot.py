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
import requests

from apprise.plugins.wecombot import NotifyWeComBot

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "wecombot://",
        {
            "instance": TypeError,
        },
    ),
    (
        "wecombot://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "wecombot://botkey",
        {
            # Minimum requirements met
            "instance": NotifyWeComBot,
        },
    ),
    (
        "wecombot://?key=botkey",
        {
            # Test ?key=
            "instance": NotifyWeComBot,
        },
    ),
    # Support Native URLs
    (
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=BOTKEY",
        {
            "instance": NotifyWeComBot,
        },
    ),
    (
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send/?key=BOTKEY&data=123",
        {
            # another variation (more parameters don't obstruct our key)
            "instance": NotifyWeComBot,
        },
    ),
    (
        "wecombot://botkey",
        {
            "instance": NotifyWeComBot,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "wecombot://botkey",
        {
            "instance": NotifyWeComBot,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "wecombot://botkey",
        {
            "instance": NotifyWeComBot,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_wecombot_urls():
    """NotifyWeComBot() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
