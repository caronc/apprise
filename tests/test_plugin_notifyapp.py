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
from json import dumps, loads
import logging
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import requests

import apprise
from apprise import NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.notifyapp import NotifyNotifyApp

logging.disable(logging.CRITICAL)

# A device token as the Notify! app hands it out
TOKEN = "aB3dE5fG7hJ9kL2"

# Our Testing URLs
apprise_url_tests = (
    (
        "notifyapp://",
        {
            # No Device ID specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "notifyapp://:@/",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "notifyapp://IOabcdefgh123456",
        {
            # No Token specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "notifyapp://IOabcdefgh123456/{}".format(TOKEN),
        {
            "instance": NotifyNotifyApp,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifyapp://I...6/a...2/",
        },
    ),
    (
        # A Device Group
        "notifyapp://GRPA1B2C/{}".format(TOKEN),
        {
            "instance": NotifyNotifyApp,
        },
    ),
    (
        # Our token provided as a query argument
        "notifyapp://AB12CD34/?token={}".format(TOKEN),
        {
            "instance": NotifyNotifyApp,
            "privacy_url": "notifyapp://A...4/a...2/",
        },
    ),
    (
        # Our options
        "notifyapp://AB12CD34/{}?image=no&thread=ci&urgent=yes".format(TOKEN),
        {
            "instance": NotifyNotifyApp,
        },
    ),
    (
        # Native URL
        "https://push.getnotifyapp.com/notify/AB12CD34?token={}".format(TOKEN),
        {
            "instance": NotifyNotifyApp,
        },
    ),
    (
        # Native JSON URL
        "https://push.getnotifyapp.com/notify-json/AB12CD34/?token={}".format(
            TOKEN
        ),
        {
            "instance": NotifyNotifyApp,
        },
    ),
    (
        # Native Group URL
        "https://push.getnotifyapp.com/notify-group/GRPA1B2C?token={}".format(
            TOKEN
        ),
        {
            "instance": NotifyNotifyApp,
        },
    ),
    (
        "notifyapp://AB12CD34/{}".format(TOKEN),
        {
            "instance": NotifyNotifyApp,
            # Throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "notifyapp://AB12CD34/{}".format(TOKEN),
        {
            "instance": NotifyNotifyApp,
            "response": False,
            "requests_response_code": requests.codes.forbidden,
        },
    ),
    (
        "notifyapp://AB12CD34/{}".format(TOKEN),
        {
            "instance": NotifyNotifyApp,
            # Throws a series of i/o exceptions with this flag set and tests
            # that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_notifyapp_urls():
    """NotifyNotifyApp() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_notifyapp_init():
    """NotifyNotifyApp() rejects a bad Device ID or Token."""

    # A Device ID with characters it can never contain
    result = NotifyNotifyApp.parse_url(f"notifyapp://AB12CD34/{TOKEN}")
    result["device"] = "AB 12"
    assert apprise.Apprise.instantiate(result) is None

    # An empty Token
    result = NotifyNotifyApp.parse_url(f"notifyapp://AB12CD34/{TOKEN}")
    result["token"] = "  "
    assert apprise.Apprise.instantiate(result) is None


@mock.patch("requests.post")
def test_plugin_notifyapp_payload(mock_post):
    """NotifyNotifyApp() builds the expected request."""

    # Prepare our response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = dumps(
        {
            "success": True,
            "type": "device",
            "deviceId": "AB12CD34",
            "message": "Notification sent successfully",
        }
    ).encode("utf-8")
    mock_post.return_value = response

    obj = apprise.Apprise.instantiate(
        f"notifyapp://AB12CD34/{TOKEN}?thread=ci&urgent=yes"
    )
    assert isinstance(obj, NotifyNotifyApp)

    # Plain text arrives as typed, title included
    assert obj.notify(
        title="Build <1> & done",
        body="_hello_ *world* #1 <ok>!",
        notify_type=NotifyType.FAILURE,
    )

    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "push.getnotifyapp.com"
    assert urlparse(url).path == "/notify-json/AB12CD34"
    assert mock_post.call_args[1]["params"] == {"token": TOKEN}

    payload = loads(mock_post.call_args[1]["data"])
    assert payload["title"] == "Build <1> & done"
    assert payload["text"] == "_hello_ *world* #1 <ok>!"
    assert payload["groupType"] == "ci"
    assert payload["timeSensitive"] is True
    assert payload["iconUrl"].startswith("http")

    # Our settings survive a round trip
    obj2 = apprise.Apprise.instantiate(obj.url())
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.thread == "ci"
    assert obj2.urgent is True

    mock_post.reset_mock()

    # Now with our defaults, no title and no image
    obj = apprise.Apprise.instantiate(f"notifyapp://AB12CD34/{TOKEN}?image=no")
    assert obj.notify(body="body")

    payload = loads(mock_post.call_args[1]["data"])
    assert payload == {"text": "body"}

    # Our settings survive a round trip
    obj2 = apprise.Apprise.instantiate(obj.url())
    assert obj2.include_image is False
    assert obj2.urgent is False
    assert obj2.thread is None


@mock.patch("requests.post")
def test_plugin_notifyapp_response(mock_post):
    """NotifyNotifyApp() accepts a 200 response it cannot read."""

    # Prepare our response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = apprise.Apprise.instantiate(f"notifyapp://GRPA1B2C/{TOKEN}")

    # A body that is not JSON
    response.content = b"not json"
    assert obj.notify(body="body")

    # JSON that is not an object
    response.content = b"[]"
    assert obj.notify(body="body")

    # A group that reached some of its devices still succeeds
    response.content = dumps(
        {"success": True, "successCount": 1, "failureCount": 2}
    ).encode("utf-8")
    assert obj.notify(body="body")

    # A group that reached none of its devices fails
    response.content = dumps(
        {"success": True, "successCount": 0, "failureCount": 2}
    ).encode("utf-8")
    assert not obj.notify(body="body")


def test_plugin_notifyapp_native_fragment():
    """NotifyNotifyApp() leaves a native URL fragment out of the token."""

    result = NotifyNotifyApp.parse_native_url(
        "https://push.getnotifyapp.com/notify/AB12CD34"
        "?token={}#fragment".format(TOKEN)
    )
    assert result["device"] == "AB12CD34"
    assert result["token"] == TOKEN
