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

from apprise.plugins.webexteams import NotifyWebexTeams

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "wxteams://",
        {
            # Teams Token missing
            "instance": TypeError,
        },
    ),
    (
        "wxteams://:@/",
        {
            # We don't have strict host checking on for wxteams, so this URL
            # actually becomes parseable and :@ becomes a hostname.
            # The below errors because a second token wasn't found
            "instance": TypeError,
        },
    ),
    (
        "wxteams://{}".format("a" * 80),
        {
            # token provided - we're good
            "instance": NotifyWebexTeams,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "wxteams://a...a/",
        },
    ),
    (
        "wxteams://?token={}".format("a" * 80),
        {
            # token provided - we're good
            "instance": NotifyWebexTeams,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "wxteams://a...a/",
        },
    ),
    (
        "webex://{}".format("a" * 140),
        {
            # token provided - we're good
            "instance": NotifyWebexTeams,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "wxteams://a...a/",
        },
    ),
    # Support Native URLs
    (
        "https://api.ciscospark.com/v1/webhooks/incoming/{}".format("a" * 80),
        {
            # token provided - we're good
            "instance": NotifyWebexTeams,
        },
    ),
    # Support New Native URLs
    (
        "https://webexapis.com/v1/webhooks/incoming/{}".format("a" * 100),
        {
            # token provided - we're good
            "instance": NotifyWebexTeams,
        },
    ),
    # Support Native URLs with arguments
    (
        "https://api.ciscospark.com/v1/webhooks/incoming/{}?format=text"
        .format("a" * 80),
        {
            # token provided - we're good
            "instance": NotifyWebexTeams,
        },
    ),
    (
        "wxteams://{}".format("a" * 80),
        {
            "instance": NotifyWebexTeams,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "wxteams://{}".format("a" * 80),
        {
            "instance": NotifyWebexTeams,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "wxteams://{}".format("a" * 80),
        {
            "instance": NotifyWebexTeams,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_webex_teams_urls():
    """NotifyWebexTeams() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
