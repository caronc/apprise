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
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.betterstack import BetterStackMode, NotifyBetterStack

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "betterstack://",
        {
            # No token specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "betterstack://token",
        {
            # Incident mode with only a token
            "instance": NotifyBetterStack,
            "requests_response_code": requests.codes.created,
            "privacy_url": "betterstack://t...n/",
        },
    ),
    (
        "betterstack://token/user@example.com",
        {
            # Incident mode with a requester e-mail
            "instance": NotifyBetterStack,
            "requests_response_code": requests.codes.created,
            "privacy_url": "betterstack://t...n/user@example.com/",
        },
    ),
    (
        "betterstack://token/user@example.com/Team%20A/team2",
        {
            # Incident mode raised for two teams
            "instance": NotifyBetterStack,
            "requests_response_code": requests.codes.created,
            "privacy_url": (
                "betterstack://t...n/user@example.com/Team%20A/team2/"
            ),
        },
    ),
    (
        "betterstack://?token=token&from=user@example.com&to=Ops",
        {
            # Everything supplied as arguments
            "instance": NotifyBetterStack,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "betterstack://token/user@example.com?alert=sms,call"
        "&policy=123&team_wait=60",
        {
            # Alert methods, escalation policy and team wait
            "instance": NotifyBetterStack,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "betterstack://token/?from=invalid",
        {
            # An invalid requester e-mail
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "betterstack://token/?alert=fax",
        {
            # An invalid alert method
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "betterstack://token/?team_wait=-1",
        {
            # A negative team wait
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "betterstack://token/?team_wait=abc",
        {
            # A team wait that is not a number
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "betterstack://token@s1234.eu-nbg-2.betterstackdata.com",
        {
            # Logs mode
            "instance": NotifyBetterStack,
            "requests_response_code": requests.codes.accepted,
            "privacy_url": (
                "betterstack://t...n@s1234.eu-nbg-2.betterstackdata.com/"
            ),
        },
    ),
    (
        "betterstack://in.logs.betterstack.com:8443?token=token",
        {
            # Logs mode with a port and the token as an argument
            "instance": NotifyBetterStack,
            "requests_response_code": requests.codes.accepted,
            "privacy_url": (
                "betterstack://t...n@in.logs.betterstack.com:8443/"
            ),
        },
    ),
    (
        "betterstack://token/user@example.com",
        {
            "instance": NotifyBetterStack,
            # Authentication failed
            "response": False,
            "requests_response_code": 404,
        },
    ),
    (
        "betterstack://token/user@example.com",
        {
            "instance": NotifyBetterStack,
            # Throws a series of i/o exceptions with this flag
            "test_requests_exceptions": True,
        },
    ),
    (
        "betterstack://token@s1234.eu-nbg-2.betterstackdata.com",
        {
            "instance": NotifyBetterStack,
            # An unknown response code
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "betterstack://token@s1234.eu-nbg-2.betterstackdata.com",
        {
            "instance": NotifyBetterStack,
            # Throws a series of i/o exceptions with this flag
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_betterstack_urls():
    """NotifyBetterStack() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_betterstack_incident(mock_post):
    """NotifyBetterStack() Incident payload."""

    response = mock.Mock()
    response.status_code = requests.codes.created
    response.content = b"{}"
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "betterstack://abc123/user@example.com/Ops%20Team"
        "?alert=sms,push&policy=42&team_wait=0"
    )
    assert isinstance(obj, NotifyBetterStack)
    assert obj.mode == BetterStackMode.INCIDENT
    assert obj.targets == ["Ops Team"]
    assert len(obj) == 1

    assert obj.notify(
        title="Disk <full> & more", body="Free some _space_ now!"
    )
    assert mock_post.call_count == 1

    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "incidents.betterstack.com"
    assert urlparse(url).path == "/api/v3/incidents"

    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer abc123"

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload == {
        "summary": "Disk <full> & more",
        "name": "Disk <full> & more",
        "description": "Free some _space_ now!",
        "requester_email": "user@example.com",
        "policy_id": "42",
        "team_wait": 0,
        "call": False,
        "sms": True,
        "email": False,
        "push": True,
        "critical_alert": False,
        "team_name": "Ops Team",
    }

    # Without a title, the body is the summary and team settings decide
    # how the on-call person is alerted
    mock_post.reset_mock()
    obj = Apprise.instantiate("betterstack://abc123")
    assert obj.notify(body="Something broke")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload == {"summary": "Something broke"}


@mock.patch("requests.post")
def test_plugin_betterstack_teams(mock_post):
    """NotifyBetterStack() raises one incident per team."""

    good = mock.Mock()
    good.status_code = requests.codes.created
    good.content = b"{}"

    bad = mock.Mock()
    bad.status_code = requests.codes.not_found
    bad.content = b""

    obj = Apprise.instantiate(
        "betterstack://abc123/user@example.com/team1/team2"
    )
    assert len(obj) == 2

    # Both teams succeed
    mock_post.side_effect = (good, good)
    assert obj.notify(body="body")
    teams = [
        json.loads(c[1]["data"])["team_name"] for c in mock_post.call_args_list
    ]
    assert teams == ["team1", "team2"]

    # One failing team fails the notification but still reaches the other
    mock_post.reset_mock()
    mock_post.side_effect = (bad, good)
    assert not obj.notify(body="body")
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_betterstack_logs(mock_post):
    """NotifyBetterStack() Logs payload."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "betterstack://srctoken@s1234.eu-nbg-2.betterstackdata.com"
    )
    assert isinstance(obj, NotifyBetterStack)
    assert obj.mode == BetterStackMode.LOGS
    assert len(obj) == 1

    assert obj.notify(
        title="Title", body="Body", notify_type=NotifyType.FAILURE
    )
    url = mock_post.call_args[0][0]
    assert url == "https://s1234.eu-nbg-2.betterstackdata.com"

    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer srctoken"

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "Body"
    assert payload["title"] == "Title"
    assert payload["level"] == "error"
    assert payload["dt"].endswith("+00:00")

    # No title, a warning, and a custom port
    mock_post.reset_mock()
    obj = Apprise.instantiate(
        "betterstack://srctoken@in.logs.betterstack.com:8443"
    )
    assert obj.notify(body="Body", notify_type=NotifyType.WARNING)
    assert mock_post.call_args[0][0] == (
        "https://in.logs.betterstack.com:8443"
    )
    payload = json.loads(mock_post.call_args[1]["data"])
    assert "title" not in payload
    assert payload["level"] == "warn"


def test_plugin_betterstack_init():
    """NotifyBetterStack() direct initialization."""

    # Alert methods are matched without case and stored once
    obj = NotifyBetterStack(token="abc", alert=["SMS", "sms", "Call"])
    assert obj.alert == ["call", "sms"]

    # Round trip keeps our connection, teams and options
    obj = NotifyBetterStack(
        token="abc",
        from_addr="user@example.com",
        targets=["Team A", "Team B"],
        policy=" 42 ",
        team_wait="30",
    )
    assert obj.policy == "42"
    assert obj.team_wait == 30

    obj2 = Apprise.instantiate(obj.url())
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.targets == obj.targets
    assert obj2.from_addr == obj.from_addr
    assert obj2.policy == obj.policy
    assert obj2.team_wait == obj.team_wait

    # Incidents and logs are different connections
    logs = Apprise.instantiate("betterstack://abc@in.logs.betterstack.com")
    assert logs.url_identifier != obj.url_identifier

    # A token is required
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyBetterStack(token="  ")
