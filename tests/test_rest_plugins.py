# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

import json

# Disable logging for a cleaner testing output
import logging
from random import choice
from string import ascii_uppercase as str_alpha, digits as str_num
from unittest import mock

import pytest
import requests

from apprise import (
    Apprise,
    AppriseAsset,
    NotifyBase,
    NotifyFormat,
    OverflowMode,
)

logging.disable(logging.CRITICAL)


def test_notify_overflow_truncate_with_amalgamation():
    """
    API: Overflow With Amalgamation Truncate Functionality Testing

    """
    #
    # A little preparation
    #

    # Number of characters per line
    row = 24

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    # Create a large body and title with random data
    body = "".join(choice(str_alpha + str_num + " ") for _ in range(body_len))
    body = "\r\n".join([body[i : i + row] for i in range(0, len(body), row)])

    # the new lines add a large amount to our body; lets force the content
    # back to being 1024 characters.
    body = body[0:1024]

    # Create our title using random data
    title = "".join(choice(str_alpha + str_num) for _ in range(title_len))

    #
    # First Test: Truncated Title
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 10

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # We should throw an exception because our specified overflow is wrong.
    with pytest.raises(TypeError):
        # Load our object
        obj = TestNotification(overflow="invalid")

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title, overflow=None)
    chunks = obj._apply_overflow(body="", title="", overflow=None)
    chunks = obj._apply_overflow(body=body, title="", overflow=None)
    chunks = obj._apply_overflow(body=body, title=title, overflow=None)
    chunks = obj._apply_overflow(
        body=body, title=title, overflow=OverflowMode.SPLIT
    )
    assert len(chunks) == 1
    assert body.lstrip("\r\n\x0b\x0c").rstrip() == chunks[0].get("body")
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Line Count Control
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 5

        # Maximum number of lines
        body_max_line_count = 5

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert len(chunks[0].get("body").split("\n")) == obj.body_max_line_count
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Truncated body
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length of just 10
        body_maxlen = 10

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    # Body is lost as the title prevails over everything
    assert chunks[0].get("body") == ""
    # Title is not longer then the maximum size the body can be due to
    # amalgamationflag:
    assert title[: obj.body_maxlen] == chunks[0].get("title")

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length of just 10
        body_maxlen = 10

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1

    assert chunks[0].get("body") == ""
    # body_maxlen prevails due to it being smaller and amalgamation flag set
    assert title[0 : obj.body_maxlen] == chunks[0].get("title")

    #
    # Next Test: Append title to body + Truncated body
    #

    class TestNotification(NotifyBase):

        # Enforce no title
        title_maxlen = 0

        # Enforce a body length of just 100
        body_maxlen = 100

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched

    obj.notify_format = NotifyFormat.HTML
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1

    obj.notify_format = NotifyFormat.MARKDOWN
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1

    obj.notify_format = NotifyFormat.TEXT
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1

    # The below line should be read carefully... We're actually testing to see
    # that our title is matched against our body. Behind the scenes, the title
    # was appended to the body. The body was then truncated to the maxlen.
    # The thing is, since the title is so large, all of the body was lost
    # and a good chunk of the title was too.  The message sent will just be a
    # small portion of the title
    assert len(chunks[0].get("body")) == obj.body_maxlen
    assert title[0 : obj.body_maxlen] == chunks[0].get("body")


def test_notify_overflow_truncate_no_amalgamation():
    """
    API: Overflow No Amalgamation Truncate Functionality Testing

    """
    #
    # A little preparation
    #

    # Number of characters per line
    row = 24

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    # Create a large body and title with random data
    body = "".join(choice(str_alpha + str_num + " ") for _ in range(body_len))
    body = "\r\n".join([body[i : i + row] for i in range(0, len(body), row)])

    # the new lines add a large amount to our body; lets force the content
    # back to being 1024 characters.
    body = body[0:1024]

    # Create our title using random data
    title = "".join(choice(str_alpha + str_num) for _ in range(title_len))

    #
    # First Test: Truncated Title
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 10

        # No amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # We should throw an exception because our specified overflow is wrong.
    with pytest.raises(TypeError):
        # Load our object
        obj = TestNotification(overflow="invalid")

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title, overflow=None)
    chunks = obj._apply_overflow(body="", title="", overflow=None)
    chunks = obj._apply_overflow(body=body, title="", overflow=None)
    chunks = obj._apply_overflow(body=body, title=title, overflow=None)
    chunks = obj._apply_overflow(
        body=body, title=title, overflow=OverflowMode.SPLIT
    )
    assert len(chunks) == 1
    assert body.lstrip("\r\n\x0b\x0c").rstrip() == chunks[0].get("body")
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Line Count Control
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 5

        # Maximum number of lines
        body_max_line_count = 5

        # No amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert len(chunks[0].get("body").split("\n")) == obj.body_max_line_count
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Truncated body
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length of just 10
        body_maxlen = 10

        # No amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert body[0 : obj.body_maxlen].lstrip("\r\n\x0b\x0c").rstrip() == chunks[
        0
    ].get("body")
    assert title == chunks[0].get("title")

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length of just 10
        body_maxlen = 10

        # No amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    # No amalgamation set so our body aligns in size (no -2 like previous
    # test)
    assert body[0 : obj.body_maxlen].lstrip("\r\n\x0b\x0c").rstrip() == chunks[
        0
    ].get("body")
    assert title == chunks[0].get("title")

    #
    # Next Test: Append title to body + Truncated body
    #

    class TestNotification(NotifyBase):

        # Enforce no title
        title_maxlen = 0

        # Enforce a body length of just 100
        body_maxlen = 100

        # No amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched

    obj.notify_format = NotifyFormat.HTML
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1

    obj.notify_format = NotifyFormat.MARKDOWN
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1

    obj.notify_format = NotifyFormat.TEXT
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1

    # The below line should be read carefully... We're actually testing to see
    # that our title is matched against our body. Behind the scenes, the title
    # was appended to the body. The body was then truncated to the maxlen.
    # The thing is, since the title is so large, all of the body was lost
    # and a good chunk of the title was too.  The message sent will just be a
    # small portion of the title
    assert len(chunks[0].get("body")) == obj.body_maxlen
    assert title[0 : obj.body_maxlen] == chunks[0].get("body")


def test_notify_overflow_split_with_amalgamation():
    """
    API: Overflow With Amalgamation Splits Functionality Testing

    """

    #
    # A little preparation
    #

    # Number of characters per line
    row = 24

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    # Create a large body and title with random data
    body = "".join(choice(str_alpha + str_num) for _ in range(body_len))
    body = "\r\n".join([body[i : i + row] for i in range(0, len(body), row)])

    # the new lines add a large amount to our body; lets force the content
    # back to being 1024 characters.
    body = body[0:1024]

    # Create our title using random data
    title = "".join(choice(str_alpha + str_num) for _ in range(title_len))

    #
    # First Test: Truncated Title
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 10

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert body.lstrip("\r\n\x0b\x0c").rstrip() == chunks[0].get("body")
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Line Count Control
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 5

        # Maximum number of lines
        body_max_line_count = 5

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert len(chunks[0].get("body").split("\n")) == obj.body_max_line_count
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Split body
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # No counter is displayed because our title is so enormous
        # We switch to a display title on first message only
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The length of the body prevails our title due to it being
            # so much smaller then our title length
            assert len(chunk.get("title")) == obj.body_maxlen
            assert title[: obj.body_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    # Another edge case where the title just isn't that long leaving
    # a lot of space for the [xx/xx] entries (no truncation needed)
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title[:20])
    offset = 0
    c_len = len(" [X/X]")
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has a counter added to it
        assert title[:20] == chunk.get("title")[:-c_len]
        assert chunk.get("title")[-c_len:] == f" [{idx:01}/{len(chunks):01}]"
        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    #
    # Test forcing overflow_display_title_once
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        #  Only display title once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The body length prevails due to our amalgamation flag
            assert len(chunk.get("title")) == obj.body_maxlen
            assert title[: obj.body_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    # Test larger messages
    # and that the body remains untouched
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 150

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 400

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    new_body = body * 500
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    c_len = len(" [XXXX/XXXX]")
    assert len(chunks) == 2048
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has a counter added to it
        assert (
            title[: obj.title_maxlen][:-c_len] == chunk.get("title")[:-c_len]
        )
        assert chunk.get("title")[-c_len:] == f" [{idx:04}/{len(chunks):04}]"

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    # Body chunk is beyond 4 digits, so [XXXX/XXXX] is turned off
    new_body = body * 2500
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 10240
    for _idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    # Test larger messages
    # and that the body remains untouched
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 150

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 150

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    new_body = body * 5
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 36
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # Because 150 is what we set the title limit to
            assert len(chunk.get("title")) == obj.title_maxlen
            assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Next Test: Append title to body + split body
    #

    class TestNotification(NotifyBase):

        # Enforce no title
        title_maxlen = 0

        # Enforce a body length based on the title. Make sure it's an int.
        body_maxlen = int(title_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)

    # Our final product is that our title has been appended to our body to
    # create one great big body. As a result we'll get quite a few lines back
    # now.
    offset = 0

    # Our body will look like this in small chunks at the end of the day
    bulk = title + "\r\n" + body

    # Due to the new line added to the end
    assert len(chunks) == (
        # wrap division in int() so Python 3 doesn't convert it to a float on
        # us
        int(len(bulk) / obj.body_maxlen)
        + (1 if len(bulk) % obj.body_maxlen else 0)
    )

    for chunk in chunks:
        # Verification
        assert len(chunk.get("title")) == 0
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title is empty every time
        assert chunk.get("title") == ""
        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(bulk[offset : len(_body) + offset]) - len(
            bulk[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            bulk[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Test case where our title_len is shorter then the value
    # that would otherwise trigger the [XX/XX] elements
    #

    class TestNotification(NotifyBase):

        # Set a small title length
        title_maxlen = 100

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 7
    for _idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title is truncated and no counter added
        assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(body[offset : len(_body) + offset]) - len(
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Scenario where the title length is larger than the body
    #

    class TestNotification(NotifyBase):

        # Set a small title length
        title_maxlen = 100

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 50

        # With amalgamation
        overflow_amalgamate_title = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 22
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it due to it's length
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # Because 150 is what we set the title limit to 50 due
            # to amalamation.  The lowest value always prevails
            assert len(chunk.get("title")) == obj.body_maxlen
            assert title[: obj.body_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(body[offset : len(_body) + offset]) - len(
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff


def test_notify_overflow_split_with_amalgamation_force_title_always():
    """
    API: Overflow With Amalgamation (title alaways Split Functionality Testing

    """

    #
    # A little preparation
    #

    # Number of characters per line
    row = 24

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    # Create a large body and title with random data
    body = "".join(choice(str_alpha + str_num) for _ in range(body_len))
    body = "\r\n".join([body[i : i + row] for i in range(0, len(body), row)])

    # the new lines add a large amount to our body; lets force the content
    # back to being 1024 characters.
    body = body[0:1024]

    # Create our title using random data
    title = "".join(choice(str_alpha + str_num) for _ in range(title_len))

    #
    # First Test: Truncated Title
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 10

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert body.lstrip("\r\n\x0b\x0c").rstrip() == chunks[0].get("body")
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Line Count Control
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 5

        # Maximum number of lines
        body_max_line_count = 5

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert len(chunks[0].get("body").split("\n")) == obj.body_max_line_count
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Split body
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # No counter is displayed because our title is so enormous
        # We switch to a display title on first message only
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The length of the body prevails our title due to it being
            # so much smaller then our title length
            assert len(chunk.get("title")) == obj.body_maxlen
            assert title[: obj.body_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    # Another edge case where the title just isn't that long leaving
    # a lot of space for the [xx/xx] entries (no truncation needed)
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title[:20])
    offset = 0
    c_len = len(" [X/X]")
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has a counter added to it
        assert title[:20] == chunk.get("title")[:-c_len]
        assert chunk.get("title")[-c_len:] == f" [{idx:01}/{len(chunks):01}]"
        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    #
    # Test forcing overflow_display_title_once
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The body length prevails due to our amalgamation flag
            assert len(chunk.get("title")) == obj.body_maxlen
            assert title[: obj.body_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    # Test larger messages
    # and that the body remains untouched
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 150

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 400

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    new_body = body * 500
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    c_len = len(" [XXXX/XXXX]")
    assert len(chunks) == 2048
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has a counter added to it
        assert (
            title[: obj.title_maxlen][:-c_len] == chunk.get("title")[:-c_len]
        )
        assert chunk.get("title")[-c_len:] == f" [{idx:04}/{len(chunks):04}]"

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    # Body chunk is beyond 4 digits, so [XXXX/XXXX] is turned off
    new_body = body * 2500
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 10240
    for _idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    # Test larger messages
    # and that the body remains untouched
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 150

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 150

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    new_body = body * 5
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    # overflow_display_title_once whle set to False is still ignored
    # because our title_maxlen > body_maxlen and a full title was
    # provided
    assert len(chunks) == 36
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # Because 150 is what we set the title limit to
            assert len(chunk.get("title")) == obj.title_maxlen
            assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    # overflow_display_title_once whle set to False is still ignored
    # because our title_maxlen > body_maxlen and a full title was
    # provided
    assert len(chunks) == 36
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # Because 150 is what we set the title limit to
            assert len(chunk.get("title")) == obj.title_maxlen
            assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Run again but with a smaller title
    #
    chunks = obj._apply_overflow(body=new_body, title=title[:30])
    offset = 0
    # overflow_display_title_once whle set to False is still ignored
    # because our body_maxlen (after title has been calculated with it)
    # is less then the overflow_display_count_threshold; hence a message
    # must be a certain minimum size in order to kick in
    assert len(chunks) == 48
    for _idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title doesn't change
        assert len(chunk.get("title")) == 30
        assert title[:30] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset].rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Next Test: Append title to body + split body
    #

    class TestNotification(NotifyBase):

        # Enforce no title
        title_maxlen = 0

        # Enforce a body length based on the title. Make sure it's an int.
        body_maxlen = int(title_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)

    # Our final product is that our title has been appended to our body to
    # create one great big body. As a result we'll get quite a few lines back
    # now.
    offset = 0

    # Our body will look like this in small chunks at the end of the day
    bulk = title + "\r\n" + body

    # Due to the new line added to the end
    assert len(chunks) == (
        # wrap division in int() so Python 3 doesn't convert it to a float on
        # us
        int(len(bulk) / obj.body_maxlen)
        + (1 if len(bulk) % obj.body_maxlen else 0)
    )

    for chunk in chunks:
        # Verification
        assert len(chunk.get("title")) == 0
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title is empty every time
        assert chunk.get("title") == ""
        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(bulk[offset : len(_body) + offset]) - len(
            bulk[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            bulk[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Test case where our title_len is shorter then the value
    # that would otherwise trigger the [XX/XX] elements
    #

    class TestNotification(NotifyBase):

        # Set a small title length
        title_maxlen = 100

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 7
    for _idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title is truncated and no counter added
        assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(body[offset : len(_body) + offset]) - len(
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Scenario where the title length is larger than the body
    #

    class TestNotification(NotifyBase):

        # Set a small title length
        title_maxlen = 100

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 50

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0

    # overflow_display_title_once whle set to False is still ignored
    # because our title_maxlen > body_maxlen and a full title was
    # provided
    assert len(chunks) == 22
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it due to it's length
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # Because 150 is what we set the title limit to 50 due
            # to amalamation.  The lowest value always prevails
            assert len(chunk.get("title")) == obj.body_maxlen
            assert title[: obj.body_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(body[offset : len(_body) + offset]) - len(
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff


def test_notify_overflow_split_with_amalgamation_force_title_once():
    """
    API: Overflow With Amalgamation (title once) Split Functionality Testing

    """

    #
    # A little preparation
    #

    # Number of characters per line
    row = 24

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    # Create a large body and title with random data
    body = "".join(choice(str_alpha + str_num) for _ in range(body_len))
    body = "\r\n".join([body[i : i + row] for i in range(0, len(body), row)])

    # the new lines add a large amount to our body; lets force the content
    # back to being 1024 characters.
    body = body[0:1024]

    # Create our title using random data
    title = "".join(choice(str_alpha + str_num) for _ in range(title_len))

    #
    # First Test: Truncated Title
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 10

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert body.lstrip("\r\n\x0b\x0c").rstrip() == chunks[0].get("body")
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Line Count Control
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 5

        # Maximum number of lines
        body_max_line_count = 5

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert len(chunks[0].get("body").split("\n")) == obj.body_max_line_count
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Split body
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # No counter is displayed because our title is so enormous
        # We switch to a display title on first message only
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The length of the body prevails our title due to it being
            # so much smaller then our title length
            assert len(chunk.get("title")) == obj.body_maxlen
            assert title[: obj.body_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    # Another edge case where the title just isn't that long leaving
    # a lot of space for the [xx/xx] entries (no truncation needed)
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title[:20])
    offset = 0
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""

        else:
            # The body length prevails due to our amalgamation flag
            assert len(chunk.get("title")) == 20
            assert title[:20] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    #
    # Test forcing overflow_display_title_once
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        #  Only display title once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The body length prevails due to our amalgamation flag
            assert len(chunk.get("title")) == obj.body_maxlen
            assert title[: obj.body_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    # Test larger messages
    # and that the body remains untouched
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 150

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 400

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    new_body = body * 500
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 1281
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The body length prevails due to our amalgamation flag
            assert len(chunk.get("title")) == obj.title_maxlen
            assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    # Body chunk is beyond 4 digits, so [XXXX/XXXX] is turned off
    new_body = body * 2500
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 6401
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The body length prevails due to our amalgamation flag
            assert len(chunk.get("title")) == obj.title_maxlen
            assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    # Test larger messages
    # and that the body remains untouched
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 150

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 150

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    new_body = body * 5
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 36
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # Because 150 is what we set the title limit to
            assert len(chunk.get("title")) == obj.title_maxlen
            assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Next Test: Append title to body + split body
    #

    class TestNotification(NotifyBase):

        # Enforce no title
        title_maxlen = 0

        # Enforce a body length based on the title. Make sure it's an int.
        body_maxlen = int(title_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)

    # Our final product is that our title has been appended to our body to
    # create one great big body. As a result we'll get quite a few lines back
    # now.
    offset = 0

    # Our body will look like this in small chunks at the end of the day
    bulk = title + "\r\n" + body

    # Due to the new line added to the end
    assert len(chunks) == (
        # wrap division in int() so Python 3 doesn't convert it to a float on
        # us
        int(len(bulk) / obj.body_maxlen)
        + (1 if len(bulk) % obj.body_maxlen else 0)
    )

    for chunk in chunks:
        # Verification
        assert len(chunk.get("title")) == 0
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title is empty every time
        assert chunk.get("title") == ""
        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(bulk[offset : len(_body) + offset]) - len(
            bulk[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            bulk[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Test case where our title_len is shorter then the value
    # that would otherwise trigger the [XX/XX] elements
    #

    class TestNotification(NotifyBase):

        # Set a small title length
        title_maxlen = 100

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The body length prevails due to our amalgamation flag
            assert len(chunk.get("title")) == obj.title_maxlen
            assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(body[offset : len(_body) + offset]) - len(
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Scenario where the title length is larger than the body
    #

    class TestNotification(NotifyBase):

        # Set a small title length
        title_maxlen = 100

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 50

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 22
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it due to it's length
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # Because 150 is what we set the title limit to 50 due
            # to amalamation.  The lowest value always prevails
            assert len(chunk.get("title")) == obj.body_maxlen
            assert title[: obj.body_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(body[offset : len(_body) + offset]) - len(
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff


def test_notify_overflow_split_no_amalgamation():
    """
    API: Overflow No Amalgamation Splits Functionality Testing

    """

    #
    # A little preparation
    #

    # Number of characters per line
    row = 24

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    # Create a large body and title with random data
    body = "".join(choice(str_alpha + str_num) for _ in range(body_len))
    body = "\r\n".join([body[i : i + row] for i in range(0, len(body), row)])

    # the new lines add a large amount to our body; lets force the content
    # back to being 1024 characters.
    body = body[0:1024]

    # Create our title using random data
    title = "".join(choice(str_alpha + str_num) for _ in range(title_len))

    #
    # First Test: Truncated Title
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 10

        # No amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert body.lstrip("\r\n\x0b\x0c").rstrip() == chunks[0].get("body")
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Line Count Control
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 5

        # Maximum number of lines
        body_max_line_count = 5

        # No amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert len(chunks[0].get("body").split("\n")) == obj.body_max_line_count
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Split body
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # No amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    c_len = len(" [X/X]")
    assert len(chunks) == 4
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has a counter added to it
        assert title[:-c_len] == chunk.get("title")[:-c_len]
        assert chunk.get("title")[-c_len:] == f" [{idx:01}/{len(chunks):01}]"
        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    # Another edge case where the title just isn't that long leaving
    # a lot of space for the [xx/xx] entries (no truncation needed)
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title[:20])
    offset = 0
    assert len(chunks) == 4
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has a counter added to it
        assert title[:20] == chunk.get("title")[:-c_len]
        assert chunk.get("title")[-c_len:] == f" [{idx:01}/{len(chunks):01}]"
        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    # Test larger messages
    # and that the body remains untouched
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 150

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 400

        # No amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    new_body = body * 500
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    c_len = len(" [XXXX/XXXX]")
    assert len(chunks) == 1280
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen
        # Our title has a counter added to it
        assert (
            title[: obj.title_maxlen][:-c_len] == chunk.get("title")[:-c_len]
        )
        assert chunk.get("title")[-c_len:] == f" [{idx:04}/{len(chunks):04}]"
        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    # Body chunk is beyond 4 digits, so [XXXX/XXXX] is turned off
    new_body = body * 4500
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 11520
    for _idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        assert title[: obj.title_maxlen] == chunk.get("title")
        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    # Test larger messages
    # and that the body remains untouched
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 150

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 150

        # No amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    new_body = body * 5
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 35
    c_len = len(" [XX/XX]")
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has a counter added to it
        assert (
            title[: obj.title_maxlen][:-c_len] == chunk.get("title")[:-c_len]
        )
        assert chunk.get("title")[-c_len:] == f" [{idx:02}/{len(chunks):02}]"
        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Next Test: Append title to body + split body
    #

    class TestNotification(NotifyBase):

        # Enforce no title
        title_maxlen = 0

        # Enforce a body length based on the title. Make sure it's an int.
        body_maxlen = int(title_len / 4)

        # No Amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)

    # Our final product is that our title has been appended to our body to
    # create one great big body. As a result we'll get quite a few lines back
    # now.
    offset = 0

    # Our body will look like this in small chunks at the end of the day
    bulk = title + "\r\n" + body

    # Due to the new line added to the end
    assert len(chunks) == (
        # wrap division in int() so Python 3 doesn't convert it to a float on
        # us
        int(len(bulk) / obj.body_maxlen)
        + (1 if len(bulk) % obj.body_maxlen else 0)
    )

    for chunk in chunks:
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title is empty every time
        assert chunk.get("title") == ""

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(bulk[offset : len(_body) + offset]) - len(
            bulk[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            bulk[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Test case where our title_len is shorter then the value
    # that would otherwise trigger the [XX/XX] elements
    #

    class TestNotification(NotifyBase):

        # Set a small title length
        title_maxlen = 100

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # No Amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 4
    for _idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title is truncated and no counter added
        assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    #
    # Scenario where the title length is larger than the body
    #

    class TestNotification(NotifyBase):

        # Set a small title length
        title_maxlen = 100

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 50

        # No Amalgamation
        overflow_amalgamate_title = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 21
    for _idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title is truncated and no counter added
        assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(body[offset : len(_body) + offset]) - len(
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff


def test_notify_overflow_split_no_amalgamation_force_title_always():
    """
    API: Overflow No Amalgamation (title always) Split Functionality Testing

    """

    #
    # A little preparation
    #

    # Number of characters per line
    row = 24

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    # Create a large body and title with random data
    body = "".join(choice(str_alpha + str_num) for _ in range(body_len))
    body = "\r\n".join([body[i : i + row] for i in range(0, len(body), row)])

    # the new lines add a large amount to our body; lets force the content
    # back to being 1024 characters.
    body = body[0:1024]

    # Create our title using random data
    title = "".join(choice(str_alpha + str_num) for _ in range(title_len))

    #
    # First Test: Truncated Title
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 10

        # No amalgamation
        overflow_amalgamate_title = False

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert body.lstrip("\r\n\x0b\x0c").rstrip() == chunks[0].get("body")
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Line Count Control
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 5

        # Maximum number of lines
        body_max_line_count = 5

        # No amalgamation
        overflow_amalgamate_title = False

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert len(chunks[0].get("body").split("\n")) == obj.body_max_line_count
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Split body
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # No amalgamation
        overflow_amalgamate_title = False

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    c_len = len(" [X/X]")
    assert len(chunks) == 4
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has a counter added to it
        assert title[:-c_len] == chunk.get("title")[:-c_len]
        assert chunk.get("title")[-c_len:] == f" [{idx:01}/{len(chunks):01}]"
        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    # Another edge case where the title just isn't that long leaving
    # a lot of space for the [xx/xx] entries (no truncation needed)
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title[:20])
    offset = 0
    assert len(chunks) == 4
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has a counter added to it
        assert title[:20] == chunk.get("title")[:-c_len]
        assert chunk.get("title")[-c_len:] == f" [{idx:01}/{len(chunks):01}]"
        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    # Test larger messages
    # and that the body remains untouched
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 150

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 400

        # No amalgamation
        overflow_amalgamate_title = False

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    new_body = body * 500
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    c_len = len(" [XXXX/XXXX]")
    assert len(chunks) == 1280
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen
        # Our title has a counter added to it
        assert (
            title[: obj.title_maxlen][:-c_len] == chunk.get("title")[:-c_len]
        )
        assert chunk.get("title")[-c_len:] == f" [{idx:04}/{len(chunks):04}]"
        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    # Body chunk is beyond 4 digits, so [XXXX/XXXX] is turned off
    new_body = body * 4500
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 11520
    for _idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        assert title[: obj.title_maxlen] == chunk.get("title")
        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    # Test larger messages
    # and that the body remains untouched
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 150

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 150

        # No amalgamation
        overflow_amalgamate_title = False

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    new_body = body * 5
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 35
    c_len = len(" [XX/XX]")
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has a counter added to it
        assert (
            title[: obj.title_maxlen][:-c_len] == chunk.get("title")[:-c_len]
        )
        assert chunk.get("title")[-c_len:] == f" [{idx:02}/{len(chunks):02}]"
        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Next Test: Append title to body + split body
    #

    class TestNotification(NotifyBase):

        # Enforce no title
        title_maxlen = 0

        # Enforce a body length based on the title. Make sure it's an int.
        body_maxlen = int(title_len / 4)

        # No Amalgamation
        overflow_amalgamate_title = False

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)

    # Our final product is that our title has been appended to our body to
    # create one great big body. As a result we'll get quite a few lines back
    # now.
    offset = 0

    # Our body will look like this in small chunks at the end of the day
    bulk = title + "\r\n" + body

    # Due to the new line added to the end
    assert len(chunks) == (
        # wrap division in int() so Python 3 doesn't convert it to a float on
        # us
        int(len(bulk) / obj.body_maxlen)
        + (1 if len(bulk) % obj.body_maxlen else 0)
    )

    for chunk in chunks:
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title is empty every time
        assert chunk.get("title") == ""

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(bulk[offset : len(_body) + offset]) - len(
            bulk[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            bulk[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Test case where our title_len is shorter then the value
    # that would otherwise trigger the [XX/XX] elements
    #

    class TestNotification(NotifyBase):

        # Set a small title length
        title_maxlen = 100

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # No Amalgamation
        overflow_amalgamate_title = False

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 4
    for _idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title is truncated and no counter added
        assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    #
    # Scenario where the title length is larger than the body
    #

    class TestNotification(NotifyBase):

        # Set a small title length
        title_maxlen = 100

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 50

        # No Amalgamation
        overflow_amalgamate_title = False

        # Force title to be displayed always
        overflow_display_title_once = False

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 21
    for _idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title is truncated and no counter added
        assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(body[offset : len(_body) + offset]) - len(
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff


def test_notify_overflow_split_no_amalgamation_force_title_once():
    """
    API: Overflow No Amalgamation (title once) Split Functionality Testing

    """

    #
    # A little preparation
    #

    # Number of characters per line
    row = 24

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    # Create a large body and title with random data
    body = "".join(choice(str_alpha + str_num) for _ in range(body_len))
    body = "\r\n".join([body[i : i + row] for i in range(0, len(body), row)])

    # the new lines add a large amount to our body; lets force the content
    # back to being 1024 characters.
    body = body[0:1024]

    # Create our title using random data
    title = "".join(choice(str_alpha + str_num) for _ in range(title_len))

    #
    # First Test: Truncated Title
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 10

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert body.lstrip("\r\n\x0b\x0c").rstrip() == chunks[0].get("body")
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Line Count Control
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 5

        # Maximum number of lines
        body_max_line_count = 5

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert len(chunks[0].get("body").split("\n")) == obj.body_max_line_count
    assert title[0 : obj.title_maxlen] == chunks[0].get("title")

    #
    # Next Test: Split body
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # No counter is displayed because our title is so enormous
        # We switch to a display title on first message only
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The length of the body prevails our title due to it being
            # so much smaller then our title length
            assert len(chunk.get("title")) == obj.body_maxlen
            assert title[: obj.body_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    # Another edge case where the title just isn't that long leaving
    # a lot of space for the [xx/xx] entries (no truncation needed)
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title[:20])
    offset = 0
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # No counter is displayed because our title is so enormous
        # We switch to a display title on first message only
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The length of the body prevails our title due to it being
            # so much smaller then our title length
            assert len(chunk.get("title")) == 20
            assert title[:20] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    #
    # Test forcing overflow_display_title_once
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The body length prevails due to our amalgamation flag
            assert len(chunk.get("title")) == obj.body_maxlen
            assert title[: obj.body_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")
        assert (
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
            == _body
        )
        offset += len(_body)

    # Test larger messages
    # and that the body remains untouched
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 150

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 400

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    new_body = body * 500
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 1281
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # No counter is displayed because our title is so enormous
        # We switch to a display title on first message only
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The length of the body prevails our title due to it being
            # so much smaller then our title length
            assert len(chunk.get("title")) == obj.title_maxlen
            assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    # Body chunk is beyond 4 digits, so [XXXX/XXXX] is turned off
    new_body = body * 2500
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 6401
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # No counter is displayed because our title is so enormous
        # We switch to a display title on first message only
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The length of the body prevails our title due to it being
            # so much smaller then our title length
            assert len(chunk.get("title")) == obj.title_maxlen
            assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    # Test larger messages
    # and that the body remains untouched
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 150

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 150

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    new_body = body * 5
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=new_body, title="")
    chunks = obj._apply_overflow(body=new_body, title=title)
    offset = 0
    assert len(chunks) == 36
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # Because 150 is what we set the title limit to
            assert len(chunk.get("title")) == obj.title_maxlen
            assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(new_body[offset : len(_body) + offset]) - len(
            new_body[offset : len(_body) + offset]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
        )

        assert (
            new_body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Next Test: Append title to body + split body
    #

    class TestNotification(NotifyBase):

        # Enforce no title
        title_maxlen = 0

        # Enforce a body length based on the title. Make sure it's an int.
        body_maxlen = int(title_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)

    # Our final product is that our title has been appended to our body to
    # create one great big body. As a result we'll get quite a few lines back
    # now.
    offset = 0

    # Our body will look like this in small chunks at the end of the day
    bulk = title + "\r\n" + body

    # Due to the new line added to the end
    assert len(chunks) == (
        # wrap division in int() so Python 3 doesn't convert it to a float on
        # us
        int(len(bulk) / obj.body_maxlen)
        + (1 if len(bulk) % obj.body_maxlen else 0)
    )

    for chunk in chunks:
        # Verification
        assert len(chunk.get("title")) == 0
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title is empty every time
        assert chunk.get("title") == ""
        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(bulk[offset : len(_body) + offset]) - len(
            bulk[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            bulk[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Test case where our title_len is shorter then the value
    # that would otherwise trigger the [XX/XX] elements
    #

    class TestNotification(NotifyBase):

        # Set a small title length
        title_maxlen = 100

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 5
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # No counter is displayed because our title is so enormous
        # We switch to a display title on first message only
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # The length of the body prevails our title due to it being
            # so much smaller then our title length
            assert len(chunk.get("title")) == obj.title_maxlen
            assert title[: obj.title_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(body[offset : len(_body) + offset]) - len(
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff

    #
    # Scenario where the title length is larger than the body
    #

    class TestNotification(NotifyBase):

        # Set a small title length
        title_maxlen = 100

        # Enforce a body length. Make sure it's an int.
        body_maxlen = 50

        # With amalgamation
        overflow_amalgamate_title = True

        # Force title displayed once
        overflow_display_title_once = True

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 22
    for idx, chunk in enumerate(chunks, start=1):
        # Verification
        assert len(chunk.get("title")) <= obj.title_maxlen
        assert len(chunk.get("body")) <= obj.body_maxlen

        # Our title has no counter added to it due to it's length
        if idx > 1:
            # Empty (no title displayed on following entries
            assert chunk.get("title") == ""
        else:
            # Because 150 is what we set the title limit to 50 due
            # to amalamation.  The lowest value always prevails
            assert len(chunk.get("title")) == obj.body_maxlen
            assert title[: obj.body_maxlen] == chunk.get("title")

        # Our body is only broken up; not lost
        _body = chunk.get("body")

        # Un-used whitespace is always cleaned up; make sure we account for
        # this in our new calculation
        ws_diff = len(body[offset : len(_body) + offset]) - len(
            body[offset : len(_body) + offset].lstrip("\r\n\x0b\x0c").rstrip()
        )

        assert (
            body[offset : len(_body) + offset + ws_diff]
            .lstrip("\r\n\x0b\x0c")
            .rstrip()
            == _body
        )
        offset += len(_body) + ws_diff


def test_notify_markdown_general():
    """
    API: Markdown General Testing

    """

    #
    # A little preparation
    #

    #
    # First Test: Truncated Title
    #
    class TestMarkdownNotification(NotifyBase):

        # Force our title to wrap
        title_maxlen = 0

        # Default Notify Format
        notify_format = NotifyFormat.MARKDOWN

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestMarkdownNotification()
    assert obj is not None

    # A bad header
    title = " # "
    body = "**Test Body**"

    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    # whitspace is trimmed
    assert chunks[0].get("body") == "#\r\n**Test Body**"
    assert chunks[0].get("title") == ""

    # If we know our input is text however, we perform manipulation
    chunks = obj._apply_overflow(body="", title=title)
    chunks = obj._apply_overflow(body="", title="")
    chunks = obj._apply_overflow(body=body, title="")
    chunks = obj._apply_overflow(
        body=body, title=title, body_format=NotifyFormat.TEXT
    )
    assert len(chunks) == 1
    # Our title get's stripped off since it's not of valid markdown
    assert body.lstrip("\r\n\x0b\x0c").rstrip() == chunks[0].get("body")
    assert chunks[0].get("title") == ""


@mock.patch("requests.post")
def test_notify_emoji_general(mock_post):
    """
    API: Emoji General Testing

    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Set up our emojis
    title = ":smile:"
    body = ":grin:"

    # general reference used below (using default values)
    asset = AppriseAsset()

    #
    # Test default emoji asset value
    #

    # Load our object
    ap_obj = Apprise(asset=asset)
    ap_obj.add("json://localhost")
    assert len(ap_obj) == 1

    assert ap_obj.notify(title=title, body=body) is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    dataset = json.loads(details[1]["data"])

    # No changes
    assert dataset["title"] == title
    assert dataset["message"] == body

    mock_post.reset_mock()

    #
    # Test URL over-ride while default value set in asset
    #

    # Load our object
    ap_obj = Apprise(asset=asset)
    ap_obj.add("json://localhost?emojis=no")
    assert len(ap_obj) == 1

    assert ap_obj.notify(title=title, body=body) is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    dataset = json.loads(details[1]["data"])

    # No changes
    assert dataset["title"] == title
    assert dataset["message"] == body

    mock_post.reset_mock()

    #
    # Test URL over-ride while default value set in asset pt 2
    #

    # Load our object
    ap_obj = Apprise(asset=asset)
    ap_obj.add("json://localhost?emojis=yes")
    assert len(ap_obj) == 1

    assert ap_obj.notify(title=title, body=body) is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    dataset = json.loads(details[1]["data"])

    # Emoji's are displayed
    assert dataset["title"] == "😄"
    assert dataset["message"] == "😃"

    mock_post.reset_mock()

    #
    # Test URL over-ride while default value set in asset pt 2
    #

    # Load our object
    ap_obj = Apprise(asset=asset)
    ap_obj.add("json://localhost?emojis=no")
    assert len(ap_obj) == 1

    assert ap_obj.notify(title=title, body=body) is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    dataset = json.loads(details[1]["data"])

    # No changes
    assert dataset["title"] == title
    assert dataset["message"] == body

    mock_post.reset_mock()

    #
    # Test Default Emoji settings
    #

    # Set our interpret emoji's flag
    asset = AppriseAsset(interpret_emojis=True)

    # Re-create our object
    ap_obj = Apprise(asset=asset)

    # Load our object
    ap_obj.add("json://localhost")
    assert len(ap_obj) == 1

    assert ap_obj.notify(title=title, body=body) is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    dataset = json.loads(details[1]["data"])

    # emoji's are displayed
    assert dataset["title"] == "😄"
    assert dataset["message"] == "😃"

    mock_post.reset_mock()

    #
    # With Emoji's turned on by default, the user can optionally turn them
    # off.
    #

    # Re-create our object
    ap_obj = Apprise(asset=asset)

    ap_obj.add("json://localhost?emojis=no")
    assert len(ap_obj) == 1

    assert ap_obj.notify(title=title, body=body) is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    dataset = json.loads(details[1]["data"])

    # No changes
    assert dataset["title"] == title
    assert dataset["message"] == body

    mock_post.reset_mock()

    #
    # With Emoji's turned on by default, there is no change when emojis
    # flag is set to on
    #

    # Re-create our object
    ap_obj = Apprise(asset=asset)

    ap_obj.add("json://localhost?emojis=yes")
    assert len(ap_obj) == 1

    assert ap_obj.notify(title=title, body=body) is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    dataset = json.loads(details[1]["data"])

    # emoji's are displayed
    assert dataset["title"] == "😄"
    assert dataset["message"] == "😃"

    mock_post.reset_mock()

    #
    # Enforce the disabling of emojis
    #

    # Set our interpret emoji's flag
    asset = AppriseAsset(interpret_emojis=False)

    # Re-create our object
    ap_obj = Apprise(asset=asset)

    # Load our object
    ap_obj.add("json://localhost")
    assert len(ap_obj) == 1

    assert ap_obj.notify(title=title, body=body) is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    dataset = json.loads(details[1]["data"])

    # Disabled - no emojis
    assert dataset["title"] == title
    assert dataset["message"] == body

    mock_post.reset_mock()

    #
    # Enforce the disabling of emojis
    #

    # Set our interpret emoji's flag
    asset = AppriseAsset(interpret_emojis=False)

    # Re-create our object
    ap_obj = Apprise(asset=asset)

    # Load our object
    ap_obj.add("json://localhost?emojis=yes")
    assert len(ap_obj) == 1

    assert ap_obj.notify(title=title, body=body) is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    dataset = json.loads(details[1]["data"])

    # Disabled - no emojis
    assert dataset["title"] == title
    assert dataset["message"] == body

    mock_post.reset_mock()
