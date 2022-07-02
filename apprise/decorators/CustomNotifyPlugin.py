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
from ..plugins.NotifyBase import NotifyBase
from ..common import NotifyType
from ..common import CUSTOM_PLUGIN_MAP
from ..utils import IS_SCHEMA_RE
from ..utils import parse_url
from .. import plugins
from ..logger import logger
import inspect


class CustomNotifyPlugin(NotifyBase):
    """
    Apprise Custom Plugin Hook

    This gets initialized based on @notify decorator definitions

    """
    # Our Custom notification
    service_url = 'https://github.com/caronc/apprise/wiki/Custom_Notification'

    # Over-ride our category since this inheritance of the NotifyBase class
    # should be treated differently.
    category = 'custom'

    # Define object templates
    templates = (
        '{schema}://',
    )

    # Our default arguments will get populated after we're instatiated by the
    # wrapper class
    __default_args = {}

    def __init__(self, **kwargs):
        """
        Our initialization

        """
        super(CustomNotifyPlugin, self).__init__(**kwargs)

        # Apply our updates based on what was parsed
        self.__default_args.update(kwargs)

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns arguments retrieved

        """
        return NotifyBase.parse_url(url, verify_host=False)

    def url(self, privacy=False, *args, **kwargs):
        """
        General URL assembly
        """
        return '{schema}://'.format(schema=self.secure_protocol)

    @staticmethod
    def instantiate_plugin(url, send_func, name=None):
        """
        The function used to add a new notification plugin based on the schema
        parsed from the provided URL into our supported matrix structure.
        """

        # Validate that our schema is okay

        re_match = IS_SCHEMA_RE.match(url)
        if not re_match:
            msg = 'An invalid custom notify url/schema ({}) provided in ' \
                'function {}.'.format(url, send_func.__name__)
            logger.warning(msg)
            return None

        # Keep a default set of arguments to apply to all called references
        default_args = parse_url(url, verify_host=False)
        if default_args['schema'] in plugins.SCHEMA_MAP:
            # we're already handling this object
            msg = 'The schema ({}) is already defined and could not be ' \
                'loaded from custom notify function {}.' \
                .format(url, send_func.__name__)
            logger.warning(msg)
            return None

        # Acquire our plugin name
        plugin_name = re_match.group('schema').lower()

        # We define our own custom wrapper class so that we can initialize
        # some key default configuration values allowing calls to our
        # `Apprise.details()` to correctly differentiate one custom plugin
        # that was loaded from another
        class CustomNotifyPluginWrapper(CustomNotifyPlugin):

            # Our Service Name
            service_name = name if name else 'Custom - {}'.format(plugin_name)

            # Store our matched schema
            secure_protocol = plugin_name

            requirements = {
                # Define our required packaging in order to work
                'details': "Source: {}".format(inspect.getfile(send_func))
            }

            # Assign our send() function
            __send = staticmethod(send_func)

            # Update our default arguments
            __default_args = default_args

            def send(self, body, title='', notify_type=NotifyType.INFO, *args,
                     **kwargs):
                """
                Our send() call which triggers our hook
                """

                response = False
                try:
                    # Enforce a boolean response
                    result = self.__send(
                        body, title, notify_type, *args,
                        meta=self.__default_args, **kwargs)

                    if result is None:
                        # The wrapper did not define a return (or returned
                        # None)
                        # this is treated as a successful return as it is
                        # assumed the developer did not care about the result
                        # of the call.
                        response = True

                    else:
                        # Perform boolean check (allowing obects to also be
                        # returned and check against the __bool__ call
                        response = True if result else False

                except Exception as e:
                    # Unhandled Exception
                    self.logger.warning(
                        'An exception occured sending a %s notification.',
                        plugins.SCHEMA_MAP[self.secure_protocol].service_name)
                    self.logger.debug(
                        '%s Exception: %s',
                        plugins.SCHEMA_MAP[self.secure_protocol], str(e))
                    return False

                if response:
                    self.logger.info(
                        'Sent %s notification.',
                        plugins.SCHEMA_MAP[self.secure_protocol].service_name)
                else:
                    self.logger.warning(
                        'Failed to send %s notification.',
                        plugins.SCHEMA_MAP[self.secure_protocol].service_name)
                return response

        # Store our plugin
        plugins.SCHEMA_MAP[plugin_name] = CustomNotifyPluginWrapper

        # Update our custom plugin map
        module_name = str(send_func.__module__)
        CUSTOM_PLUGIN_MAP[module_name]['services'][plugin_name] = {
            'name': CustomNotifyPluginWrapper.service_name,
            'fn_name': send_func.__name__,
            'url': url,
            'plugin': CustomNotifyPluginWrapper,
        }

        return plugins.SCHEMA_MAP[plugin_name]
