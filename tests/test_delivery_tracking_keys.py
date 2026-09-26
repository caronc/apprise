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


"""Ensure similar values remain distinct delivery targets.

The same value may identify different target types, such as SMS and
WhatsApp. Each type needs its own key so neither hides the other.
"""

# Disable logging for a cleaner testing output
import contextlib
import logging
from unittest import mock

from helpers import ATTACHMENT, ok_response
import pytest

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.base import NotifyBase, _delivery_tracker

logging.disable(logging.CRITICAL)

# Each URL below names the same value twice, once under each kind of
# target the service understands.
LOOK_ALIKE = {
    "kook": ("kook://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/1234567890/@1234567890"),
    "mattermost": (
        "mmost://user@localhost/3ccdd113474722377935511fc85d3dd4"
        "?mode=bot&channels=%23abc,%2Babc"
    ),
    "pushover": (
        "pover://abcdefghijklmnopqrstuvwxyz1234@"
        "token1234567890abcdefghijklmno/device1/"
        "#abcdefghijklmnopqrstuvwxyz1234"
    ),
    "pushy": "pushy://_/#abc/@abc?key=apikey",
    "twilio": (
        "twilio://ACaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb@12125550000/"
        "12125550001/whatsapp:12125550001"
    ),
}


@contextlib.contextmanager
def _watched():
    """Run with the network replaced and every key asked about recorded."""

    seen = []

    def answer(key, per_message=False):
        seen.append(key)
        return False

    with (
        mock.patch("requests.post", side_effect=ok_response),
        mock.patch("requests.get", side_effect=ok_response),
        mock.patch("requests.put", side_effect=ok_response),
        mock.patch("requests.patch", side_effect=ok_response),
        mock.patch("apprise.plugins.base.time.sleep"),
        mock.patch.object(NotifyBase, "is_delivered", side_effect=answer),
    ):
        yield seen


@pytest.mark.parametrize("name", sorted(LOOK_ALIKE))
def test_target_kinds_stay_distinct(name):
    """The same value under two kinds produces two different keys."""

    obj = Apprise.instantiate(LOOK_ALIKE[name], suppress_exceptions=True)
    assert obj is not None, f"{name}: URL no longer loads"

    with _watched() as seen:
        obj.send(body="test", title="test", notify_type=NotifyType.INFO)

    # Both destinations were walked
    assert len(seen) == 2, f"{name}: expected two targets, saw {seen}"

    # ... and neither one hides the other
    distinct = {(type(key), repr(key)) for key in seen}
    assert len(distinct) == 2, (
        f"{name}: both targets share the delivery key {seen[0]!r}; one"
        " delivery would hide the other"
    )


def test_serwersms_mms_tracking():
    """An MMS that arrives is recorded just like a plain message."""

    obj = Apprise.instantiate(
        "serwersms://user:pass@SenderA/+48123456789",
        suppress_exceptions=True,
    )
    assert obj is not None

    token = _delivery_tracker.set(set())
    try:
        with (
            mock.patch("requests.post", side_effect=ok_response) as post,
            mock.patch("apprise.plugins.base.time.sleep"),
        ):
            attach = AppriseAttachment(ATTACHMENT)
            assert obj.send(body="test", title="test", attach=attach) is True
            assert post.call_count == 1

            # A retry has nothing left to send
            post.reset_mock()
            assert obj.send(body="test", title="test", attach=attach) is True
            assert post.call_count == 0

    finally:
        _delivery_tracker.reset(token)


def test_home_assistant_batch_tracking():
    """Each batch of devices is its own delivery."""

    # The ":" form gives one service several devices, and those are what
    # get split into batches
    obj = Apprise.instantiate(
        "hassio://localhost/long.lived.token/notify.mobile:dev1,dev2",
        suppress_exceptions=True,
    )
    assert obj is not None

    token = _delivery_tracker.set(set())
    try:
        with (
            mock.patch("requests.post", side_effect=ok_response) as post,
            mock.patch("apprise.plugins.base.time.sleep"),
        ):
            assert obj.send(body="test", title="test") is True

            # One call per device; neither batch hides the other
            assert post.call_count == 2

    finally:
        _delivery_tracker.reset(token)


def test_smpp_segment_tracking():
    """Each part of a long message is its own delivery."""

    smpplib = pytest.importorskip("smpplib")
    obj = Apprise.instantiate(
        "smpp://user:pass@localhost:2775/12125550000/12125550001",
        suppress_exceptions=True,
    )
    assert obj is not None

    token = _delivery_tracker.set(set())
    try:
        with (
            mock.patch("smpplib.client.Client.connect"),
            mock.patch("smpplib.client.Client.bind_transmitter"),
            mock.patch("smpplib.client.Client.unbind"),
            mock.patch("smpplib.client.Client.disconnect"),
            mock.patch("smpplib.client.Client.send_message") as sent,
            mock.patch("apprise.plugins.base.time.sleep"),
        ):
            assert smpplib is not None
            assert obj.send(body="y" * 400, title="test") is True

            # A long message is split; every part has to go out
            assert sent.call_count > 1

            # A retry has nothing left to send
            sent.reset_mock()
            assert obj.send(body="y" * 400, title="test") is True
            assert sent.call_count == 0

    finally:
        _delivery_tracker.reset(token)
