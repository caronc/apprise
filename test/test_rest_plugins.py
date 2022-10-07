# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import pytest
from random import choice
from string import ascii_uppercase as str_alpha
from string import digits as str_num

from apprise import plugins
from apprise import NotifyBase
from apprise.common import NotifyFormat
from apprise.common import OverflowMode

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_notify_overflow_truncate():
    """
    API: Overflow Truncate Functionality Testing

    """
    #
    # A little preparation
    #

    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Number of characters per line
    row = 24

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    # Create a large body and title with random data
    body = ''.join(choice(str_alpha + str_num + ' ') for _ in range(body_len))
    body = '\r\n'.join([body[i: i + row] for i in range(0, len(body), row)])

    # the new lines add a large amount to our body; lets force the content
    # back to being 1024 characters.
    body = body[0:1024]

    # Create our title using random data
    title = ''.join(choice(str_alpha + str_num) for _ in range(title_len))

    #
    # First Test: Truncated Title
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 10

        def __init__(self, *args, **kwargs):
            super(TestNotification, self).__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # We should throw an exception because our specified overflow is wrong.
    with pytest.raises(TypeError):
        # Load our object
        obj = TestNotification(overflow='invalid')

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body=body, title=title, overflow=None)
    chunks = obj._apply_overflow(
        body=body, title=title, overflow=OverflowMode.SPLIT)
    assert len(chunks) == 1
    assert body.rstrip() == chunks[0].get('body')
    assert title[0:TestNotification.title_maxlen] == chunks[0].get('title')

    #
    # Next Test: Line Count Control
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 5

        # Maximum number of lines
        body_max_line_count = 5

        def __init__(self, *args, **kwargs):
            super(TestNotification, self).__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert len(chunks[0].get('body').split('\n')) == \
        TestNotification.body_max_line_count
    assert title[0:TestNotification.title_maxlen] == chunks[0].get('title')

    #
    # Next Test: Truncated body
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length of just 10
        body_maxlen = 10

        def __init__(self, *args, **kwargs):
            super(TestNotification, self).__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert body[0:TestNotification.body_maxlen] == chunks[0].get('body')
    assert title == chunks[0].get('title')

    #
    # Next Test: Append title to body + Truncated body
    #

    class TestNotification(NotifyBase):

        # Enforce no title
        title_maxlen = 0

        # Enforce a body length of just 100
        body_maxlen = 100

        def __init__(self, *args, **kwargs):
            super(TestNotification, self).__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.TRUNCATE)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched

    obj.notify_format = NotifyFormat.HTML
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1

    obj.notify_format = NotifyFormat.MARKDOWN
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1

    obj.notify_format = NotifyFormat.TEXT
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1

    # The below line should be read carefully... We're actually testing to see
    # that our title is matched against our body. Behind the scenes, the title
    # was appended to the body. The body was then truncated to the maxlen.
    # The thing is, since the title is so large, all of the body was lost
    # and a good chunk of the title was too.  The message sent will just be a
    # small portion of the title
    assert len(chunks[0].get('body')) == TestNotification.body_maxlen
    assert title[0:TestNotification.body_maxlen] == chunks[0].get('body')


def test_notify_overflow_split():
    """
    API: Overflow Split Functionality Testing

    """

    #
    # A little preparation
    #

    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Number of characters per line
    row = 24

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    # Create a large body and title with random data
    body = ''.join(choice(str_alpha + str_num) for _ in range(body_len))
    body = '\r\n'.join([body[i: i + row] for i in range(0, len(body), row)])

    # the new lines add a large amount to our body; lets force the content
    # back to being 1024 characters.
    body = body[0:1024]

    # Create our title using random data
    title = ''.join(choice(str_alpha + str_num) for _ in range(title_len))

    #
    # First Test: Truncated Title
    #
    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 10

        def __init__(self, *args, **kwargs):
            super(TestNotification, self).__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert body == chunks[0].get('body')
    assert title[0:TestNotification.title_maxlen] == chunks[0].get('title')

    #
    # Next Test: Line Count Control
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = 5

        # Maximum number of lines
        body_max_line_count = 5

        def __init__(self, *args, **kwargs):
            super(TestNotification, self).__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    assert len(chunks[0].get('body').split('\n')) == \
        TestNotification.body_max_line_count
    assert title[0:TestNotification.title_maxlen] == chunks[0].get('title')

    #
    # Next Test: Split body
    #

    class TestNotification(NotifyBase):

        # Test title max length
        title_maxlen = title_len

        # Enforce a body length. Make sure it's an int.
        body_maxlen = int(body_len / 4)

        def __init__(self, *args, **kwargs):
            super(TestNotification, self).__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body=body, title=title)
    offset = 0
    assert len(chunks) == 4
    for chunk in chunks:
        # Our title never changes
        assert title == chunk.get('title')

        # Our body is only broken up; not lost
        _body = chunk.get('body')
        assert body[offset: len(_body) + offset].rstrip() == _body
        offset += len(_body)

    #
    # Next Test: Append title to body + split body
    #

    class TestNotification(NotifyBase):

        # Enforce no title
        title_maxlen = 0

        # Enforce a body length based on the title. Make sure it's an int.
        body_maxlen = int(title_len / 4)

        def __init__(self, *args, **kwargs):
            super(TestNotification, self).__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestNotification(overflow=OverflowMode.SPLIT)
    assert obj is not None

    # Verify that we break the title to a max length of our title_max
    # and that the body remains untouched
    chunks = obj._apply_overflow(body=body, title=title)

    # Our final product is that our title has been appended to our body to
    # create one great big body. As a result we'll get quite a few lines back
    # now.
    offset = 0

    # Our body will look like this in small chunks at the end of the day
    bulk = title + '\r\n' + body

    # Due to the new line added to the end
    assert len(chunks) == (
        # wrap division in int() so Python 3 doesn't convert it to a float on
        # us
        int(len(bulk) / TestNotification.body_maxlen) +
        (1 if len(bulk) % TestNotification.body_maxlen else 0))

    for chunk in chunks:
        # Our title is empty every time
        assert chunk.get('title') == ''

        _body = chunk.get('body')
        assert bulk[offset: len(_body) + offset] == _body
        offset += len(_body)


def test_notify_overflow_general():
    """
    API: Overflow General Testing

    """

    #
    # A little preparation
    #

    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    #
    # First Test: Truncated Title
    #
    class TestMarkdownNotification(NotifyBase):

        # Force our title to wrap
        title_maxlen = 0

        # Default Notify Format
        notify_format = NotifyFormat.MARKDOWN

        def __init__(self, *args, **kwargs):
            super(TestMarkdownNotification, self).__init__(**kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

    # Load our object
    obj = TestMarkdownNotification()
    assert obj is not None

    # A bad header
    title = " # "
    body = "**Test Body**"

    chunks = obj._apply_overflow(body=body, title=title)
    assert len(chunks) == 1
    # whitspace is trimmed
    assert '#\r\n**Test Body**' == chunks[0].get('body')
    assert chunks[0].get('title') == ""

    # If we know our input is text however, we perform manipulation
    chunks = obj._apply_overflow(
        body=body, title=title, body_format=NotifyFormat.TEXT)
    assert len(chunks) == 1
    # Our title get's stripped off since it's not of valid markdown
    assert body == chunks[0].get('body')
    assert chunks[0].get('title') == ""
