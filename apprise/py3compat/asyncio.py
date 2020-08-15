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
from ..URLBase import URLBase
from ..logger import logger


# A global flag that tracks if we are Python v3.7 or higher
ASYNCIO_RUN_SUPPORT = \
    sys.version_info.major > 3 or \
    (sys.version_info.major == 3 and sys.version_info.minor >= 7)


def notify(coroutines, debug=False):
    """
    A Wrapper to the AsyncNotifyBase.async_notify() calls allowing us
    to call gather() and collect the responses
    """

    # Create log entry
    logger.info(
        'Notifying {} service(s) asynchronous.'.format(len(coroutines)))

    if ASYNCIO_RUN_SUPPORT:
        # async reference produces a SyntaxError (E999) in Python v2.7
        # For this reason we turn on the noqa flag
        async def main(results, coroutines):  # noqa: E999
            """
            Task: Notify all servers specified and return our result set
                  through a mutable object.
            """
            # send our notifications and store our result set into
            # our results dictionary
            results['response'] = \
                await asyncio.gather(*coroutines, return_exceptions=True)

        # Initialize a mutable object we can populate with our notification
        # responses
        results = {}

        # Send our notifications
        asyncio.run(main(results, coroutines), debug=debug)

        # Acquire our return status
        status = next((s for s in results['response'] if s is False), True)

    else:
        #
        # The depricated way
        #

        # acquire access to our event loop
        loop = asyncio.get_event_loop()

        if debug:
            # Enable debug mode
            loop.set_debug(1)

        # Send our notifications and acquire our status
        results = loop.run_until_complete(asyncio.gather(*coroutines))

        # Acquire our return status
        status = next((r for r in results if r is False), True)

    # Returns True if all notifications succeeded, otherwise False is
    # returned.
    return status


class AsyncNotifyBase(URLBase):
    """
    asyncio wrapper for the NotifyBase object
    """

    async def async_notify(self, *args, **kwargs):  # noqa: E999
        """
        Async Notification Wrapper
        """
        try:
            return self.notify(*args, **kwargs)

        except TypeError:
            # These our our internally thrown notifications
            pass

        except Exception:
            # A catch all so we don't have to abort early
            # just because one of our plugins has a bug in it.
            logger.exception("Notification Exception")

        return False
