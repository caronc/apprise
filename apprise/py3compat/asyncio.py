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

import sys
import asyncio
from functools import partial
from ..URLBase import URLBase
from ..logger import logger


# A global flag that tracks if we are Python v3.7 or higher
ASYNCIO_RUN_SUPPORT = \
    sys.version_info.major > 3 or \
    (sys.version_info.major == 3 and sys.version_info.minor >= 7)


async def notify(coroutines):
    """
    An async wrapper to the AsyncNotifyBase.async_notify() calls allowing us
    to call gather() and collect the responses
    """

    # Create log entry
    logger.info(
        'Notifying {} service(s) asynchronously.'.format(len(coroutines)))

    results = await asyncio.gather(*coroutines, return_exceptions=True)

    # Returns True if all notifications succeeded, otherwise False is
    # returned.
    failed = any(not status or isinstance(status, Exception)
                 for status in results)
    return not failed


def tosync(cor, debug=False):
    """
    Await a coroutine from non-async code.
    """

    if ASYNCIO_RUN_SUPPORT:
        try:
            loop = asyncio.get_running_loop()

        except RuntimeError:
            # There is no existing event loop, so we can start our own.
            return asyncio.run(cor, debug=debug)

        else:
            # Enable debug mode
            loop.set_debug(debug)

            # Run the coroutine and wait for the result.
            task = loop.create_task(cor)
            return asyncio.ensure_future(task, loop=loop)

    else:
        # The Deprecated Way (<= Python v3.6)
        try:
            # acquire access to our event loop
            loop = asyncio.get_event_loop()

        except RuntimeError:
            # This happens if we're inside a thread of another application
            # where there is no running event_loop().  Pythong v3.7 and
            # higher automatically take care of this case for us.  But for
            # the lower versions we need to do the following:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Enable debug mode
        loop.set_debug(debug)

        return loop.run_until_complete(cor)


async def toasyncwrapvalue(v):
    """
    Create a coroutine that, when run, returns the provided value.
    """

    return v


async def toasyncwrap(fn):
    """
    Create a coroutine that, when run, executes the provided function.
    """

    return fn()


class AsyncNotifyBase(URLBase):
    """
    asyncio wrapper for the NotifyBase object
    """

    async def async_notify(self, *args, **kwargs):
        """
        Async Notification Wrapper
        """

        loop = asyncio.get_event_loop()

        try:
            return await loop.run_in_executor(
                None, partial(self.notify, *args, **kwargs))

        except TypeError:
            # These are our internally thrown notifications
            pass

        except Exception:
            # A catch-all so we don't have to abort early
            # just because one of our plugins has a bug in it.
            logger.exception("Notification Exception")

        return False
