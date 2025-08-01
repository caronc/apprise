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
# POSSIBILITY OF SUCH DAMAGE.# BSD 2-Clause License

from json import dumps

# Disable logging for a cleaner testing output
import logging

from helpers import AppriseURLTester

from apprise.plugins.signl4 import (
    NotifySIGNL4,
    NotifyType,
)

logging.disable(logging.CRITICAL)

SIGNL4_GOOD_RESPONSE = dumps({
    "eventId": "2516485120936941747_76d5cf30-27d2-4529-84ed-f31a8f2c72b1",
})

# Our Testing URLs
apprise_url_tests = (
    (
        "signl4://",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "signl4://:@/",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "signl4://%20%20/",
        {
            # invalid secret specified
            "instance": TypeError,
        },
    ),
    (
        "signl4://secret/",
        {
            # No targets specified; this is allowed
            "instance": NotifySIGNL4,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": SIGNL4_GOOD_RESPONSE,
        },
    ),
    (
        "signl4://?secret=secret",
        {
            # No targets specified; this is allowed
            "instance": NotifySIGNL4,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": SIGNL4_GOOD_RESPONSE,
        },
    ),
    (
        "signl4://secret/?service=IoT",
        {
            # European Region
            "instance": NotifySIGNL4,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": SIGNL4_GOOD_RESPONSE,
        },
    ),
    (
        "signl4://secret/?filtering=yes",
        {
            # European Region
            "instance": NotifySIGNL4,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": SIGNL4_GOOD_RESPONSE,
        },
    ),
    (
        "signl4://secret/?location=40.6413111,-73.7781391",
        {
            # European Region
            "instance": NotifySIGNL4,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": SIGNL4_GOOD_RESPONSE,
        },
    ),
    (
        "signl4://secret/?alerting_scenario=singl4_ack",
        {
            # European Region
            "instance": NotifySIGNL4,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": SIGNL4_GOOD_RESPONSE,
        },
    ),
    (
        "signl4://secret/?filtering=False",
        {
            # European Region
            "instance": NotifySIGNL4,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": SIGNL4_GOOD_RESPONSE,
        },
    ),
        (
        "signl4://secret/?external_id=ar1234&status=new",
        {
            # European Region
            "instance": NotifySIGNL4,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": SIGNL4_GOOD_RESPONSE,
        },
    ),
    (
        "signl4://secret/",
        {
            "instance": NotifySIGNL4,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "signl4://secret/",
        {
            "instance": NotifySIGNL4,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)

def test_plugin_signl4_urls():
    """NotifySIGNL4() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
