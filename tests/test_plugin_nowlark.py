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


from json import loads
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.nowlark import NotifyNowlark

logging.disable(logging.CRITICAL)

KEY = "nlk_" + "a1B2-c3D4_" * 4 + "xyz"

apprise_url_tests = (
    (
        "nowlark://",
        {
            # No API Key
            "instance": TypeError,
        },
    ),
    (
        "nowlark://%20/",
        {
            # Invalid API Key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "nowlark://not-a-key",
        {
            # A key without the nlk_ prefix
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"nowlark://{KEY}",
        {
            "instance": NotifyNowlark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "nowlark://****/Apprise?",
        },
    ),
    (
        f"nowlark://{KEY}/Nightly%20backup?priority=high",
        {
            "instance": NotifyNowlark,
        },
    ),
    (
        f"nowlark://?key={KEY}&source=Backups&priority=-2",
        {
            "instance": NotifyNowlark,
        },
    ),
    (
        f"nowlark://{KEY}/Backups?priority=invalid",
        {
            # An unknown priority falls back to normal
            "instance": NotifyNowlark,
        },
    ),
    (
        f"nowlark://{KEY}/Backups?url=https://example.com/run/42",
        {
            "instance": NotifyNowlark,
        },
    ),
    (
        f"nowlark://{KEY}/Backups?url=ftp://example.com",
        {
            # Nowlark accepts only http and https links
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"nowlark://{KEY}/{'s' * 257}",
        {
            # Nowlark's source is at most 256 characters
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"nowlark://{KEY}",
        {
            "instance": NotifyNowlark,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"nowlark://{KEY}",
        {
            "instance": NotifyNowlark,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_nowlark_urls():
    """NotifyNowlark() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@pytest.mark.parametrize(
    "given,expected",
    [
        ("low", -2),
        ("moderate", -1),
        ("normal", 0),
        ("high", 1),
        ("emergency", 2),
        ("-2", -2),
        ("2", 2),
        (None, 0),
        ("nonsense", 0),
    ],
)
def test_plugin_nowlark_priority(given, expected):
    """A priority by name or by Nowlark's own -2 to 2 number."""
    assert NotifyNowlark(apikey=KEY, priority=given).priority == expected


@mock.patch("requests.post")
def test_plugin_nowlark_payload(mock_post):
    """The request is the one Nowlark's API documents."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b'{"id":"n_1"}'
    mock_post.return_value = response

    apobj = Apprise()
    assert apobj.add(
        f"nowlark://{KEY}/Nightly%20backup?priority=emergency"
        "&url=https://example.com/run/42"
    )
    assert bool(apobj.notify(title="Backup failed", body="Disk full")) is True

    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    assert url == "https://nowlark.com/v1/notify"
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == f"Bearer {KEY}"
    assert loads(mock_post.call_args[1]["data"]) == {
        "source": "Nightly backup",
        "priority": 2,
        "title": "Backup failed",
        "body": "Disk full",
        "url": "https://example.com/run/42",
    }

    # The URL round trips
    obj = Apprise.instantiate(apobj[0].url())
    assert isinstance(obj, NotifyNowlark)
    assert obj.source == "Nightly backup"
    assert obj.priority == 2
    assert obj.click == "https://example.com/run/42"
    assert len(obj) == 1
