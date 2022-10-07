# -*- coding: utf-8 -*-

# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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
