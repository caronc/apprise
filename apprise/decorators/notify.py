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
        def your_action(body, title, notify_type, body_format, meta, attach,
                        *args, **kwargs):
            ...

    Arguments break down as follows:
      body:        The message body associated with the notification
      title:       The message title associated with the notification
      notify_type: The message type (info, success, warning, and failure)
      body_format: The format of the incoming notification body. This is
                   either text, html, or markdown.
      meta:        Combines the URL arguments specified on the `on` call
                   with the ones loaded from a users configuration. This
                   is a dictionary that presents itself like this:
                    {
                      'schema': 'http',
                      'url': 'http://hostname',
                      'host': 'hostname',

                      'user': 'john',
                      'password': 'doe',
                      'port': 80,
                      'path': '/',
                      'fullpath': '/test.php',
                      'query': 'test.php',

                      'qsd': {'key': 'value', 'key2': 'value2'},

                      'asset': <AppriseAsset>,
                      'tag': set(),
                    }

                    Meta entries are ONLY present if found.  A simple URL
                    such as foobar:// would only produce the following:
                    {
                      'schema': 'foobar',
                      'url': 'foobar://',

                      'asset': <AppriseAsset>,
                      'tag': set(),
                    }

      attach:      An array AppriseAttachment objects (if any were provided)

      body_format: Defaults to the expected format output; By default this
                   will be TEXT unless over-ridden in the Apprise URL


    If you don't intend on using all of the parameters, your @notify() call
    # can be greatly simplified to just:

        @notify(on="foobar", name="My Foobar Process")
        def your_action(body, title, *args, **kwargs)

    Always end your wrappers declaration with *args and **kwargs to be future
    proof with newer versions of Apprise.

    Your wrapper should return True if processed the send() function as you
    expected and return False if not. If nothing is returned, then this is
    treated as as success (True).

    """
    def wrapper(func):
        """
        Instantiate our custom (notification) plugin
        """

        # Generate
        CustomNotifyPlugin.instantiate_plugin(
            url=on, send_func=func, name=name)

        return func

    return wrapper
