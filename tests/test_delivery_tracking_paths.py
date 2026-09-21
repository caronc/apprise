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

"""Cover delivery-skip paths that depend on an earlier step.

Each case lets the outer workflow run, then reports that only the inner
message, upload, batch, or lookup was already completed.
"""

# Disable logging for a cleaner testing output
import contextlib
import logging
import os
import socket
from unittest import mock

from helpers import ATTACHMENT, delivery_marks, ok_response
import pytest

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.base import NotifyBase, _delivery_tracker

logging.disable(logging.CRITICAL)


def kind(prefix):
    """Answer "already delivered" only for keys of this kind."""

    def answer(key, per_message=False):
        return isinstance(key, tuple) and bool(key) and key[0] == prefix

    return answer


def _nothing(key, per_message=False):
    """Answer "not delivered yet" for everything."""
    return False


def _everything(key, per_message=False):
    """Answer "already delivered" for everything."""
    return True


def _send(obj):
    """Deliver a plain message."""
    obj.send(body="test", title="test")


def _send_attached(obj):
    """Deliver a message that carries a file."""
    obj.send(body="test", title="test", attach=AppriseAttachment(ATTACHMENT))


@contextlib.contextmanager
def _offline(answer, clients=(), methods=(), obj=None):
    """Replace every outbound path and count what the service uses."""

    direct = []
    stubs = []
    sent = mock.MagicMock()
    with (
        mock.patch("requests.post", side_effect=ok_response) as post,
        mock.patch("requests.get", side_effect=ok_response) as get,
        mock.patch("requests.put", side_effect=ok_response) as put,
        mock.patch("requests.patch", side_effect=ok_response) as patch,
        mock.patch("apprise.plugins.base.time.sleep"),
        mock.patch.object(socket.socket, "connect"),
        mock.patch.object(socket.socket, "sendall", sent),
        mock.patch.object(socket.socket, "send", sent),
        mock.patch.object(socket.socket, "recv", return_value=b""),
        mock.patch.object(NotifyBase, "is_delivered", side_effect=answer),
        delivery_marks() as recorded,
        contextlib.ExitStack() as extra,
    ):
        direct.extend((post, get, put, patch, sent))

        for dotted in clients:
            # A service with its own client speaks through the stub
            # rather than through requests, so it is counted too.
            stubs.append(extra.enter_context(mock.patch(dotted)))

        for attr, value in methods:
            # A step answered for us is still work the service asked
            # for, so it is counted like any other outbound call.
            direct.append(
                extra.enter_context(
                    mock.patch.object(type(obj), attr, return_value=value)
                )
            )

        def work():
            """Return how far the service has reached out so far."""
            return sum(call.call_count for call in direct) + sum(
                len(stub.mock_calls) for stub in stubs
            )

        yield work, recorded


def _skips(url, answer, send=None, clients=(), methods=(), setup=None):
    """Deliver twice and prove the pre-decided answer saved work.

    The first run has nothing delivered yet, so it does the whole job.
    The second is told part of it already arrived, and has to leave
    exactly that part alone:

    - it reaches out less often than the first run, so the skipped work
      really was skipped
    - it records nothing it was already told about, so nothing went out
      a second time under a different name
    """

    if send is None:
        send = _send

    done = []
    for pre_decided in (_nothing, answer):
        obj = _build(url)
        if setup is not None:
            setup(obj)

        with _offline(
            pre_decided, clients=clients, methods=methods, obj=obj
        ) as (work, recorded):
            send(obj)

            done.append((work(), list(recorded)))

    (busy, _marked), (quiet, marked) = done

    repeated = [key for key in marked if answer(key)]
    assert not repeated, (
        f"{repeated[0]!r} was sent again even though the service had"
        " already been told it arrived"
    )

    assert quiet < busy, (
        f"the service reached out {quiet} times either way; nothing was"
        " skipped even though it was told the work had already arrived"
    )


@pytest.fixture()
def tracker():
    """Provide an empty tracker for the duration of one test."""
    token = _delivery_tracker.set(set())
    try:
        yield

    finally:
        _delivery_tracker.reset(token)


def _build(url):
    """Load a service and make sure the URL is still good."""
    obj = Apprise.instantiate(url, suppress_exceptions=True)
    assert obj is not None, f"{url} no longer loads"
    return obj


def test_telegram_skips_sent_piece(tracker):
    """Telegram leaves a piece of a split message alone once it lands."""

    _skips(
        "tgram://123456789:ABCdefGHIjklMNOpqrSTUvwxYZ1234567890/111/",
        kind("body"),
    )


def test_humhub_skips_sent_attachment(tracker):
    """HumHub leaves an upload alone once it is on the post."""

    _skips(
        "humhubs://mytoken@hostname/1",
        kind("attachment"),
        send=_send_attached,
    )


def test_pushbullet_skips_sent_attachment(tracker):
    """PushBullet leaves an upload alone once it has gone out."""

    _skips(
        "pbul://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/#chan1",
        kind("attachment"),
        send=_send_attached,
    )


def test_pushover_clears_title_after_skip(tracker):
    """Pushover drops the title once the first upload has gone out."""

    _skips(
        "pover://uuuuuuuuuuuuuuuuuuuuuuuuuuuuuu@"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/DEVICE1/",
        kind("attachment"),
        send=_send_attached,
    )


def test_pushsafer_clears_message_after_skip(tracker):
    """PushSafer stops repeating the text once a batch has gone out."""

    _skips(
        "psafer://eeeeeeeeeeeeeeeeeeee/12",
        kind("attachment"),
        send=_send_attached,
    )


def test_home_assistant_skips_sent_batch(tracker):
    """Home Assistant leaves a finished batch of devices alone."""

    # The ":" form gives one service several devices, and those are what
    # get split into batches.
    url = "hassio://localhost/long.lived.token/notify.mobile:dev1,dev2"
    assert _build(url).targets[0][2] == ["dev1", "dev2"]

    _skips(url, kind("batch"))


def test_smpp_skips_sent_segment(tracker):
    """SMPP leaves a message part alone once it has gone out."""

    pytest.importorskip("smpplib")
    _skips(
        "smpp://user:pass@localhost:2775/12125550000/12125550001",
        kind("part"),
        clients=["smpplib.client.Client"],
    )


def test_twitter_skips_sent_recipient(tracker):
    """Twitter leaves a direct message alone once it has arrived."""

    def answer(key, per_message=False):
        # Twitter pairs the message number with the recipient
        return (
            isinstance(key, tuple)
            and len(key) == 2
            and isinstance(key[0], int)
        )

    _skips(
        "twitter://ck/cs/at/as/user1",
        answer,
        methods=[("_user_lookup", {"user1": 1})],
    )


def test_irc_skips_sent_targets(tracker):
    """IRC leaves a channel or a user alone once the message lands."""

    url = "ircs://nick@localhost/%23chan1/@bob"
    client = ["apprise.plugins.irc.base.IRCClient"]

    _skips(url, kind("channel"), clients=client)
    _skips(url, kind("user"), clients=client)


def test_emby_skips_sent_session(tracker):
    """Emby leaves a session alone once it has the message."""

    _skips(
        "emby://user:pass@localhost",
        _everything,
        methods=[("login", True), ("sessions", {"abc": {}})],
    )


def test_twist_skips_sent_channel(tracker):
    """Twist leaves a channel alone once it has the message."""

    def learned(obj):
        # Twist normally learns its channels from the server
        obj.channel_ids = {"1:2"}

    _skips(
        "twist://password:user1@example.com",
        _everything,
        methods=[("login", True), ("get_channels", {"general": 1})],
        setup=learned,
    )


def test_rocketchat_skips_sent_room(tracker):
    """Rocket.Chat leaves a room alone once it has the message."""

    url = "rocket://user:pass@localhost/room1"
    assert _build(url).rooms == ["room1"]

    _skips(
        url,
        _everything,
        methods=[("login", True), ("logout", True)],
    )


def test_matrix_skips_sent_user(tracker):
    """Matrix leaves a direct message alone once it has arrived."""

    url = "matrix://user:pass@localhost/@bob"
    assert _build(url).users

    _skips(url, kind("user"))


def test_matrix_skips_sent_attachment(tracker):
    """Matrix leaves an upload alone once it is in the room."""

    prepared = [{"body": "x", "msgtype": "m.image", "url": "mxc://x/1"}]

    _skips(
        "matrix://user:pass@localhost/#room1",
        kind("attachment"),
        send=_send_attached,
        methods=[("_send_attachments", prepared)],
    )


def test_telegram_skips_sent_attachment(tracker):
    """Telegram leaves an upload alone once it has gone out."""

    def send(obj):
        assert (
            obj._send_attachments(
                obj.targets[0],
                notify_type=NotifyType.INFO,
                attach=AppriseAttachment(ATTACHMENT),
            )
            is True
        )

    _skips(
        "tgram://123456789:ABCdefGHIjklMNOpqrSTUvwxYZ1234567890/111/",
        kind("attachment"),
        send=send,
    )


def test_slack_skips_shared_upload(tracker):
    """Slack moves on when no channel still needs the upload."""

    # Slack answers each call with the channel it posted to
    answer = {
        "ok": True,
        "channel": "C1",
        "file_id": "F1",
        "upload_url": "https://localhost/u",
        "files": [{"id": "F1"}],
    }

    _skips(
        "slack://xoxb-1234-1234-abc123/#chan1",
        kind("attachment"),
        send=_send_attached,
        methods=[("_send", answer)],
    )


def test_slack_stops_after_upload_failure(tracker):
    """Slack gives up on the attachment once an upload is refused."""

    obj = _build("slack://xoxb-1234-1234-abc123/#chan1")

    posted = {
        "ok": True,
        "channel": "C1",
        "file_id": "F1",
        "upload_url": "https://localhost/u",
        "files": [{"id": "F1"}],
    }

    def answer(url, *args, **kwargs):
        # The upload itself is refused; everything else is accepted
        return None if str(url).endswith("/u") else posted

    with (
        mock.patch("requests.post", side_effect=ok_response),
        mock.patch("requests.get", side_effect=ok_response),
        mock.patch("apprise.plugins.base.time.sleep"),
        mock.patch.object(
            NotifyBase,
            "is_delivered",
            side_effect=lambda key, per_message=False: False,
        ),
        mock.patch.object(type(obj), "_send", side_effect=answer),
    ):
        assert (
            obj.send(
                body="test",
                title="test",
                attach=AppriseAttachment(ATTACHMENT),
            )
            is False
        )


def test_aprs_skips_sent_callsign(tracker):
    """APRS leaves a callsign alone once the message has gone out."""

    obj = _build("aprs://DF1ABC:12345@DF1DEF/DF1GHI")

    # APRS talks over a socket rather than HTTP, so stand one in.  The
    # login exchange is answered for us; it is not what is under test.
    stand_in = mock.MagicMock()

    with (
        mock.patch("socket.create_connection", return_value=stand_in),
        mock.patch.object(type(obj), "aprsis_login", return_value=True),
        mock.patch.object(type(obj), "socket_reset"),
        mock.patch("apprise.plugins.base.time.sleep"),
        mock.patch.object(
            NotifyBase,
            "is_delivered",
            side_effect=lambda key, per_message=False: True,
        ),
    ):
        obj.send(body="test", title="test")

    # Every callsign was skipped, so nothing was written to the socket
    assert stand_in.sendall.call_count == 0


def test_vapid_counts_sent_endpoint(tracker, tmpdir):
    """Vapid counts a skipped endpoint so a retry still reports success."""

    pytest.importorskip("cryptography")

    from apprise import asset
    from apprise.common import PersistentStoreMode
    from apprise.plugins.vapid import NotifyVapid
    from apprise.plugins.vapid.subscription import (
        WebPushSubscriptionManager,
    )

    # The key pair a browser hands over when it subscribes
    p256dh = (
        "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
        "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
    )

    work = str(tmpdir.mkdir("vapid-skip"))
    subfile = os.path.join(work, "subscriptions.json")

    manager = WebPushSubscriptionManager()
    assert manager.add(
        {
            "endpoint": "https://web.push.apple.com/ABC",
            "keys": {"p256dh": p256dh, "auth": "k9Xzm43nBGo="},
        },
        name="abc123",
    )
    assert manager.write(subfile)

    obj = NotifyVapid(
        "user@example.ca",
        targets=["abc123"],
        subfile=subfile,
        asset=asset.AppriseAsset(
            storage_mode=PersistentStoreMode.FLUSH,
            storage_path=work,
            pem_autogen=True,
        ),
    )

    with (
        mock.patch("requests.post", side_effect=ok_response) as posted,
        mock.patch("apprise.plugins.base.time.sleep"),
        mock.patch.object(
            NotifyBase,
            "is_delivered",
            side_effect=lambda key, per_message=False: True,
        ),
    ):
        # The endpoint was reached on an earlier attempt.  It still
        # counts, so this reports success instead of "nothing was sent".
        assert obj.send(body="test", title="test") is True

    # ...and nothing was pushed a second time
    assert posted.call_count == 0


def test_matrix_skips_sent_encrypted_attachment(tracker):
    """Matrix leaves an encrypted upload alone once it is in the room."""

    pytest.importorskip("cryptography")

    url = "matrixs://user:pass@localhost/#room1?e2ee=yes"
    obj = _build(url)
    if not (obj.e2ee and obj.secure):
        pytest.skip("this build has no end-to-end encryption support")

    prepared = [{"body": "x", "msgtype": "m.image", "url": "mxc://x/1"}]

    _skips(
        url,
        kind("attachment"),
        send=_send_attached,
        methods=[
            ("_send_attachments", prepared),
            ("_room_join", "!room1:localhost"),
            ("_e2ee_send_to_room", True),
            ("_e2ee_get_megolm", object()),
            ("_e2ee_room_encrypted", True),
            ("_e2ee_setup", True),
            # Signing in is not what is under test here
            ("_login", True),
            ("_whoami", {}),
        ],
    )


def test_matrix_skips_sent_message(tracker):
    """Matrix leaves a room's message alone once it has arrived."""

    _skips(
        "matrix://user:pass@localhost/#room1",
        kind("message"),
        methods=[
            ("_room_join", "!room1:localhost"),
            ("_login", True),
            ("_whoami", {}),
        ],
    )


def test_matrix_skips_sent_encrypted_message(tracker):
    """Matrix leaves an encrypted message alone once it has arrived."""

    pytest.importorskip("cryptography")

    url = "matrixs://user:pass@localhost/#room1?e2ee=yes"
    obj = _build(url)
    if not (obj.e2ee and obj.secure):
        pytest.skip("this build has no end-to-end encryption support")

    _skips(
        url,
        kind("message"),
        methods=[
            ("_room_join", "!room1:localhost"),
            ("_e2ee_setup", True),
            ("_e2ee_room_encrypted", True),
            ("_e2ee_send_to_room", True),
            ("_e2ee_get_megolm", object()),
            ("_login", True),
            ("_whoami", {}),
        ],
    )


def test_matrix_skips_sent_image(tracker):
    """Matrix leaves the notification image alone once it is posted."""

    # The inline image is only posted by the v2 API
    _skips(
        "matrix://user:pass@localhost/#room1?image=yes&version=2",
        kind("image"),
        methods=[
            ("_room_join", "!room1:localhost"),
            ("_login", True),
            ("_whoami", {}),
        ],
    )
