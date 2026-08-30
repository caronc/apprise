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
from unittest.mock import Mock, patch

from helpers import AppriseURLTester
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.lauther import LautherPriority, NotifyLauther

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "lauther://",
        {
            # No token specified
            "instance": TypeError,
        },
    ),
    (
        "lauther://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "lauther://%badtoken%",
        {
            # Not a valid token
            "instance": TypeError,
        },
    ),
    (
        "lauther://abc123",
        {
            # Tokens must carry the lpt_ prefix
            "instance": TypeError,
        },
    ),
    (
        "lauther://lpt_abc123",
        {
            # A valid token
            "instance": NotifyLauther,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "lauther://l...3/",
        },
    ),
    (
        "lauther://?token=lpt_abc123",
        {
            # Token provided as an argument
            "instance": NotifyLauther,
        },
    ),
    (
        "lauther://lpt_abc123?priority=high",
        {
            # Priority by name
            "instance": NotifyLauther,
        },
    ),
    (
        "lauther://lpt_abc123?priority=2",
        {
            # Priority by value
            "instance": NotifyLauther,
        },
    ),
    (
        "lauther://lpt_abc123?priority=invalid",
        {
            # An invalid priority falls back to the default
            "instance": NotifyLauther,
        },
    ),
    (
        "lauther://lpt_abc123?priority=99",
        {
            # An out-of-range priority is not acceptable
            "instance": TypeError,
        },
    ),
    (
        "lauther://lpt_abc123?sound=default&click=https://example.ca",
        {
            # Sound and click-through URL
            "instance": NotifyLauther,
        },
    ),
    (
        "lauther://lpt_abc123"
        "?icon=https://example.ca/icon.png&color=%23D9EF00"
        "&group=orders&route=/orders/123",
        {
            # Icon, color, group, and paired-site route overrides
            "instance": NotifyLauther,
        },
    ),
    (
        "lauther://lpt_abc123",
        {
            "instance": NotifyLauther,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "lauther://lpt_abc123",
        {
            "instance": NotifyLauther,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "lauther://lpt_abc123",
        {
            "instance": NotifyLauther,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_lauther_urls():
    """NotifyLauther() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@patch("requests.post")
def test_plugin_lauther_general(mock_post):
    """NotifyLauther() General Checks."""

    response = Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Prepare our object
    obj = Apprise.instantiate("lauther://lpt_abc123")
    assert isinstance(obj, NotifyLauther)
    assert obj.notify(body="body", title="title", notify_type=NotifyType.INFO)

    assert mock_post.call_count == 1
    details = mock_post.call_args_list[0]
    assert details[0][0] == "https://api.lauther.id/v1/push"

    # The token travels in the Authorization header, never the payload
    assert details[1]["headers"]["Authorization"] == "Bearer lpt_abc123"
    assert "token" not in details[1]["json"]

    # Verify our url() call is reversible back into the same object
    assert isinstance(obj.url(), str)
    obj_b = Apprise.instantiate(obj.url())
    assert isinstance(obj_b, NotifyLauther)
    assert obj.url_identifier == obj_b.url_identifier

    # The token is masked when privacy is requested
    assert "lpt_abc123" not in obj.url(privacy=True)


@patch("requests.post")
def test_plugin_lauther_priority(mock_post):
    """NotifyLauther() Priority Handling."""

    response = Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Named priorities resolve to their integer equivalent
    obj = Apprise.instantiate("lauther://lpt_abc123?priority=emergency")
    assert isinstance(obj, NotifyLauther)
    assert obj.priority == LautherPriority.EMERGENCY

    # As do numeric ones
    obj = Apprise.instantiate("lauther://lpt_abc123?priority=-2")
    assert isinstance(obj, NotifyLauther)
    assert obj.priority == LautherPriority.LOWEST

    # No priority at all lands on the default
    obj = Apprise.instantiate("lauther://lpt_abc123")
    assert isinstance(obj, NotifyLauther)
    assert obj.priority == LautherPriority.NORMAL

    # "low" and "lowest" share a prefix; each must resolve to itself. A
    # shortest-key-first scan silently mapped "low" onto LOWEST.
    obj = Apprise.instantiate("lauther://lpt_abc123?priority=low")
    assert isinstance(obj, NotifyLauther)
    assert obj.priority == LautherPriority.LOW

    obj = Apprise.instantiate("lauther://lpt_abc123?priority=lowest")
    assert isinstance(obj, NotifyLauther)
    assert obj.priority == LautherPriority.LOWEST
