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

from apprise.plugins.streamlabs import NotifyStreamlabs

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "strmlabs://",
        {
            # No Access Token specified
            "instance": TypeError,
        },
    ),
    (
        "strmlabs://a_bd_/",
        {
            # invalid Access Token
            "instance": TypeError,
        },
    ),
    (
        "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso",
        {
            # access token
            "instance": NotifyStreamlabs,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "strmlabs://I...o",
        },
    ),
    # Test incorrect currency
    (
        "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?currency=ABCD",
        {
            "instance": TypeError,
        },
    ),
    # Test complete params - donations
    (
        (
            "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/"
            "?name=tt&identifier=pyt&amount=20&currency=USD&call=donations"
        ),
        {
            "instance": NotifyStreamlabs,
        },
    ),
    # Test complete params - donations
    (
        (
            "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/"
            "?image_href=https://example.org/rms.jpg"
            "&sound_href=https://example.org/rms.mp3"
        ),
        {
            "instance": NotifyStreamlabs,
        },
    ),
    # Test complete params - alerts
    (
        (
            "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/"
            "?duration=1000&image_href=&"
            "sound_href=&alert_type=donation&special_text_color=crimson"
        ),
        {
            "instance": NotifyStreamlabs,
        },
    ),
    # Test incorrect call
    (
        (
            "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/"
            "?name=tt&identifier=pyt&amount=20&currency=USD&call=rms"
        ),
        {
            "instance": TypeError,
        },
    ),
    # Test incorrect alert_type
    (
        (
            "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/"
            "?name=tt&identifier=pyt&amount=20&currency=USD&alert_type=rms"
        ),
        {
            "instance": TypeError,
        },
    ),
    # Test incorrect name
    (
        "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?name=t",
        {
            "instance": TypeError,
        },
    ),
    (
        "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=donations",
        {
            "instance": NotifyStreamlabs,
            # A failure has status set to zero
            # Test without an 'error' flag
            "requests_response_text": {
                "status": 0,
            },
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=alerts",
        {
            "instance": NotifyStreamlabs,
            # A failure has status set to zero
            # Test without an 'error' flag
            "requests_response_text": {
                "status": 0,
            },
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=alerts",
        {
            "instance": NotifyStreamlabs,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=donations",
        {
            "instance": NotifyStreamlabs,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_streamlabs_urls():
    """NotifyStreamlabs() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
