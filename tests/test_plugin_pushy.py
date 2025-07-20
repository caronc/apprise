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

from apprise.plugins.pushy import NotifyPushy

logging.disable(logging.CRITICAL)


# However we'll be okay if we return a proper response
GOOD_RESPONSE = {
    "success": True,
}

# Our Testing URLs
apprise_url_tests = (
    (
        "pushy://",
        {
            # No no secret api key
            "instance": TypeError,
        },
    ),
    (
        "pushy://:@/",
        {
            # just invalid all around
            "instance": TypeError,
        },
    ),
    (
        "pushy://apikey",
        {
            # No Device/Topic specified
            "instance": NotifyPushy,
            # Expected notify() response False (because we won't be able
            # to actually notify anything if no device_key was specified
            "notify_response": False,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "pushy://apikey/topic",
        {
            # No Device/Topic specified
            "instance": NotifyPushy,
            # Expected notify() response False because the success flag
            # was set to false
            "notify_response": False,
            "requests_response_text": {"success": False},
        },
    ),
    (
        "pushy://apikey/topic",
        {
            # No Device/Topic specified
            "instance": NotifyPushy,
            # Expected notify() response False because the success flag
            # was set to false
            "notify_response": False,
            # Invalid JSON data
            "requests_response_text": "}",
        },
    ),
    (
        "pushy://apikey/%20(",
        {
            # Invalid topic specified
            "instance": NotifyPushy,
            # Expected notify() response False because there is no one to
            # notify
            "notify_response": False,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "pushy://apikey/@device",
        {
            # Everything is okay
            "instance": NotifyPushy,
            "requests_response_text": GOOD_RESPONSE,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pushy://a...y/@device/",
        },
    ),
    (
        "pushy://apikey/topic",
        {
            # Everything is okay; no prefix means it's a topic
            "instance": NotifyPushy,
            "requests_response_text": GOOD_RESPONSE,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pushy://a...y/#topic/",
        },
    ),
    (
        "pushy://apikey/device/?sound=alarm.aiff",
        {
            # alarm.aiff sound loaded
            "instance": NotifyPushy,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "pushy://apikey/device/?badge=100",
        {
            # set badge
            "instance": NotifyPushy,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "pushy://apikey/device/?badge=invalid",
        {
            # set invalid badge
            "instance": NotifyPushy,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "pushy://apikey/device/?badge=-12",
        {
            # set invalid badge
            "instance": NotifyPushy,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "pushy://_/@device/#topic?key=apikey",
        {
            # set device and topic
            "instance": NotifyPushy,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "pushy://apikey/?to=@device",
        {
            # test use of to= argument
            "instance": NotifyPushy,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    (
        "pushy://_/@device/#topic?key=apikey",
        {
            "instance": NotifyPushy,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
            "requests_response_text": GOOD_RESPONSE,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pushy://a...y/#topic/@device/",
        },
    ),
    (
        "pushy://_/@device/#topic?key=apikey",
        {
            "instance": NotifyPushy,
            "requests_response_text": GOOD_RESPONSE,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_pushy_urls():
    """NotifyPushy() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
