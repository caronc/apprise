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

"""Exercises the skip path of every plugin that tracks its deliveries.

``tests/test_delivery_tracking_fleet.py`` proves the behaviour is right.
This file makes sure the branch is actually reached for every service,
including the ones the fleet harness cannot drive end to end.

Each plugin is loaded from one of its own test URLs, then told that every
target has already been reached.  ``send()`` should walk its targets,
skip them all, and come back without contacting anything.
"""

# Disable logging for a cleaner testing output
import contextlib
from json import dumps
import logging
import os
import socket
from unittest import mock

import pytest
import requests

from apprise import Apprise, AppriseAttachment
from apprise.plugins.base import NotifyBase, _delivery_tracker

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")
ATTACHMENT = os.path.join(TEST_VAR_DIR, "apprise-test.gif")

# A response wide enough that most services accept it and carry on to
# their target list.  Without one they stop at the first status check and
# never reach the part under test.
OK_BODY = dumps(
    {
        "ok": True,
        "success": True,
        "status": "success",
        "id": "1",
        "code": 0,
        "errcode": 0,
        "error": None,
        "channel": "C1",
        "access_token": "abc",
        "expires_in": 3600,
        "upload_url": "https://localhost/upload",
        "file_id": "F1",
        "content_uri": "mxc://localhost/1",
        "event_id": "e1",
        "room_id": "!r:localhost",
        "user_id": "@u:localhost",
        "post": {"id": 1},
        "result": {"message_id": 1, "id": "1"},
        "data": {"id": "1"},
        "json": {"errors": []},
        "messages": [{"status": "0", "message-id": "1"}],
    }
)


def _ok_response(*args, **kwargs):
    """Return a response a plugin will treat as a success."""
    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = OK_BODY
    response.text = OK_BODY
    response.headers = {"Content-Type": "application/json"}
    return response


# One URL per service that tracks deliveries.  Each is taken from that
# plugin's own test suite so it stays valid as the plugin changes.
TRACKED = {
    "africas_talking": "atalk://user@apikey/+15551234567",
    "bark": "bark://192.168.0.6:8081/device_key",
    "brevo": "brevo://abcd:user@example.com/test@example.ca",
    "bulksms": "bulksms://aaaaa:bbbbbbbbbb@123/33333333333/abcd/",
    "bulkvs": "bulkvs://uuuuuuuuuu:pppppppppp@1111111111/15551234567",
    "burstsms": "burstsms://ffffffff:gggggggggggggggg@33333333333/15551234567",
    "clicksend": "clicksend://user:pass@33333333333333?batch=yes",
    "d7networks": "d7sms://token1@33333333333333?batch=yes",
    "dapnet": "dapnet://user:pass@localhost/DL0001/DL9999",
    "eight00com": "eight00com://GOODTOKEN@9876543210/15551234567",
    "emby": "emby://user@localhost",
    "evolution": (
        "evolution://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@localhost/inst/"
        "12125550001/12125559999"
    ),
    "exotel": (
        "exotel://sid:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@12125550000/"
        "12125550001/12125559999"
    ),
    "fcm": "fcm://apikey/device",
    "flock": "flock://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/u:0001/u:9999",
    "fortysixelks": "46elks://user:pass@sender/12125550001/12125559999",
    "google_chat": "gchat://workspace/key/token",
    "home_assistant": "hassio://localhost/accesstoken",
    "httpsms": (
        "httpsms://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@12125550000/"
        "12125550001/12125559999"
    ),
    "humhub": "humhub://mytoken@hostname/1",
    "ifttt": "ifttt://WebHookID@EventID/EventID2/",
    "jira": "jira://apikey/user@example.com",
    "join": "join://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/device0001",
    "kavenegar": "kavenegar://12125550000/12125550001/12125559999",
    "line": "line://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/target0001",
    "mailersend": (
        "mailersend://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:user@example.com/"
        "one@example.ca"
    ),
    "mailgun": "mailgun://user@localhost.localdomain/apikey/test@example.ca",
    "matrix": "matrix://user:pass@localhost/#general",
    "mattermost": "mmost://user@localhost/3ccdd113474722377935511fc85d3dd4?channel=test",
    "messagebird": "msgbird://aaaaaaaaaaaaaaaaaaaaaaaaa/12125550000/",
    "nextcloud": "ncloud://localhost/admin/user1",
    "nextcloudtalk": "nctalk://user:pass@localhost/room1",
    "notifiarr": "notifiarr://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/#1001",
    "ntfy": "ntfy://localhost/topic0001/topic9999",
    "octopush": (
        "octopush://user@example.com/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/"
        "12125550001"
    ),
    "office365": (
        "o365://tenant/ab-cd-ef-gh/abcd/123/3343/@jack/test/email1@test.ca"
    ),
    "one_signal": "onesignal://appid@apikey/playerid",
    "opsgenie": "opsgenie://apikey/user",
    "pingram": "pingram://pingram_sk_abc123/12125550001",
    "plivo": (
        "plivo://aaaaaaaaaaaaaaaaaaaaaaaaa@"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/15551231234"
    ),
    "postmark": (
        "postmark://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:user@example.com/"
        "one@example.ca"
    ),
    "pushbullet": "pbul://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/#chan1",
    "pushed": (
        "pushed://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/#chan0001/@user0001"
    ),
    "pushover": "pover://user@token/",
    "pushplus": "pushplus://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/group0001",
    "pushsafer": "psafer://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/12",
    "pushy": "pushy://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/@device",
    "reddit": (
        "reddit://user:pass@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/sub0001"
    ),
    "resend": (
        "resend://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:user@example.com/"
        "one@example.ca"
    ),
    "revolt": "revolt://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/chan0001",
    "ringcentral": (
        "ringc://18005554321:jwtcccccccccccccccccccccccccccccccccc"
        "cccccccccccccccccccccccccc@client_id/secret/1555123456"
        "?mode=jwt"
    ),
    "rocketchat": "rocket://user:pass@localhost/#chan0001",
    "sendgrid": (
        "sendgrid://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:user@example.com/"
        "one@example.ca"
    ),
    "sendpulse": ("sendpulse://user@example.com/cid/csecret/one@example.ca"),
    "serwersms": "serwersms://user:pass@SenderA/+48123456789",
    "ses": (
        "ses://user@example.ca/aaaaaaaaaaaaaaaaaaaa/"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/us-east-1/"
        "one@example.ca"
    ),
    "seven": "seven://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/12125550001",
    "sfr": "sfr://user:pass@spaceid/12125550001",
    "signalgrid": "signalgrid://CLIENTKEY/CHANNEL",
    "sinch": (
        "sinch://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb@15551230000/15551234567"
    ),
    "slack": ("slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#chan1"),
    "smpp": "smpp://user:pass@localhost:2775/12125550000/12125550001",
    "smseagle": "smseagle://token@localhost/12512222222/@contact/%23group",
    "smsmanager": "smsmgr://zzzzzzzzzz@123/33333333333/abcd/+44444444444",
    "smtp2go": (
        "smtp2go://user@example.com/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/"
        "one@example.ca"
    ),
    "sns": (
        "sns://aaaaaaaaaaaaaaaaaaaa/"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/us-east-1/"
        "12125550001/MyTopic"
    ),
    "sogs": (
        "sessions://"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb:"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@"
        "open.getsession.org/test-room"
    ),
    "sparkpost": (
        "sparkpost://user@example.com/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/"
        "one@example.ca"
    ),
    "telegram": (
        "tgram://123456789:ABCdefGHIjklMNOpqrSTUvwxYZ1234567890/111/"
    ),
    "telnyx": (
        "telnyx://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@12125550000/12125550001"
    ),
    "threema": (
        "threema://*GATEWAY@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/user0001"
    ),
    "trigv": "trigvs://trgv_a1b2c3d4_0123456789abcdef0123456789abcdef",
    "twilio": (
        "twilio://ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb@12125550000/12125550001"
    ),
    "twist": "twist://user@example.com/password",
    "twitter": (
        "twitter://consumer_key/consumer_secret/atoken2/access_secret/user1"
    ),
    "vapid": "vapid://user@example.ca/abc123",
    "viber": "viber://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/t0001?from=Bot",
    "voipms": "voipms://pass:user@example.com/12125550000/12125550001",
    "vonage": (
        "vonage://ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb@12125550000/12125550001"
    ),
    "webexteams": "wxteams://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/room0001",
    "whatsapp": (
        "whatsapp://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@12125550000/12125550001"
    ),
    "wpush": "wpush://WPUSHaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "zulip": "zulip://botname@apprise/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/chan1",
}

# These sign in to the service before they look at their target list.
# That first request is not a delivery, so it is allowed here.
AUTHENTICATES_FIRST = {
    "matrix",
    "office365",
    "reddit",
    "ringcentral",
    "rocketchat",
    "sendpulse",
}

# These cannot reach their target loop without something a generic mock
# cannot provide: a live session list, a stored subscription file, an
# open socket, or a lookup answer shaped per service.  Their behaviour is
# covered by test_delivery_tracking_fleet.py where it can be driven, and
# by their own test suites otherwise.
CANNOT_REACH_TARGETS = {
    "d7networks": "batches are built from a prepared payload",
    "emby": "needs a live session list from the server",
    "jira": "needs an issue lookup answer",
    "opsgenie": "needs an alert lookup answer",
    "pushbullet": "recipient lookup happens before the loop",
    "smpp": "needs an open SMPP connection",
    "twist": "needs a channel listing",
    "twitter": "needs a user lookup answer",
    "vapid": "needs a stored subscription file",
}

# Names only, for readable test ids
TRACKED_IDS = sorted(TRACKED)


# A socket-based service builds its socket before the patched connect()
# refuses it; the object is discarded unused.
@pytest.mark.filterwarnings("ignore::ResourceWarning")
@pytest.mark.parametrize("name", TRACKED_IDS)
def test_every_target_can_be_skipped(name):
    """send() walks its targets and skips ones already delivered."""

    if name in CANNOT_REACH_TARGETS:
        pytest.skip(f"{name}: {CANNOT_REACH_TARGETS[name]}")

    obj = Apprise.instantiate(TRACKED[name], suppress_exceptions=True)
    if obj is None:
        pytest.skip(f"{name}: URL no longer loads")

    token = _delivery_tracker.set(set())
    try:
        # Pretend every target was reached on an earlier attempt, then
        # let the plugin walk its list.
        with (
            mock.patch.object(
                NotifyBase, "is_delivered", return_value=True
            ) as asked,
            mock.patch("requests.post", side_effect=_ok_response) as post,
            mock.patch("requests.get", side_effect=_ok_response) as get,
            mock.patch("requests.put", side_effect=_ok_response) as put,
            mock.patch("requests.patch", side_effect=_ok_response) as patch,
            mock.patch("apprise.plugins.base.time.sleep"),
            # Keep the test off the network entirely
            mock.patch.object(socket.socket, "connect", side_effect=OSError),
        ):
            # A service that needs a live connection (a socket, an SMTP
            # session) cannot get far enough to deliver anything.  The
            # skip path is still walked on the way through.
            with contextlib.suppress(Exception):
                # An attachment is offered so services that fan out over
                # their uploads walk that path too.  send() is called
                # directly here, so it has to be handed a prepared
                # object the way notify() would.
                obj.send(
                    body="test",
                    title="test",
                    attach=AppriseAttachment(ATTACHMENT),
                )

            # The plugin has to ask before it sends, otherwise it has no
            # way of knowing a target was already reached.
            assert asked.called, (
                f"{name}: send() never called is_delivered(); a retry"
                " would contact every target again"
            )

            if name in AUTHENTICATES_FIRST:
                # Signing in is expected; there is nothing further to
                # check for these.
                return

            # With every target already reached there is nothing left to
            # deliver.  Any request here is a message going out twice.
            for name_, call in (
                ("post", post),
                ("get", get),
                ("put", put),
                ("patch", patch),
            ):
                assert not call.called, (
                    f"{name}: requests.{name_}() was used even though"
                    " every target had already been reached"
                )

    finally:
        _delivery_tracker.reset(token)
