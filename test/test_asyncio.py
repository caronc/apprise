# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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

from __future__ import print_function
import sys
import pytest
from apprise import Apprise
from apprise import NotifyBase
from apprise import NotifyFormat

from apprise.common import NOTIFY_SCHEMA_MAP

import apprise.py3compat.asyncio as py3aio

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


@pytest.mark.skipif(sys.version_info >= (3, 7),
                    reason="Requires Python 3.0 to 3.6")
def test_apprise_asyncio_runtime_error():
    """
    API: Apprise() AsyncIO RuntimeError handling

    """
    class GoodNotification(NotifyBase):
        def __init__(self, **kwargs):
            super().__init__(
                notify_format=NotifyFormat.HTML, **kwargs)

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay
            return True

        @staticmethod
        def parse_url(url, *args, **kwargs):
            # always parseable
            return NotifyBase.parse_url(url, verify_host=False)

    # Store our good notification in our schema map
    NOTIFY_SCHEMA_MAP['good'] = GoodNotification

    # Create ourselves an Apprise object
    a = Apprise()

    # Add a few entries
    for _ in range(25):
        a.add('good://')

    # Python v3.6 and lower can't handle situations gracefully when an
    # event_loop isn't already established(). Test that Apprise can handle
    # these situations
    import asyncio

    # Get our event loop
    loop = asyncio.get_event_loop()

    # Adjust out event loop to not point at anything
    asyncio.set_event_loop(None)

    # With the event loop inactive, we'll fail trying to get the active loop
    with pytest.raises(RuntimeError):
        asyncio.get_event_loop()

    try:
        # Below, we internally will throw a RuntimeError() since there will
        # be no active event_loop in place. However internally it will be smart
        # enough to create a new event loop and continue...
        assert a.notify(title="title", body="body") is True

        # Verify we have an active event loop
        new_loop = asyncio.get_event_loop()

        # We didn't throw an exception above; thus we have an event loop at
        # this point
        assert new_loop

        # Close off the internal loop created inside a.notify()
        new_loop.close()

    finally:
        # Restore our event loop (in the event the above test failed)
        asyncio.set_event_loop(loop)


@pytest.mark.skipif(sys.version_info < (3, 7),
                    reason="Requires Python 3.7+")
def test_apprise_works_in_async_loop():
    """
    API: Apprise() can execute synchronously in an existing event loop

    """
    class GoodNotification(NotifyBase):
        def __init__(self, **kwargs):
            super().__init__(
                notify_format=NotifyFormat.HTML, **kwargs)

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay
            return True

        @staticmethod
        def parse_url(url, *args, **kwargs):
            # always parseable
            return NotifyBase.parse_url(url, verify_host=False)

    # Store our good notification in our schema map
    NOTIFY_SCHEMA_MAP['good'] = GoodNotification

    # Create ourselves an Apprise object
    a = Apprise()

    # Add a few entries
    for _ in range(25):
        a.add('good://')

    # To ensure backwards compatibility, it should be possible to call
    # asynchronous Apprise methods from code that already uses an event loop,
    # even when using the synchronous notify() method.
    # see https://github.com/caronc/apprise/issues/610
    import asyncio

    def try_notify():
        a.notify(title="title", body="body")

    # Convert to a coroutine to run asynchronously.
    cor = py3aio.toasyncwrap(try_notify)

    # Should execute successfully.
    asyncio.run(cor)
