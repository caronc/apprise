# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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
from .CustomNotifyPlugin import CustomNotifyPlugin


def notify(on, name=None):
    """
    @notify decorator allows you to map functions you've defined to be loaded
    as a regular notify by Apprise.  You must identify a protocol that
    users will trigger your call by.

        @notify(on="foobar")
        def your_declaration(body, title, notify_type, meta, *args, **kwargs):
            ...

    You can optionally provide the name to associate with the plugin which
    is what calling functions via the API will receive.

        @notify(on="foobar", name="My Foobar Process")
        def your_action(body, title, notify_type, meta, *args, **kwargs):
            ...

    The meta variable is actually the processed URL contents found in
    configuration files that landed you in this function you wrote in
    the first place.  It's very easily tokenized already for you so
    that you can bend the notification logic to your hearts content.

        @notify(on="foobar", name="My Foobar Process")
        def your_action(body, title, notify_type, meta, *args, **kwargs):
            ...

    Possible kwargs that may also be provided are:
      attach:      An array AppriseAttachment objects (if any were provided)

      body_format: Defaults to the expected format output; By default this
                   will be TEXT unless over-ridden in the Apprise URL

    Your send function should return True or False when complete.

    You should return True if processed the send() function as you expected
    and return False if not.
    """
    def wrapper(func):
        """
        Instantiate our custom (notification) plugin
        """

        try:
            # Generate
            CustomNotifyPlugin.instantiate_plugin(
                url=on, send_func=func, name=name)

        except ValueError:
            # Do nothing
            pass

        return func

    return wrapper
