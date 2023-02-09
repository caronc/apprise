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
