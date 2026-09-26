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
import asyncio
from collections import Counter
import hashlib
from json import dumps, loads
import logging
from unittest import mock

import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.base import (
    NotifyBase,
    _delivery_index,
    _delivery_memo,
    _delivery_tracker,
)
from apprise.plugins.jira import NotifyJira
from apprise.plugins.opsgenie import NotifyOpsgenie

logging.disable(logging.CRITICAL)

# A Telegram URL aimed at two chats; the second one is made to fail.
TGRAM = "tgram://123456789:ABCdefGHIjklMNOpqrSTUvwxYZ1234567890/111/222/"


def _tgram_post(bad="222", fail_times=None):
    """Build a requests.post replacement that fails one chat.

    - ``bad`` is the chat id that should be refused.
    - ``fail_times`` limits how many times it is refused; None means
      always.
    """
    seen = []
    state = {"n": 0}

    def handler(url, *args, **kwargs):
        data = kwargs.get("data") or {}
        if not isinstance(data, dict):
            try:
                data = loads(data)
            except (TypeError, ValueError):
                data = {}

        chat = str(data.get("chat_id", ""))
        r = requests.Request()
        if chat == bad:
            state["n"] += 1
            refuse = fail_times is None or state["n"] <= fail_times
            r.status_code = 400 if refuse else requests.codes.ok

        else:
            r.status_code = requests.codes.ok

        seen.append((chat, len(data.get("text", "") or "")))
        r.content = dumps({"ok": True, "result": {"message_id": 1}})
        return r

    return handler, seen


class _Dummy(NotifyBase):
    """A tiny plugin used to poke the helpers directly."""

    service_name = "Dummy"
    protocol = "dummy"

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        return True

    def url(self, privacy=False, *args, **kwargs):
        return "dummy://"


def test_helpers_are_inert_without_a_tracker():
    """Nothing is recorded when retries were never requested."""

    obj = _Dummy()

    # No tracker exists, so nothing is ever considered delivered
    assert obj.is_delivered("abc") is False

    # Marking is accepted but changes nothing
    obj.mark_delivered("abc")
    assert obj.is_delivered("abc") is False


def test_tracker_remembers_marked_targets():
    """A marked target reads back as delivered."""

    obj = _Dummy()
    token = _delivery_tracker.set(set())
    try:
        assert obj.is_delivered("abc") is False
        obj.mark_delivered("abc")
        assert obj.is_delivered("abc") is True

        # An unrelated target is untouched
        assert obj.is_delivered("xyz") is False

    finally:
        _delivery_tracker.reset(token)


def test_memo_is_inert_without_retries():
    """Nothing is kept when there is no later attempt to read it."""

    obj = _Dummy()

    obj.remember("key", "value")
    assert obj.recall("key") is None
    assert obj.recall("key", "fallback") == "fallback"


def test_memo_carries_a_value_between_attempts():
    """What one attempt remembers, the next one reads back."""

    obj = _Dummy()
    token = _delivery_memo.set({})
    try:
        assert obj.recall("key") is None

        obj.remember("key", "value")
        assert obj.recall("key") == "value"

        # Writing again replaces what was there
        obj.remember("key", "other")
        assert obj.recall("key") == "other"

        # An unrelated entry is untouched
        assert obj.recall("elsewhere") is None

    finally:
        _delivery_memo.reset(token)


def test_memo_pieces_keep_their_own_value():
    """Part two of a split message does not read part one's value.

    Two pieces can hold identical content, so sharing by default would
    hand the second piece whatever the first stored under the same key.
    """

    obj = _Dummy()
    memo_token = _delivery_memo.set({})
    piece_token = _delivery_index.set(0)
    try:
        obj.remember("key", "first piece")

        # The second piece starts with nothing of its own
        _delivery_index.set(1)
        assert obj.recall("key") is None

        obj.remember("key", "second piece")
        assert obj.recall("key") == "second piece"

        # ... and the first piece still reads back its own
        _delivery_index.set(0)
        assert obj.recall("key") == "first piece"

    finally:
        _delivery_index.reset(piece_token)
        _delivery_memo.reset(memo_token)


def test_memo_per_message_spans_pieces():
    """``per_message`` shares one value across the whole notification."""

    obj = _Dummy()
    memo_token = _delivery_memo.set({})
    piece_token = _delivery_index.set(0)
    try:
        obj.remember("upload", "media-1", per_message=True)

        # Every piece of the message cites the same upload
        _delivery_index.set(1)
        assert obj.recall("upload", per_message=True) == "media-1"

        # The per-piece slot of the same key is untouched
        assert obj.recall("upload") is None

    finally:
        _delivery_index.reset(piece_token)
        _delivery_memo.reset(memo_token)


def test_memo_keys_stay_distinct():
    """Look-alike keys of different types do not collide."""

    obj = _Dummy()
    token = _delivery_memo.set({})
    try:
        obj.remember(1, "number")
        obj.remember("1", "text")
        obj.remember(["1"], "list")

        assert obj.recall(1) == "number"
        assert obj.recall("1") == "text"
        assert obj.recall(["1"]) == "list"

    finally:
        _delivery_memo.reset(token)


def test_memo_does_not_outlive_its_notification():
    """A second notification never reads the first one's working state."""

    obj = _Dummy()

    token = _delivery_memo.set({})
    obj.remember("key", "first")
    assert obj.recall("key") == "first"
    _delivery_memo.reset(token)

    # A fresh notification starts with nothing carried over
    token = _delivery_memo.set({})
    try:
        assert obj.recall("key") is None

    finally:
        _delivery_memo.reset(token)


def test_message_pieces_are_tracked_separately():
    """Part two of a split message is not skipped because of part one."""

    obj = _Dummy()
    token = _delivery_tracker.set(set())
    try:
        # Mark the target against the first piece
        obj.mark_delivered("abc")
        assert obj.is_delivered("abc") is True

        # The second piece has not reached that target yet
        index = _delivery_index.set(1)
        try:
            assert obj.is_delivered("abc") is False
            obj.mark_delivered("abc")
            assert obj.is_delivered("abc") is True

        finally:
            _delivery_index.reset(index)

        # The first piece is still recorded
        assert obj.is_delivered("abc") is True

    finally:
        _delivery_tracker.reset(token)


def test_whole_message_keys_ignore_the_piece():
    """A key marked for the whole message is seen from every piece."""

    obj = _Dummy()
    token = _delivery_tracker.set(set())
    try:
        obj.mark_delivered("icon", per_message=True)

        # The next piece of the same message still sees it
        index = _delivery_index.set(1)
        try:
            assert obj.is_delivered("icon", per_message=True) is True

            # The per-piece slot is left alone
            assert obj.is_delivered("icon") is False

        finally:
            _delivery_index.reset(index)

    finally:
        _delivery_tracker.reset(token)


@pytest.mark.parametrize(
    "key",
    [
        None,
        "",
        0,
        False,
        "a-string",
        3.14,
        b"bytes",
        ("a", "tuple"),
        ["a", "list"],
        {"a": "dict"},
        {"a", "set"},
    ],
)
def test_any_kind_of_key_is_accepted(key):
    """Odd keys are tolerated rather than raising."""

    obj = _Dummy()
    token = _delivery_tracker.set(set())
    try:
        assert obj.is_delivered(key) is False
        obj.mark_delivered(key)
        assert obj.is_delivered(key) is True

    finally:
        _delivery_tracker.reset(token)


class _Unhashable:
    """A value that cannot be hashed and is not a list, dict or set."""

    __hash__ = None

    def __init__(self, label):
        self.label = label

    def __repr__(self):
        return f"_Unhashable({self.label})"


def test_an_unhashable_object_is_still_tracked():
    """A custom unhashable value falls back to its text form."""

    obj = _Dummy()
    token = _delivery_tracker.set(set())
    try:
        first = _Unhashable("one")
        second = _Unhashable("two")

        assert obj.is_delivered(first) is False
        obj.mark_delivered(first)
        assert obj.is_delivered(first) is True

        # A different value is not confused with the first
        assert obj.is_delivered(second) is False

    finally:
        _delivery_tracker.reset(token)


def test_unhashable_keys_stay_distinct():
    """Two different lists are not treated as the same target."""

    obj = _Dummy()
    token = _delivery_tracker.set(set())
    try:
        obj.mark_delivered(["a"])
        assert obj.is_delivered(["a"]) is True
        assert obj.is_delivered(["b"]) is False

    finally:
        _delivery_tracker.reset(token)


@pytest.mark.parametrize(
    "marked, look_alike",
    [
        (False, 0),
        (1, "1"),
        (1, True),
        ((0,), (False,)),
        ("1", b"1"),
    ],
)
def test_look_alike_keys_stay_distinct(marked, look_alike):
    """A key keeps its type, so values Python calls equal stay apart."""

    obj = _Dummy()
    token = _delivery_tracker.set(set())
    try:
        obj.mark_delivered(marked)

        assert obj.is_delivered(marked) is True
        assert obj.is_delivered(look_alike) is False

    finally:
        _delivery_tracker.reset(token)


def test_container_key_does_not_collide_with_text():
    """A container and a string resembling it remain separate targets."""

    obj = _Dummy()
    token = _delivery_tracker.set(set())
    try:
        obj.mark_delivered(["a"])

        assert obj.is_delivered(["a"]) is True
        assert obj.is_delivered('["a"]') is False
        assert obj.is_delivered("['a']") is False

    finally:
        _delivery_tracker.reset(token)


@pytest.mark.parametrize("plugin_cls", (NotifyJira, NotifyOpsgenie))
def test_alert_ids_survive_partial_retry(plugin_cls):
    """A retry keeps request IDs returned by earlier successful batches."""

    obj = plugin_cls("apikey", targets=["@one", "@two"])
    cache_key = hashlib.sha1(b"title").hexdigest()[0:10]

    tracker_token = _delivery_tracker.set(set())
    try:
        with mock.patch.object(
            obj,
            "_fetch",
            side_effect=[(True, "id-one"), (False, None)],
        ):
            assert (
                obj.send(
                    body="body",
                    title="title",
                    notify_type=NotifyType.WARNING,
                )
                is False
            )

        with mock.patch.object(
            obj,
            "_fetch",
            return_value=(True, "id-two"),
        ):
            assert (
                obj.send(
                    body="body",
                    title="title",
                    notify_type=NotifyType.WARNING,
                )
                is True
            )

        assert obj.store.get(cache_key) == ["id-one", "id-two"]
    finally:
        _delivery_tracker.reset(tracker_token)


@mock.patch("requests.post")
def test_no_tracker_survives_a_delivery(mock_post):
    """The tracker never outlives the call that created it."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = dumps({"ok": True})

    aobj = Apprise()
    assert aobj.add(TGRAM + "?retry=2&wait=0")
    aobj.notify(body="hello")

    # Back at rest, nothing is left behind
    assert _delivery_tracker.get() is None


@mock.patch("requests.post")
def test_tracker_released_after_plugin_error(mock_post):
    """An exception still leaves the tracker cleaned up."""

    mock_post.side_effect = RuntimeError("boom")

    aobj = Apprise()
    assert aobj.add(TGRAM + "?retry=1&wait=0")
    aobj.notify(body="hello")

    assert _delivery_tracker.get() is None
    assert _delivery_index.get() == 0


def test_successful_target_not_notified_twice():
    """A retry must not re-deliver to targets that already succeeded."""

    handler, seen = _tgram_post()
    with mock.patch("requests.post", side_effect=handler):
        aobj = Apprise()
        assert aobj.add(TGRAM + "?retry=3&wait=0")
        result = aobj.notify(body="hello")

    counts = Counter(chat for chat, _ in seen)

    # The healthy chat is contacted exactly once
    assert counts["111"] == 1

    # The broken one is retried for every attempt
    assert counts["222"] == 4
    assert bool(result) is False


def test_retry_disabled_preserves_delivery():
    """With retry off there is a single pass over the targets."""

    handler, seen = _tgram_post()
    with mock.patch("requests.post", side_effect=handler):
        aobj = Apprise()
        assert aobj.add(TGRAM + "?retry=0")
        aobj.notify(body="hello")

    counts = Counter(chat for chat, _ in seen)
    assert counts["111"] == 1
    assert counts["222"] == 1


def test_recovering_target_is_retried():
    """A target that fails once is tried again and then succeeds."""

    handler, seen = _tgram_post(fail_times=1)
    with mock.patch("requests.post", side_effect=handler):
        aobj = Apprise()
        assert aobj.add(TGRAM + "?retry=3&wait=0")
        result = aobj.notify(body="hello")

    counts = Counter(chat for chat, _ in seen)

    # The healthy chat still only hears from us once
    assert counts["111"] == 1

    # The other one needed a second go
    assert counts["222"] == 2
    assert bool(result) is True


def test_split_message_pieces_are_delivered():
    """Each chunk reaches a healthy target exactly once."""

    handler, seen = _tgram_post()
    with mock.patch("requests.post", side_effect=handler):
        aobj = Apprise()
        assert aobj.add(TGRAM + "?overflow=split&retry=2&wait=0")
        aobj.notify(body="y" * 9000)

    good = [size for chat, size in seen if chat == "111"]

    # Three chunks, each sent once and never repeated by a retry
    assert len(good) == 3
    assert sum(good) == 9000


def test_split_message_includes_the_image_once():
    """The notification image is not repeated for every chunk."""

    seen = []

    def handler(url, *args, **kwargs):
        seen.append("image" if kwargs.get("files") else "body")
        r = requests.Request()
        r.status_code = requests.codes.ok
        r.content = dumps({"ok": True, "result": {"message_id": 1}})
        r.text = r.content
        r.headers = {}
        return r

    with mock.patch("requests.post", side_effect=handler):
        aobj = Apprise()
        assert aobj.add(TGRAM + "?overflow=split&retry=2&wait=0&image=yes")
        aobj.notify(body="y" * 9000)

    counts = Counter(seen)

    # Two chats, one image each, no matter how many chunks went out
    assert counts["image"] == 2
    assert counts["body"] > 2


def test_async_delivery_tracking():
    """The asynchronous path shares the same tracking."""

    handler, seen = _tgram_post()
    with mock.patch("requests.post", side_effect=handler):
        aobj = Apprise()
        assert aobj.add(TGRAM + "?retry=3&wait=0")
        asyncio.run(aobj.async_notify(body="hello"))

    counts = Counter(chat for chat, _ in seen)
    assert counts["111"] == 1
    assert counts["222"] == 4
    assert _delivery_tracker.get() is None


def test_destination_kinds_stay_distinct():
    """A phone number used two ways is two separate destinations."""

    obj = _Dummy()
    token = _delivery_tracker.set(set())
    try:
        # The pattern every multi-mode plugin uses: pair the value with
        # the kind of destination it is.
        obj.mark_delivered(("sms", "+15551234567"))

        assert obj.is_delivered(("sms", "+15551234567")) is True

        # The same number over a different mode has not been reached
        assert obj.is_delivered(("whatsapp", "+15551234567")) is False

        # ...and the bare value is not the same thing either
        assert obj.is_delivered("+15551234567") is False

    finally:
        _delivery_tracker.reset(token)


def test_batch_positions_stay_distinct():
    """Each batch of recipients is its own delivery."""

    obj = _Dummy()
    token = _delivery_tracker.set(set())
    try:
        obj.mark_delivered(("batch", 0))

        assert obj.is_delivered(("batch", 0)) is True

        # The next batch still has to go out
        assert obj.is_delivered(("batch", 1)) is False

    finally:
        _delivery_tracker.reset(token)
