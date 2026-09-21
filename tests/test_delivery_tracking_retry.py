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

"""Ensure a second attempt does not repeat completed deliveries.

Each service runs twice against one tracker. The first pass delivers;
the second may repeat setup work but must not deliver again.
"""

# Disable logging for a cleaner testing output
import contextlib
from json import dumps, loads
import logging
import socket
from unittest import mock

from helpers import ATTACHMENT, OK_BODY, delivery_marks
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.base import _delivery_tracker

logging.disable(logging.CRITICAL)

# What a particular service needs to see before it calls a delivery a
# success.  "body" is merged over OK_BODY, "status" replaces the HTTP
# code, and "raw" replaces the response text outright.
# AWS answers in XML rather than JSON.
SNS_XML = (
    '<CreateTopicResponse xmlns="http://sns.amazonaws.com/doc/2010-03-31/">'
    "<CreateTopicResult>"
    "<TopicArn>arn:aws:sns:us-east-1:000000000000:MyTopic</TopicArn>"
    "</CreateTopicResult><ResponseMetadata>"
    "<RequestId>604bef0f-369c-50c5-a7a4-bbd474c83d6a</RequestId>"
    "<MessageId>1</MessageId>"
    "</ResponseMetadata></CreateTopicResponse>"
)

# A couple of services only act on certain notification types; the
# default would leave them with nothing to do.
NOTIFY_TYPES = {
    "jira": NotifyType.FAILURE,
    "opsgenie": NotifyType.FAILURE,
}

RESPONSES = {
    "dapnet": {"status": 201},
    "kook": {
        "body": {
            "code": 0,
            "url": "https://cdn.example/x",
            "data": {"url": "https://cdn.example/x", "id": "1"},
        }
    },
    "octopush": {"status": 201},
    "smseagle": {"body": {"result": {"status": "ok"}}},
    "pushplus": {"body": {"code": 200}},
    "pushsafer": {"body": {"status": 1}},
    "sns": {"raw": SNS_XML},
    "viber": {"body": {"status": 0}},
}

# One URL per service that records its deliveries.  Each carries at
# least one target so the loop under test actually runs.
TRACKED = {
    "africas_talking": "atalk://user@apikey/33333333333/+44444444444",
    "aprs": "aprs://DF1ABC:12345@DF1DEF/DF1GHI",
    "bark": "bark://192.168.0.6:8081/device_key",
    "brevo": "brevo://abcd:user@example.com/test@example.ca",
    "bulksms": "bulksms://aaaaa:bbbbbbbbbb@123/33333333333/abcd/",
    "bulkvs": "bulkvs://uuuuuuuuuu:pppppppppp@1111111111/15551234567",
    "burstsms": (
        "burstsms://ffffffff:gggggggggggggggg@33333333333/15551234567"
    ),
    "clickatell": (
        "clickatell://_?apikey=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "&from=1111111111&to=15551230001,15551239999"
    ),
    "clicksend": "clicksend://user:pass@33333333333333?batch=no",
    "d7networks": "d7sms://token1@33333333333333?batch=no",
    "dapnet": "dapnet://user:pass@localhost/DL0001/DL9999",
    "eight00com": "eight00com://tttttttttt@8888888888/55555555555",
    "email": "mailto://user:pass@localhost/one@example.ca/two@example.ca",
    "emby": "emby://user:pass@localhost",
    "evolution": (
        "evolution://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@localhost/inst/"
        "12125550001/12125559999"
    ),
    "exotel": (
        "exotel://sid:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@12125550000/"
        "12125550001/12125559999"
    ),
    "fcm": "fcm://apikey/#topic1/device/",
    "flock": "flock://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/u:0001/u:9999",
    "fortysixelks": "46elks://user:pass@sender/12125550001/12125559999",
    "google_chat": "gchat://workspace/key/token",
    "home_assistant": "hassio://localhost/prefix/path/long.lived.token",
    "httpsms": (
        "httpsms://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@12125550000/"
        "12125550001/12125559999"
    ),
    "humhub": "humhubs://mytoken@hostname/1/2/3",
    "ifttt": "ifttt://WebHookID@EventID/EventID2/",
    "jira": "jira://apikey/user@email.com/#team/",
    "join": "join://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/device0001",
    "kavenegar": "kavenegar://12125550000/12125550001/12125559999",
    "kook": "kook://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/1234567890",
    "line": "line://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/target0001",
    "mailersend": (
        "mailersend://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:user@example.com/"
        "one@example.ca"
    ),
    "mailgun": (
        "mailgun://user@example.com/"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbb-cccccccc/"
        "user1@example.com?batch=no"
    ),
    "matrix": "matrix://user:pass@localhost/#room1/#room2",
    "mattermost": (
        "mmost://user@localhost/3ccdd113474722377935511fc85d3dd4?channel=test"
    ),
    "messagebird": "msgbird://aaaaaaaaaaaaaaaaaaaaaaaaa/12125550000/",
    "mqtt": "mqtt://localhost/topic1/topic2",
    "nextcloud": "ncloud://user@localhost?to=user1,user2",
    "nextcloudtalk": "nctalk://user:pass@localhost/room1",
    "notifiarr": "notifiarr://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/#1001",
    "ntfy": "ntfy://localhost/topic0001/topic9999",
    "octopush": (
        "octopush://sender:user@myaccount.com/apikey/1111111111/"
        "33333333333/?batch=no"
    ),
    "office365": (
        "o365://tenant/ab-cd-ef-gh/abcd/123/3343/@jack/test/email1@test.ca"
    ),
    "one_signal": "onesignal://appid@apikey/playerid",
    "opsgenie": "opsgenie://apikey/user@email.com/",
    "pingram": "pingram://pingram_sk_abc123/12125550001",
    "plivo": (
        "plivo://15551232123?id=aaaaaaaaaaaaaaaaaaaaaaaaa"
        "&token=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "&from=15551233000&to=15551232000"
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
    "pushover": (
        "pover://uuuuuuuuuuuuuuuuuuuuuuuuuuuuuu@"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/DEVICE1/"
    ),
    "pushplus": "pushplus://abc123def456ghi789jkl012mno345pq/group1",
    "pushsafer": "psafer://eeeeeeeeeeeeeeeeeeee/12",
    "pushy": "pushy://_/@device/#topic?key=apikey",
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
        "cccccccccccccccccccccccccc@client_id/secret/1555123456?mode=jwt"
    ),
    "rocketchat": "rocket://user:pass@localhost/#chan0001",
    "sendgrid": (
        "sendgrid://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:user@example.com/"
        "one@example.ca"
    ),
    "sendpulse": (
        "sendpulse://user@example.com/client_id/cs9/chris@example.com/"
        "chris2@example.com"
    ),
    "serwersms": "serwersms://user:pass@SenderA/+48123456789",
    "ses": (
        "ses://user@example.com/T1JJ3TD4JD/TIiajkdnlazk7FQ/us-west-2/"
        "user2@example.ca?batch=no"
    ),
    "seven": "seven://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/12125550001",
    "sfr": "sfr://user:pass@spaceid/12125550001",
    "signal_api": "signal://localhost/+12125550000/+12125550001",
    "signalgrid": "signalgrid://CLIENTKEY/CHANNEL1/CHANNEL2",
    "sinch": (
        "sinch://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb@15551230000/15551234567"
    ),
    "slack": ("slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#chan1"),
    "smpp": "smpp://user:pass@localhost:2775/12125550000/12125550001",
    "smseagle": "smseagle://token@localhost/12512222222/@contact/%23group",
    "smsmanager": "smsmgr://zzzzzzzzzz@123/33333333333/+44444444444",
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
        "one@example.ca?batch=no"
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
    "trigv": (
        "trigvs://trgv_a1b2c3d4_0123456789abcdef0123456789abcdef/alerts/ops"
    ),
    "twilio": (
        "twilio://ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb@12125550000/12125550001"
    ),
    "twist": "twist://password:user1@example.com",
    "twitter": "twitter://consumer_key/consumer_secret/atoken2/asecret/user1",
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

# These need more of their service emulated than a shared fixture can
# offer: a signed handshake, a stored key pair, a session or channel
# listing, or a multi-step upload.  Their delivery tracking is exercised
# by test_delivery_tracking_paths.py, and their own suites cover the
# rest of their behaviour.
NEEDS_ITS_OWN_SERVICE = {
    "aprs": "needs an APRS-IS login handshake",
    "emby": "needs a live session listing",
    "jira": "needs a stored request id from a previous call",
    "opsgenie": "needs a stored request id from a previous call",
    "pushbullet": "needs a recipient lookup answer",
    "slack": "needs the multi-step file upload exchange",
    "sogs": "needs a signed Session handshake",
    "twist": "needs a workspace and channel listing",
    "twitter": "needs a user lookup answer",
    "vapid": "needs a stored key pair and subscription file",
}

TRACKED_IDS = sorted(TRACKED)


class _Work:
    """Counts everything a plugin does that reaches the outside world."""

    def __init__(self, spec=None):
        self.count = 0
        spec = spec or {}
        self.status = spec.get("status", requests.codes.ok)
        self.handler = spec.get("handler")
        if "raw" in spec:
            self.payload = spec["raw"]

        else:
            merged = dict(loads(OK_BODY))
            merged.update(spec.get("body", {}))
            self.payload = dumps(merged)

    def http(self, *args, **kwargs):
        self.count += 1
        status, text = self.status, self.payload
        if self.handler is not None:
            # A service that needs its answer shaped to the request
            # supplies its own.
            shaped = self.handler(args[0] if args else "", kwargs)
            if shaped is not None:
                status, text = shaped

        response = requests.Request()
        response.status_code = status
        response.content = text
        response.text = text
        response.headers = {"Content-Type": "application/json"}
        return response

    def plain(self, *args, **kwargs):
        self.count += 1
        return True


# Services that speak their own protocol need their client stubbed out
# rather than their socket; a bare socket leaves them waiting for a
# handshake that never comes.
def _protocol_stubs(work):
    """Return extra patches needed by non-HTTP services."""
    stubs = []

    try:
        import paho.mqtt.client  # noqa: F401

        published = mock.Mock(**{"rc": 0, "is_published.return_value": True})

        def publish(*args, **kwargs):
            """Count the call and hand back a published message."""
            work.plain()
            return published

        client = mock.Mock(
            **{
                "connect.return_value": 0,
                "reconnect.return_value": 0,
                "is_connected.return_value": True,
                "publish.side_effect": publish,
            }
        )
        stubs.append(
            mock.patch("paho.mqtt.client.Client", return_value=client)
        )

    except ImportError:
        pass

    try:
        import smpplib.client  # noqa: F401

        stubs.append(
            mock.patch(
                "smpplib.client.Client.send_message",
                side_effect=work.plain,
            )
        )
        stubs.append(mock.patch("smpplib.client.Client.connect"))
        stubs.append(mock.patch("smpplib.client.Client.bind_transmitter"))
        stubs.append(mock.patch("smpplib.client.Client.unbind"))
        stubs.append(mock.patch("smpplib.client.Client.disconnect"))

    except ImportError:
        pass

    return stubs


@contextlib.contextmanager
def _watched(work):
    """Run with every outbound path replaced by a counter."""
    sent = mock.MagicMock(side_effect=work.plain)
    with (
        mock.patch("requests.post", side_effect=work.http),
        mock.patch("requests.get", side_effect=work.http),
        mock.patch("requests.put", side_effect=work.http),
        mock.patch("requests.patch", side_effect=work.http),
        mock.patch("apprise.plugins.base.time.sleep"),
        # Socket and mail based services never leave the machine
        mock.patch.object(socket.socket, "connect"),
        mock.patch.object(socket.socket, "sendall", sent),
        mock.patch.object(socket.socket, "send", sent),
        mock.patch.object(socket.socket, "recv", return_value=b""),
        mock.patch("smtplib.SMTP") as smtp,
        mock.patch("smtplib.SMTP_SSL") as smtps,
        contextlib.ExitStack() as extra,
    ):

        def sendmail(*args, **kwargs):
            """Count the call; an empty mapping means everything arrived."""
            work.plain()
            return {}

        # sendmail() reports the addresses it could NOT reach, so an
        # empty mapping is what success looks like.
        for server in (smtp, smtps):
            session = server.return_value.__enter__.return_value
            session.sendmail.side_effect = sendmail
            server.return_value.sendmail.side_effect = sendmail

        for stub in _protocol_stubs(work):
            extra.enter_context(stub)

        yield


def _deliver(obj, work, notify_type=NotifyType.INFO):
    """Deliver once; report whether it worked and what it cost."""
    before = work.count
    outcome = obj.send(
        body="test",
        title="test",
        notify_type=notify_type,
        attach=AppriseAttachment(ATTACHMENT),
    )

    return bool(outcome), work.count - before


@pytest.mark.filterwarnings("ignore::ResourceWarning")
@pytest.mark.parametrize("name", TRACKED_IDS)
def test_retry_does_not_repeat_delivery(name):
    """A retry only picks up what the first attempt did not finish."""

    if name in NEEDS_ITS_OWN_SERVICE:
        pytest.skip(f"{name}: {NEEDS_ITS_OWN_SERVICE[name]}")

    work = _Work(RESPONSES.get(name))
    token = _delivery_tracker.set(set())
    try:
        with _watched(work):
            # Built inside the patches; a service that opens its own
            # client in __init__ has to pick up the stub, not a real one.
            obj = Apprise.instantiate(TRACKED[name], suppress_exceptions=True)
            if obj is None:
                # The service needs a package this build does not have
                pytest.skip(f"{name}: not available in this build")

            kind = NOTIFY_TYPES.get(name, NotifyType.INFO)
            delivered, first = _deliver(obj, work, kind)

            # Watch what the second pass records; the first one already
            # delivered everything, so it should record nothing at all.
            with delivery_marks() as repeated:
                still_ok, second = _deliver(obj, work, kind)

    finally:
        _delivery_tracker.reset(token)

    # The first pass has to actually deliver something, otherwise this
    # case proves nothing at all.
    assert first > 0, (
        f"{name}: nothing was delivered on the first attempt, so this"
        " case cannot show whether a retry repeats itself"
    )

    # A first pass that failed leaves nothing recorded, and repeating it
    # is the whole point of a retry.  The case only means something when
    # the first pass worked.
    assert delivered, (
        f"{name}: the first attempt reported failure, so this case"
        " cannot show whether a retry repeats itself"
    )

    # Skipping what already arrived is still a success.  A service
    # that reports failure here would turn a healthy retry into an
    # error the caller never had before.
    assert still_ok, (
        f"{name}: the second attempt reported failure even though"
        " everything had already been delivered"
    )

    # Whatever work is left on the second pass, it is not a delivery.
    # A recorded target means that target heard from us twice.
    assert not repeated, (
        f"{name}: the second attempt delivered to {repeated[0]!r} again"
    )

    # Everything the first pass sent is recorded, so the second pass has
    # less to do.  Equal counts mean the message went out twice.
    assert second < first, (
        f"{name}: the second attempt did the same work as the first"
        f" ({second} of {first}); a retry would deliver twice"
    )
