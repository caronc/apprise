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

"""Proves that a retry never re-notifies a target that already succeeded.

Every service able to reach more than one target in a single call is
driven here with two targets, one of which always refuses the message.
Two things are then checked:

  - the healthy target is contacted exactly once, no matter how many
    retries were asked for, and
  - the broken one is retried on every attempt.

A per-service baseline runs first so a badly written entry in the table
below shows up as a broken entry rather than a false pass.
"""

# Disable logging for a cleaner testing output
from json import dumps
import logging
from unittest import mock

from helpers import OK_FIELDS
import pytest
import requests

from apprise import Apprise

logging.disable(logging.CRITICAL)

# Number of retries requested by every case below.
RETRY = 2

# Stand-in credentials; long enough to satisfy the usual token checks.
TOKEN = "a" * 32

# Each entry drives one service.
#
#   name   -- the plugin, used only to name the test
#   url    -- a URL carrying exactly two targets
#   good   -- text that appears in the request for the healthy target
#   bad    -- text that appears in the request for the broken target
#   body   -- extra response fields this service needs to see.  The
#             reserved key "__http__" sets the status code this
#             service treats as a success (default 200).
FLEET = (
    (
        "telegram",
        "tgram://123456789:ABCdefGHIjklMNOpqrSTUvwxYZ1234567890/111/999/",
        "111",
        "999",
        {},
    ),
    (
        "bulkvs",
        "bulkvs://user:pass@12125550000/12125550001/12125559999/",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "httpsms",
        f"httpsms://{TOKEN}@12125550000/12125550001/12125559999/",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "telnyx",
        f"telnyx://{TOKEN}@12125550000/12125550001/12125559999/",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "zulip",
        f"zulip://botname@apprise/{'b' * 32}/channel1/channel999",
        "channel1",
        "channel999",
        {},
    ),
    (
        "nextcloudtalk",
        "nctalk://user:pass@localhost/room1/room999",
        "room1",
        "room999",
        {},
    ),
    (
        "brevo",
        f"brevo://{TOKEN}:user@example.com/one@example.ca/nine@example.ca",
        "one@example.ca",
        "nine@example.ca",
        {},
    ),
    (
        "resend",
        f"resend://{TOKEN}:user@example.com/one@example.ca/nine@example.ca",
        "one@example.ca",
        "nine@example.ca",
        {},
    ),
    (
        "postmark",
        f"postmark://{TOKEN}:user@example.com/one@example.ca/nine@example.ca",
        "one@example.ca",
        "nine@example.ca",
        {},
    ),
    (
        "sendgrid",
        f"sendgrid://{TOKEN}:user@example.com/one@example.ca/nine@example.ca",
        "one@example.ca",
        "nine@example.ca",
        {},
    ),
    (
        "mailersend",
        (
            f"mailersend://{TOKEN}:user@example.com"
            "/one@example.ca/nine@example.ca"
        ),
        "one@example.ca",
        "nine@example.ca",
        {},
    ),
    (
        "pushbullet",
        f"pbul://{TOKEN}/#chan1/#chan999",
        "chan1",
        "chan999",
        {},
    ),
    (
        "seven",
        f"seven://{TOKEN}/12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "line",
        f"line://{TOKEN}/target0001/target9999",
        "target0001",
        "target9999",
        {},
    ),
    (
        "join",
        f"join://{TOKEN}/device0001/device9999",
        "device0001",
        "device9999",
        {},
    ),
    (
        "kavenegar",
        "kavenegar://12125550000/12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "viber",
        f"viber://{TOKEN}/t0001/t9999?from=Bot",
        "t0001",
        "t9999",
        # Viber reports its own outcome in a numeric status field
        {"status": 0},
    ),
    (
        "clickatell",
        f"clickatell://12125550000@{TOKEN}/12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "d7networks",
        f"d7sms://{TOKEN}@12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "exotel",
        f"exotel://sid:{TOKEN}@12125550000/12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "vonage",
        f"vonage://AC{TOKEN}:{TOKEN}@12125550000/12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "whatsapp",
        f"whatsapp://{TOKEN}@12125550000/12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "voipms",
        "voipms://pass:user@example.com/12125550000/12125550001/12125559999",
        # VoIPms drops the leading country digit before sending
        "2125550001",
        "2125559999",
        {"status": "success", "message": "ok"},
    ),
    (
        "sfr",
        "sfr://user:pass@spaceid/12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "bulksms",
        "bulksms://user:pass@12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "pingram",
        f"pingram://pingram_sk_{TOKEN}/12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "rocketchat",
        "rocket://user:pass@localhost/#chan0001/#chan9999",
        "chan0001",
        "chan9999",
        {"status": "success"},
    ),
    (
        "revolt",
        f"revolt://{TOKEN}/chan0001/chan9999",
        "chan0001",
        "chan9999",
        {},
    ),
    (
        "ntfy",
        "ntfy://localhost/topic0001/topic9999",
        "topic0001",
        "topic9999",
        {},
    ),
    (
        "reddit",
        f"reddit://user:pass@{TOKEN}/{TOKEN}/sub0001/sub9999",
        "sub0001",
        "sub9999",
        # Reddit authenticates first, then posts
        {"json": {"errors": []}, "access_token": "abc", "expires_in": 3600},
    ),
    (
        "bark",
        "bark://localhost/dev0001/dev9999",
        "dev0001",
        "dev9999",
        {},
    ),
    (
        "threema",
        f"threema://*GATEWAY@{TOKEN}/user0001/user9999",
        "user0001",
        "user9999",
        {},
    ),
    (
        "twilio",
        f"twilio://AC{TOKEN}:{TOKEN}@12125550000/12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "ifttt",
        f"ifttt://{TOKEN}@event0001/event9999",
        "event0001",
        "event9999",
        {},
    ),
    (
        "fortysixelks",
        "46elks://user:pass@sender/12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "evolution",
        f"evolution://{TOKEN}@localhost/inst/12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
    (
        "notifiarr",
        f"notifiarr://{TOKEN}/#1001/#9009",
        "1001",
        "9009",
        {},
    ),
    (
        "dapnet",
        "dapnet://user:pass@localhost/DL0001/DL9999",
        "DL0001",
        "DL9999",
        {"__http__": 201},
    ),
    (
        "flock",
        f"flock://{TOKEN}/u:0001/u:9999",
        "0001",
        "9999",
        {},
    ),
    (
        "pushed",
        f"pushed://{TOKEN}/{TOKEN}/#chan0001/#chan9999",
        "chan0001",
        "chan9999",
        {},
    ),
    (
        "sns",
        f"sns://{TOKEN}/{'b' * 40}/us-east-1/12125550001/12125559999",
        "12125550001",
        "12125559999",
        {},
    ),
)

# Names only, for readable test ids
FLEET_IDS = [row[0] for row in FLEET]


def _drive(url, body, bad=None):
    """Send one notification and report every request that was made.

    ``bad`` names the target that should be refused; pass None to let
    every target succeed.
    """
    calls = []
    payload = dict(OK_FIELDS)
    payload.update(body)

    # Some services only accept a specific success code
    ok_status = payload.pop("__http__", requests.codes.ok)
    encoded = dumps(payload)

    def handler(target_url, *args, **kwargs):
        # Everything the plugin passed, so a target can be spotted
        # wherever the service happens to put it.
        blob = repr(target_url) + repr(args) + repr(kwargs)
        calls.append(blob)

        response = requests.Request()
        response.status_code = (
            400 if bad is not None and bad in blob else ok_status
        )
        response.content = encoded
        response.text = encoded
        response.headers = {"Content-Type": "application/json"}
        return response

    separator = "&" if "?" in url else "?"
    with (
        mock.patch("requests.post", side_effect=handler),
        mock.patch("requests.get", side_effect=handler),
        mock.patch("requests.put", side_effect=handler),
        mock.patch("requests.patch", side_effect=handler),
        # Keep the run quick; the delays are not what is being tested.
        mock.patch("apprise.plugins.base.time.sleep"),
        mock.patch("apprise.apprise.time.sleep"),
    ):
        aobj = Apprise()
        assert aobj.add(f"{url}{separator}retry={RETRY}&wait=0")
        result = aobj.notify(body="hello")

    return result, calls


@pytest.mark.parametrize(
    ("name", "url", "good", "bad", "body"), FLEET, ids=FLEET_IDS
)
def test_fleet_entry_is_usable(name, url, good, bad, body):
    """Each table entry reaches two targets when nothing goes wrong."""

    obj = Apprise.instantiate(url)
    assert obj is not None, f"{name}: URL did not load"

    # Two separate endpoints are required for this to mean anything
    assert len(obj) == 2, f"{name}: expected 2 targets, got {len(obj)}"

    result, calls = _drive(url, body)
    assert bool(result) is True, f"{name}: baseline delivery failed"

    # One request per target, and each target is recognisable
    assert sum(1 for c in calls if good in c) == 1
    assert sum(1 for c in calls if bad in c) == 1


@pytest.mark.parametrize(
    ("name", "url", "good", "bad", "body"), FLEET, ids=FLEET_IDS
)
def test_fleet_retry_skips_delivered_targets(name, url, good, bad, body):
    """A retry only re-contacts the target that is still failing."""

    result, calls = _drive(url, body, bad=bad)

    delivered = [c for c in calls if good in c]
    refused = [c for c in calls if bad in c]

    # The healthy target hears from us once and is never repeated
    assert len(delivered) == 1, (
        f"{name}: healthy target notified {len(delivered)} times;"
        " mark_delivered() is missing or in the wrong place"
    )

    # The broken one is tried again on every attempt.  A service that
    # re-authenticates before each post makes more than one request per
    # attempt, so this is a floor rather than an exact count.
    assert len(refused) >= RETRY + 1, (
        f"{name}: broken target tried {len(refused)} times,"
        f" expected at least {RETRY + 1}"
    )

    # Something genuinely failed, so the call reports failure
    assert bool(result) is False
