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

from apprise.plugins.kavenegar import NotifyKavenegar

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "kavenegar://",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "kavenegar://:@/",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "kavenegar://{}/{}/{}".format("1" * 10, "2" * 15, "a" * 13),
        {
            # valid api key and valid authentication
            "instance": NotifyKavenegar,
            # Since there are no targets specified we expect a False return on
            # send()
            "notify_response": False,
        },
    ),
    (
        "kavenegar://{}/{}".format("a" * 24, "3" * 14),
        {
            # valid api key and valid number
            "instance": NotifyKavenegar,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "kavenegar://a...a/",
        },
    ),
    (
        "kavenegar://{}?to={}".format("a" * 24, "3" * 14),
        {
            # valid api key and valid number
            "instance": NotifyKavenegar,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "kavenegar://a...a/",
        },
    ),
    (
        "kavenegar://{}@{}/{}".format("1" * 14, "b" * 24, "3" * 14),
        {
            # valid api key and valid number
            "instance": NotifyKavenegar,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "kavenegar://{}@b...b/".format("1" * 14),
        },
    ),
    (
        "kavenegar://{}@{}/{}".format("a" * 14, "b" * 24, "3" * 14),
        {
            # invalid from number
            "instance": TypeError,
        },
    ),
    (
        "kavenegar://{}@{}/{}".format("3" * 4, "b" * 24, "3" * 14),
        {
            # invalid from number
            "instance": TypeError,
        },
    ),
    (
        "kavenegar://{}/{}?from={}".format("b" * 24, "3" * 14, "1" * 14),
        {
            # valid api key and valid number
            "instance": NotifyKavenegar,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "kavenegar://{}@b...b/".format("1" * 14),
        },
    ),
    (
        "kavenegar://{}/{}".format("b" * 24, "4" * 14),
        {
            "instance": NotifyKavenegar,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "kavenegar://{}/{}".format("c" * 24, "5" * 14),
        {
            "instance": NotifyKavenegar,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_kavenegar_urls():
    """NotifyKavenegar() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
