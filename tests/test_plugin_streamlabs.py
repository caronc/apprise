# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
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
from unittest import mock

from helpers import AppriseURLTester
import requests

import apprise
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.streamlabs import NotifyStreamlabs

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "strmlabs://",
        {
            # No Access Token specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "strmlabs://a_bd_/",
        {
            # invalid Access Token
            "instance": AppriseImproperlyConfigured,
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
            "instance": AppriseImproperlyConfigured,
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
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Test incorrect alert_type
    (
        (
            "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/"
            "?name=tt&identifier=pyt&amount=20&currency=USD&alert_type=rms"
        ),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Test incorrect name
    (
        "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?name=t",
        {
            "instance": AppriseImproperlyConfigured,
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
            # throw a bizarre code forcing us to fail to look it up
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
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=alerts",
        {
            "instance": NotifyStreamlabs,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=donations",
        {
            "instance": NotifyStreamlabs,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_streamlabs_urls():
    """NotifyStreamlabs() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_streamlabs_alert_payload(mock_post):
    """NotifyStreamlabs() alert places title and body correctly."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok

    obj = apprise.Apprise.instantiate(
        "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=alerts"
    )
    assert isinstance(obj, NotifyStreamlabs)

    # Title is the heading and the body is the second line
    assert obj.notify(body="the body", title="the title") is True
    data = mock_post.call_args[1]["data"]
    assert data["message"] == "the title"
    assert data["user_message"] == "the body"
    assert "user_massage" not in data

    # Without a title, the body is the heading so it is still shown
    mock_post.reset_mock()
    assert obj.notify(body="the body") is True
    data = mock_post.call_args[1]["data"]
    assert data["message"] == "the body"
    assert data["user_message"] == ""


@mock.patch("requests.post")
def test_plugin_streamlabs_donation_payload(mock_post):
    """NotifyStreamlabs() donation keeps the title in its message."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok

    obj = apprise.Apprise.instantiate(
        "strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=donations"
    )
    assert isinstance(obj, NotifyStreamlabs)

    # The title leads the message
    assert obj.notify(body="the body", title="the title") is True
    data = mock_post.call_args[1]["data"]
    assert data["message"] == "the title\r\nthe body"

    # Without a title, only the body is sent
    mock_post.reset_mock()
    assert obj.notify(body="the body") is True
    assert mock_post.call_args[1]["data"]["message"] == "the body"

    # The message always stays under 255 characters
    mock_post.reset_mock()
    assert obj.notify(body="b" * 255, title="t" * 20) is True
    assert len(mock_post.call_args[1]["data"]["message"]) == 254
