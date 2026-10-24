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
import json
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.lfgalarm import NotifyLFGAlarm

logging.disable(logging.CRITICAL)

# A made up alarm token
TOKEN = "m9s346q3d25vt4f5v37e3s3e28jt97kb"

# What LFG Alarm replies with
RANG = json.dumps({"fired": True, "wokeUp": 1, "devices": 3})
COOLING_DOWN = json.dumps(
    {
        "error": "cooling_down",
        "message": "It rang moments ago.",
        "retryAfterSeconds": 42,
    }
)
ALARM_OFF = json.dumps({"error": "alarm_off"})

# Our Testing URLs
apprise_url_tests = (
    (
        "lfg://",
        {
            # No token specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "lfg://invalid!token",
        {
            # An invalid token
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "lfg://{}".format(TOKEN[:-1]),
        {
            # A token that is too short
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "lfg://{}".format(TOKEN),
        {
            # A valid token
            "instance": NotifyLFGAlarm,
            "requests_response_text": RANG,
            "privacy_url": "lfg://m...b/",
        },
    ),
    (
        "lfg://?token={}".format(TOKEN),
        {
            # The token supplied as an argument
            "instance": NotifyLFGAlarm,
            "requests_response_text": RANG,
            "privacy_url": "lfg://m...b/",
        },
    ),
    (
        "https://api.lfg.gm/horn/{}".format(TOKEN),
        {
            # The link LFG Alarm hands out
            "instance": NotifyLFGAlarm,
            "requests_response_text": RANG,
            "privacy_url": "lfg://m...b/",
        },
    ),
    (
        "https://api.lfg.gm/horn/{}/?verify=no".format(TOKEN),
        {
            # The link with a trailing slash and an Apprise argument
            "instance": NotifyLFGAlarm,
            "requests_response_text": RANG,
        },
    ),
    (
        "lfg://{}".format(TOKEN),
        {
            "instance": NotifyLFGAlarm,
            # A reply we can not read does not confirm a ring
            "response": False,
            "requests_response_text": "not json",
        },
    ),
    (
        "lfg://{}".format(TOKEN),
        {
            "instance": NotifyLFGAlarm,
            # The alarm rang moments ago; nothing rang
            "response": False,
            "requests_response_code": requests.codes.too_many_requests,
            "requests_response_text": COOLING_DOWN,
        },
    ),
    (
        "lfg://{}".format(TOKEN),
        {
            "instance": NotifyLFGAlarm,
            # The alarm is switched off; nothing rang
            "response": False,
            "requests_response_code": requests.codes.conflict,
            "requests_response_text": ALARM_OFF,
        },
    ),
    (
        "lfg://{}".format(TOKEN),
        {
            "instance": NotifyLFGAlarm,
            # No alarm at this link
            "response": False,
            "requests_response_code": requests.codes.not_found,
        },
    ),
    (
        "lfg://{}".format(TOKEN),
        {
            "instance": NotifyLFGAlarm,
            # A failure has been returned by the server
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "lfg://{}".format(TOKEN),
        {
            "instance": NotifyLFGAlarm,
            # An unknown response code
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "lfg://{}".format(TOKEN),
        {
            "instance": NotifyLFGAlarm,
            # Socket errors are handled
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_lfgalarm_urls():
    """NotifyLFGAlarm() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_lfgalarm_send(mock_post):
    """NotifyLFGAlarm() rings the alarm without a body."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = RANG.encode("utf-8")
    mock_post.return_value = response

    obj = Apprise.instantiate("lfg://{}".format(TOKEN))
    assert isinstance(obj, NotifyLFGAlarm)
    assert obj.notify(title="Ignored", body="Also ignored")

    # One post to the alarm's link, with nothing in it
    assert mock_post.call_count == 1
    assert mock_post.call_args[0][0] == "https://api.lfg.gm/horn/{}".format(
        TOKEN
    )
    assert "data" not in mock_post.call_args[1]
    assert "json" not in mock_post.call_args[1]

    # A confirmed ring, with or without a phone count
    for reply in ({"fired": True, "devices": 1}, {"fired": True}):
        response.content = json.dumps(reply).encode("utf-8")
        assert obj.notify(body="ring")

    # Anything short of fired=true is a failure
    for content in (
        b"[]",
        json.dumps({"devices": 1}).encode("utf-8"),
        json.dumps({"fired": None}).encode("utf-8"),
        json.dumps({"fired": False}).encode("utf-8"),
        json.dumps({"fired": "cooling_down"}).encode("utf-8"),
    ):
        response.content = content
        assert obj.notify(body="ring") is False


@mock.patch("requests.post")
def test_plugin_lfgalarm_rings_once(mock_post):
    """NotifyLFGAlarm() rings once even when asked to split a long body."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = RANG.encode("utf-8")
    mock_post.return_value = response

    obj = Apprise.instantiate("lfg://{}?overflow=split".format(TOKEN))
    assert isinstance(obj, NotifyLFGAlarm)
    assert obj.notify(title="t" * 400, body="b" * 70000)

    # A second post would land in the cooldown and fail
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_lfgalarm_nothing_rang(mock_post):
    """NotifyLFGAlarm() reports a cooldown or a switched off alarm."""

    response = mock.Mock()
    mock_post.return_value = response

    obj = NotifyLFGAlarm(token=TOKEN)

    # Cooling down, with and without a wait we can read
    response.status_code = requests.codes.too_many_requests
    for content in (COOLING_DOWN.encode("utf-8"), None):
        response.content = content
        with mock.patch.object(obj.logger, "warning") as warning:
            assert obj.notify(body="ring") is False
        message = warning.call_args[0][1]
        assert "cooling down" in message
        assert ("42s" in message) is (content is not None)

    # Switched off
    response.status_code = requests.codes.conflict
    response.content = ALARM_OFF.encode("utf-8")
    with mock.patch.object(obj.logger, "warning") as warning:
        assert obj.notify(body="ring") is False
    assert "switched off" in warning.call_args[0][1]


def test_plugin_lfgalarm_init():
    """NotifyLFGAlarm() init and url round trip."""

    obj = NotifyLFGAlarm(token=TOKEN)
    assert len(obj) == 1

    # The token is hidden in the privacy url and kept in the full one
    assert TOKEN not in obj.url(privacy=True)
    assert obj.url().startswith("lfg://{}/".format(TOKEN))

    # The URL survives a round trip
    result = NotifyLFGAlarm.parse_url(obj.url())
    obj2 = NotifyLFGAlarm(**result)
    assert obj.url_identifier == obj2.url_identifier

    # The link LFG Alarm hands out reads the same as lfg://
    result = NotifyLFGAlarm.parse_native_url(
        "https://api.lfg.gm/horn/{}".format(TOKEN)
    )
    assert result["token"] == TOKEN
    assert NotifyLFGAlarm(**result).url_identifier == obj.url_identifier

    # Other links are not ours
    assert (
        NotifyLFGAlarm.parse_native_url(
            "https://example.com/horn/{}".format(TOKEN)
        )
        is None
    )

    # A missing or blank token is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyLFGAlarm(token="  ")

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyLFGAlarm(token=None)
