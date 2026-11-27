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

from json import dumps, loads

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.sinch import NotifySinch

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "sinch://",
        {
            # No Account SID specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "sinch://:@/",
        {
            # invalid Auth token
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "sinch://{}@12345678".format("a" * 32),
        {
            # Just spi provided
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "sinch://{}:{}@_".format("a" * 32, "b" * 32),
        {
            # spi and token provided but invalid from
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "sinch://{}:{}@{}".format("a" * 32, "b" * 32, "3" * 5),
        {
            # using short-code (5 characters) without a target
            # We can still instantiate ourselves with a valid short code
            "instance": NotifySinch,
            # Expected notify() response because we have no one to notify
            "notify_response": False,
        },
    ),
    (
        "sinch://{}:{}@{}".format("a" * 32, "b" * 32, "3" * 9),
        {
            # spi and token provided and from but invalid from no
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "sinch://{}:{}@{}/123/{}/abcd/".format(
            "a" * 32, "b" * 32, "3" * 11, "9" * 15
        ),
        {
            # valid everything but target numbers
            "instance": NotifySinch,
            # Every target is refused, so there is nobody to notify
            "notify_response": False,
        },
    ),
    (
        "sinch://{}:{}@12345/{}".format("a" * 32, "b" * 32, "4" * 11),
        {
            # using short-code (5 characters)
            "instance": NotifySinch,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "sinch://...aaaa:b...b@12345",
        },
    ),
    (
        "sinch://{}:{}@123456/{}".format("a" * 32, "b" * 32, "4" * 11),
        {
            # using short-code (6 characters)
            "instance": NotifySinch,
        },
    ),
    (
        "sinch://{}:{}@{}".format("a" * 32, "b" * 32, "5" * 11),
        {
            # using phone no with no target - we text ourselves in
            # this case
            "instance": NotifySinch,
        },
    ),
    (
        "sinch://{}:{}@{}?region=eu".format("a" * 32, "b" * 32, "5" * 11),
        {
            # Specify a region
            "instance": NotifySinch,
        },
    ),
    (
        "sinch://{}:{}@{}?region=invalid".format("a" * 32, "b" * 32, "5" * 11),
        {
            # Invalid region
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "sinch://_?spi={}&token={}&from={}".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # use get args to acomplish the same thing
            "instance": NotifySinch,
        },
    ),
    (
        "sinch://_?spi={}&token={}&source={}".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # use get args to acomplish the same thing (use source instead of
            # from)
            "instance": NotifySinch,
        },
    ),
    (
        "sinch://_?spi={}&token={}&from={}&to={}".format(
            "a" * 32, "b" * 32, "5" * 11, "7" * 13
        ),
        {
            # use to=
            "instance": NotifySinch,
        },
    ),
    (
        "sinch://{}:{}@{}".format("a" * 32, "b" * 32, "6" * 11),
        {
            "instance": NotifySinch,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "sinch://{}:{}@{}".format("a" * 32, "b" * 32, "6" * 11),
        {
            "instance": NotifySinch,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_sinch_urls():
    """NotifyTemplate() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_sinch_edge_cases(mock_post):
    """NotifySinch() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    service_plan_id = "{}".format("b" * 32)
    api_token = "{}".format("b" * 32)
    source = "+1 (555) 123-3456"

    # No service_plan_id specified
    with pytest.raises(AppriseImproperlyConfigured):
        NotifySinch(service_plan_id=None, api_token=api_token, source=source)

    # No api_token specified
    with pytest.raises(AppriseImproperlyConfigured):
        NotifySinch(
            service_plan_id=service_plan_id, api_token=None, source=source
        )

    # a error response
    response.status_code = 400
    response.content = dumps(
        {
            "code": 21211,
            "message": "The 'To' number +1234567 is not a valid phone number.",
        }
    )
    mock_post.return_value = response

    # Initialize our object
    obj = NotifySinch(
        service_plan_id=service_plan_id, api_token=api_token, source=source
    )

    # We will fail with the above error code
    assert bool(obj.notify("title", "body", "info")) is False


@mock.patch("requests.post")
def test_plugin_sinch_invalid_recipients_kept(mock_post):
    """Refused phone numbers never fall back to messaging ourselves."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Shared (but valid) credentials for every object below
    kwargs = {
        "service_plan_id": "a" * 32,
        "api_token": "b" * 32,
        "source": "15551232000",
    }

    # No phone numbers given, so we message ourselves
    obj = NotifySinch(targets=None, **kwargs)
    assert obj.notify("body") is True
    assert mock_post.call_count == 1
    assert loads(mock_post.call_args[1]["data"])["to"] == ["+15551232000"]

    # Only separators given is the same as giving no phone numbers
    mock_post.reset_mock()
    obj = NotifySinch(targets=";, ,", **kwargs)
    obj = Apprise.instantiate(obj.url())
    assert obj.notify("body") is True
    assert mock_post.call_count == 1
    assert loads(mock_post.call_args[1]["data"])["to"] == ["+15551232000"]

    # Every phone number refused leaves nobody to notify
    mock_post.reset_mock()
    obj = NotifySinch(targets=["abcd", "123"], **kwargs)
    assert obj.notify("body") is False

    # Loading our URL again still leaves nobody to notify
    obj = Apprise.instantiate(obj.url())
    assert obj.notify("body") is False
    assert mock_post.call_count == 0
