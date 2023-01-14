# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.
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
