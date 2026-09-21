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

"""Covers the skip paths that sit behind another step.

Several services only reach part of their delivery tracking after
something earlier has finished: a message split into pieces, an upload, a
batch of devices, a channel listing. A plain "everything is already
delivered" run never gets there, because the outer target check skips the
whole loop before the inner one can run.

Each case here answers "yes, already delivered" only for the inner piece
under test, so the service walks its outer loop normally and then finds
the inner work already done.
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

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.base import NotifyBase, _delivery_tracker

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")
ATTACHMENT = os.path.join(TEST_VAR_DIR, "apprise-test.gif")

# A response wide enough that a service accepts it and carries on.
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
        "post": {"id": 1},
        "upload_url": "https://localhost/u",
        "file_id": "F1",
        "file_name": "apprise-test.gif",
        "file_type": "image/gif",
        "file_url": "https://localhost/x",
        "media_id": 1,
        "media_id_string": "1",
        "content_uri": "mxc://localhost/1",
        "event_id": "e1",
        "room_id": "!r:localhost",
        "user_id": "@u:localhost",
        "url": "https://cdn.example/x",
        "data": {"url": "https://cdn.example/x", "id": "1"},
        "result": {"message_id": 1, "id": "1", "status": "ok"},
        "json": {"errors": []},
        "requestId": "1",
        "messages": [{"status": "0", "message-id": "1"}],
    }
)


def _ok(*args, **kwargs):
    """Return a response a plugin will treat as a success."""
    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = OK_BODY
    response.text = OK_BODY
    response.headers = {"Content-Type": "application/json"}
    return response


def kind(prefix):
    """Answer "already delivered" only for keys of this kind."""

    def answer(key, per_message=False):
        return isinstance(key, tuple) and bool(key) and key[0] == prefix

    return answer


@contextlib.contextmanager
def _delivered(answer, clients=(), methods=(), obj=None):
    """Run with the outside world replaced and one answer pre-decided."""
    with (
        mock.patch("requests.post", side_effect=_ok),
        mock.patch("requests.get", side_effect=_ok),
        mock.patch("requests.put", side_effect=_ok),
        mock.patch("requests.patch", side_effect=_ok),
        mock.patch("apprise.plugins.base.time.sleep"),
        mock.patch.object(socket.socket, "connect"),
        mock.patch.object(socket.socket, "sendall"),
        mock.patch.object(socket.socket, "send"),
        mock.patch.object(socket.socket, "recv", return_value=b""),
        mock.patch.object(NotifyBase, "is_delivered", side_effect=answer),
        contextlib.ExitStack() as extra,
    ):
        for dotted in clients:
            extra.enter_context(mock.patch(dotted))

        for attr, value in methods:
            extra.enter_context(
                mock.patch.object(type(obj), attr, return_value=value)
            )

        yield


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


def test_telegram_skips_a_message_piece_already_sent(tracker):
    """Telegram leaves a piece of a split message alone once it lands."""

    obj = _build("tgram://123456789:ABCdefGHIjklMNOpqrSTUvwxYZ1234567890/111/")
    with _delivered(kind("body")):
        obj.send(body="test", title="test")


def test_humhub_skips_an_attachment_already_uploaded(tracker):
    """HumHub leaves an upload alone once it is on the post."""

    obj = _build("humhubs://mytoken@hostname/1")
    with _delivered(kind("attachment")):
        obj.send(
            body="test", title="test", attach=AppriseAttachment(ATTACHMENT)
        )


def test_pushbullet_skips_an_attachment_already_sent(tracker):
    """PushBullet leaves an upload alone once it has gone out."""

    obj = _build("pbul://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/#chan1")
    with _delivered(kind("attachment")):
        obj.send(
            body="test", title="test", attach=AppriseAttachment(ATTACHMENT)
        )


def test_pushover_clears_the_title_for_a_sent_attachment(tracker):
    """Pushover drops the title once the first upload has gone out."""

    obj = _build(
        "pover://uuuuuuuuuuuuuuuuuuuuuuuuuuuuuu@"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/DEVICE1/"
    )
    with _delivered(kind("attachment")):
        obj.send(
            body="test", title="test", attach=AppriseAttachment(ATTACHMENT)
        )


def test_pushsafer_blanks_the_message_for_a_sent_batch(tracker):
    """PushSafer stops repeating the text once a batch has gone out."""

    obj = _build("psafer://eeeeeeeeeeeeeeeeeeee/12")
    with _delivered(kind("attachment")):
        obj.send(
            body="test", title="test", attach=AppriseAttachment(ATTACHMENT)
        )


def test_home_assistant_skips_a_batch_already_sent(tracker):
    """Home Assistant leaves a finished batch of devices alone."""

    # The ":" form gives one service several devices, and those are what
    # get split into batches.
    obj = _build("hassio://localhost/long.lived.token/notify.mobile:dev1,dev2")
    assert obj.targets[0][2] == ["dev1", "dev2"]

    with _delivered(kind("batch")):
        obj.send(body="test", title="test")


def test_smpp_skips_a_segment_already_sent(tracker):
    """SMPP leaves a message part alone once it has gone out."""

    pytest.importorskip("smpplib")
    obj = _build("smpp://user:pass@localhost:2775/12125550000/12125550001")
    with _delivered(kind("part"), clients=["smpplib.client.Client"]):
        obj.send(body="test", title="test")


def test_twitter_skips_a_recipient_already_messaged(tracker):
    """Twitter leaves a direct message alone once it has arrived."""

    obj = _build("twitter://ck/cs/at/as/user1")

    def answer(key, per_message=False):
        # Twitter pairs the message number with the recipient
        return (
            isinstance(key, tuple)
            and len(key) == 2
            and isinstance(key[0], int)
        )

    with _delivered(answer, methods=[("_user_lookup", {"user1": 1})], obj=obj):
        obj.send(body="test", title="test")


def test_irc_skips_a_channel_and_a_user_already_reached(tracker):
    """IRC leaves a channel or a user alone once the message lands."""

    obj = _build("ircs://nick@localhost/%23chan1/@bob")
    client = "apprise.plugins.irc.base.IRCClient"

    with _delivered(kind("channel"), clients=[client]):
        obj.send(body="test", title="test")

    with _delivered(kind("user"), clients=[client]):
        obj.send(body="test", title="test")


def test_emby_skips_a_session_already_notified(tracker):
    """Emby leaves a session alone once it has the message."""

    obj = _build("emby://user:pass@localhost")
    with _delivered(
        lambda key, per_message=False: True,
        methods=[("login", True), ("sessions", {"abc": {}})],
        obj=obj,
    ):
        obj.send(body="test", title="test")


def test_twist_skips_a_channel_already_posted(tracker):
    """Twist leaves a channel alone once it has the message."""

    obj = _build("twist://password:user1@example.com")

    # Twist normally learns its channels from the server
    obj.channel_ids = {"1:2"}

    with _delivered(
        lambda key, per_message=False: True,
        methods=[("login", True), ("get_channels", {"general": 1})],
        obj=obj,
    ):
        obj.send(body="test", title="test")


def test_rocketchat_skips_a_room_already_reached(tracker):
    """Rocket.Chat leaves a room alone once it has the message."""

    obj = _build("rocket://user:pass@localhost/room1")
    assert obj.rooms == ["room1"]

    with _delivered(
        lambda key, per_message=False: True,
        methods=[("login", True), ("logout", True)],
        obj=obj,
    ):
        obj.send(body="test", title="test", notify_type=NotifyType.INFO)


def test_matrix_skips_a_user_already_reached(tracker):
    """Matrix leaves a direct message alone once it has arrived."""

    obj = _build("matrix://user:pass@localhost/@bob")
    assert obj.users

    with _delivered(kind("user")):
        obj.send(body="test", title="test")


def test_matrix_skips_an_attachment_already_sent(tracker):
    """Matrix leaves an upload alone once it is in the room."""

    obj = _build("matrix://user:pass@localhost/#room1")
    prepared = [{"body": "x", "msgtype": "m.image", "url": "mxc://x/1"}]

    with _delivered(
        kind("attachment"),
        methods=[("_send_attachments", prepared)],
        obj=obj,
    ):
        obj.send(
            body="test", title="test", attach=AppriseAttachment(ATTACHMENT)
        )


def test_telegram_skips_an_attachment_already_uploaded(tracker):
    """Telegram leaves an upload alone once it has gone out."""

    obj = _build("tgram://123456789:ABCdefGHIjklMNOpqrSTUvwxYZ1234567890/111/")
    target = obj.targets[0]

    with _delivered(kind("attachment")):
        assert (
            obj._send_attachments(
                target,
                notify_type=NotifyType.INFO,
                attach=AppriseAttachment(ATTACHMENT),
            )
            is True
        )


def test_slack_skips_an_upload_every_channel_already_has(tracker):
    """Slack moves on when no channel still needs the upload."""

    obj = _build("slack://xoxb-1234-1234-abc123/#chan1")

    # Slack answers each call with the channel it posted to
    answer = {
        "ok": True,
        "channel": "C1",
        "file_id": "F1",
        "upload_url": "https://localhost/u",
        "files": [{"id": "F1"}],
    }

    with _delivered(kind("attachment"), methods=[("_send", answer)], obj=obj):
        obj.send(
            body="test", title="test", attach=AppriseAttachment(ATTACHMENT)
        )


def test_slack_stops_when_an_upload_is_refused(tracker):
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
        mock.patch("requests.post", side_effect=_ok),
        mock.patch("requests.get", side_effect=_ok),
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


def test_aprs_skips_a_callsign_already_reached(tracker):
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


def test_vapid_counts_an_endpoint_already_reached(tracker, tmpdir):
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
        mock.patch("requests.post", side_effect=_ok) as posted,
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


def test_matrix_skips_an_encrypted_attachment_already_sent(tracker):
    """Matrix leaves an encrypted upload alone once it is in the room."""

    pytest.importorskip("cryptography")

    obj = _build("matrixs://user:pass@localhost/#room1?e2ee=yes")
    if not (obj.e2ee and obj.secure):
        pytest.skip("this build has no end-to-end encryption support")

    prepared = [{"body": "x", "msgtype": "m.image", "url": "mxc://x/1"}]

    with _delivered(
        kind("attachment"),
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
        obj=obj,
    ):
        obj.send(
            body="test", title="test", attach=AppriseAttachment(ATTACHMENT)
        )


def test_matrix_skips_a_message_already_in_the_room(tracker):
    """Matrix leaves a room's message alone once it has arrived."""

    obj = _build("matrix://user:pass@localhost/#room1")

    with _delivered(
        kind("message"),
        methods=[
            ("_room_join", "!room1:localhost"),
            ("_login", True),
            ("_whoami", {}),
        ],
        obj=obj,
    ):
        obj.send(body="test", title="test")


def test_matrix_skips_an_encrypted_message_already_sent(tracker):
    """Matrix leaves an encrypted message alone once it has arrived."""

    pytest.importorskip("cryptography")

    obj = _build("matrixs://user:pass@localhost/#room1?e2ee=yes")
    if not (obj.e2ee and obj.secure):
        pytest.skip("this build has no end-to-end encryption support")

    with _delivered(
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
        obj=obj,
    ):
        obj.send(body="test", title="test")


def test_matrix_skips_an_image_already_posted(tracker):
    """Matrix leaves the notification image alone once it is posted."""

    # The inline image is only posted by the v2 API
    obj = _build("matrix://user:pass@localhost/#room1?image=yes&version=2")

    with _delivered(
        kind("image"),
        methods=[
            ("_room_join", "!room1:localhost"),
            ("_login", True),
            ("_whoami", {}),
        ],
        obj=obj,
    ):
        obj.send(body="test", title="test")
