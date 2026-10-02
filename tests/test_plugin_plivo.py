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
from json import loads
import logging
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise import Apprise
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.plivo import NotifyPlivo

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "plivo://",
        {
            # No hostname/apikey specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "plivo://{}@{}/15551232000".format("a" * 10, "a" * 25),
        {
            # invalid auth id
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "plivo://{}@{}/15551232000".format("a" * 25, "a" * 10),
        {
            # invalid token
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "plivo://{}@{}/123".format("a" * 25, "a" * 40),
        {
            # invalid phone number
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "plivo://{}@{}/abc".format("a" * 25, "a" * 40),
        {
            # invalid phone number
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "plivo://{}@{}/15551231234".format("a" * 25, "b" * 40),
        {
            # target phone number becomes who we text too; all is good
            "instance": NotifyPlivo,
        },
    ),
    (
        "plivo://{}@{}/15551232000/abcd".format("a" * 25, "a" * 40),
        {
            # invalid target phone number
            "instance": NotifyPlivo,
            # Notify will fail because it couldn't send to anyone
            "response": False,
        },
    ),
    (
        "plivo://{}@{}/15551232000/123".format("a" * 25, "a" * 40),
        {
            # invalid target phone number
            "instance": NotifyPlivo,
            # Notify will fail because it couldn't send to anyone
            "response": False,
        },
    ),
    (
        "plivo://{}@{}/?from=15551233000&to=15551232000&batch=yes".format(
            "a" * 25, "a" * 40
        ),
        {
            # reference to to= and from=
            "instance": NotifyPlivo,
        },
    ),
    (
        "plivo://?id={}&token={}&from=15551233000&to=15551232000".format(
            "a" * 25, "a" * 40
        ),
        {
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "plivo://a...a@a...a/+15551233000/+15551232000",
            # reference to to= and from=
            "instance": NotifyPlivo,
        },
    ),
    (
        "plivo://15551232123?id={}&token={}&from=15551233000"
        "&to=15551232000".format("a" * 25, "a" * 40),
        {
            # reference to to= and from=
            "instance": NotifyPlivo,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "plivo://a...a@a...a/+15551233000/+15551232123",
        },
    ),
    (
        "plivo://{}@{}/15551232000".format("a" * 25, "a" * 40),
        {
            "instance": NotifyPlivo,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "plivo://{}@{}/15551232000".format("a" * 25, "a" * 40),
        {
            "instance": NotifyPlivo,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_plivo_urls():
    """NotifyPlivo() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_plivo_dst_single(mock_post):
    """Plivo sends one message per recipient in dst."""

    # Plivo answers a queued message with 202 Accepted
    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b"{}"
    mock_post.return_value = response

    aobj = Apprise()
    assert aobj.add(
        "plivo://{}@{}/15551230000/15551231111/15551232222".format(
            "a" * 25, "b" * 40
        )
    )
    assert aobj.notify(body="body", title="title")

    # One post per recipient
    assert mock_post.call_count == 2
    first = loads(mock_post.call_args_list[0][1]["data"])
    second = loads(mock_post.call_args_list[1][1]["data"])
    assert first["src"] == "+15551230000"
    assert first["dst"] == "+15551231111"
    assert second["dst"] == "+15551232222"

    # No undocumented keys are sent
    assert "recipients" not in first


@mock.patch("requests.post")
def test_plugin_plivo_dst_batch(mock_post):
    """Plivo batches recipients into dst separated by <."""

    # Plivo also documents 201 Created as a success
    response = mock.Mock()
    response.status_code = requests.codes.created
    response.content = b"{}"
    mock_post.return_value = response

    aobj = Apprise()
    assert aobj.add(
        "plivo://{}@{}/15551230000/15551231111/15551232222?batch=yes".format(
            "a" * 25, "b" * 40
        )
    )
    assert aobj.notify(body="body", title="title")

    # A single post carries every recipient
    assert mock_post.call_count == 1
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["dst"] == "+15551231111<+15551232222"
    assert "recipients" not in payload


@mock.patch("requests.post")
def test_plugin_plivo_retry_skips_delivered(mock_post):
    """A Plivo retry only re-sends to the recipient that failed."""

    good = mock.Mock()
    good.status_code = requests.codes.accepted
    good.content = b"{}"

    bad = mock.Mock()
    bad.status_code = requests.codes.internal_server_error
    bad.content = b"{}"

    def respond(url, data=None, **kwargs):
        # Only the second recipient is refused
        return bad if loads(data)["dst"] == "+15551232222" else good

    mock_post.side_effect = respond

    aobj = Apprise()
    assert aobj.add(
        "plivo://{}@{}/15551230000/15551231111/15551232222"
        "?retry=1&wait=0".format("a" * 25, "b" * 40)
    )
    assert not aobj.notify(body="body")

    # The healthy recipient is contacted exactly once
    dsts = [loads(c[1]["data"])["dst"] for c in mock_post.call_args_list]
    assert dsts.count("+15551231111") == 1
    assert dsts.count("+15551232222") == 2
