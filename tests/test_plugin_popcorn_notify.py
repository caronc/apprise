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

from apprise.plugins.popcorn_notify import NotifyPopcornNotify

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "popcorn://",
        {
            # No hostname/apikey specified
            "instance": TypeError,
        },
    ),
    (
        "popcorn://{}/18001231234".format("_" * 9),
        {
            # invalid apikey
            "instance": TypeError,
        },
    ),
    (
        "popcorn://{}/1232348923489234923489234289-32423".format("a" * 9),
        {
            # invalid phone number
            "instance": NotifyPopcornNotify,
            "notify_response": False,
        },
    ),
    (
        "popcorn://{}/abc".format("b" * 9),
        {
            # invalid email
            "instance": NotifyPopcornNotify,
            "notify_response": False,
        },
    ),
    (
        "popcorn://{}/15551232000/user@example.com".format("c" * 9),
        {
            # value phone and email
            "instance": NotifyPopcornNotify,
        },
    ),
    (
        "popcorn://{}/15551232000/user@example.com?batch=yes".format("w" * 9),
        {
            # value phone and email with batch mode set
            "instance": NotifyPopcornNotify,
        },
    ),
    (
        "popcorn://{}/?to=15551232000".format("w" * 9),
        {
            # reference to to=
            "instance": NotifyPopcornNotify,
        },
    ),
    (
        "popcorn://{}/15551232000".format("x" * 9),
        {
            "instance": NotifyPopcornNotify,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "popcorn://{}/15551232000".format("y" * 9),
        {
            "instance": NotifyPopcornNotify,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "popcorn://{}/15551232000".format("z" * 9),
        {
            "instance": NotifyPopcornNotify,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_popcorn_notify_urls():
    """NotifyPopcornNotify() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
