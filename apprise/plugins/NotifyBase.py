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

import re

from ..URLBase import URLBase
from ..common import NotifyType
from ..common import NOTIFY_TYPES
from ..common import NotifyFormat
from ..common import NOTIFY_FORMATS
from ..common import OverflowMode
from ..common import OVERFLOW_MODES


class NotifyBase(URLBase):
    """
    This is the base class for all notification services
    """

    # The services URL
    service_url = None

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = None

    # Most Servers do not like more then 1 request per 5 seconds, so 5.5 gives
    # us a safe play range. Override the one defined already in the URLBase
    request_rate_per_sec = 5.5

    # Allows the user to specify the NotifyImageSize object
    image_size = None

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 32768

    # Defines the maximum allowable characters in the title; set this to zero
    # if a title can't be used. Titles that are not used but are defined are
    # automatically placed into the body
    title_maxlen = 250

    # Set the maximum line count; if this is set to anything larger then zero
    # the message (prior to it being sent) will be truncated to this number
    # of lines. Setting this to zero disables this feature.
    body_max_line_count = 0

    # Default Notify Format
    notify_format = NotifyFormat.TEXT

    # Default Overflow Mode
    overflow_mode = OverflowMode.UPSTREAM

    # Default Title HTML Tagging
    # When a title is specified for a notification service that doesn't accept
    # titles, by default apprise tries to give a plesant view and convert the
    # title so that it can be placed into the body. The default is to just
    # use a <b> tag.  The below causes the <b>title</b> to get generated:
    default_html_tag_id = 'b'

    def __init__(self, **kwargs):
        """
        Initialize some general configuration that will keep things consistent
        when working with the notifiers that will inherit this class.

        """

        super(NotifyBase, self).__init__(**kwargs)

        if 'format' in kwargs:
            # Store the specified format if specified
            notify_format = kwargs.get('format', '')
            if notify_format.lower() not in NOTIFY_FORMATS:
                msg = 'Invalid notification format %s'.format(notify_format)
                self.logger.error(msg)
                raise TypeError(msg)

            # Provide override
            self.notify_format = notify_format

        if 'overflow' in kwargs:
            # Store the specified format if specified
            overflow = kwargs.get('overflow', '')
            if overflow.lower() not in OVERFLOW_MODES:
                msg = 'Invalid overflow method {}'.format(overflow)
                self.logger.error(msg)
                raise TypeError(msg)

            # Provide override
            self.overflow_mode = overflow

    def image_url(self, notify_type, logo=False, extension=None):
        """
        Returns Image URL if possible
        """

        if not self.image_size:
            return None

        if notify_type not in NOTIFY_TYPES:
            return None

        return self.asset.image_url(
            notify_type=notify_type,
            image_size=self.image_size,
            logo=logo,
            extension=extension,
        )

    def image_path(self, notify_type, extension=None):
        """
        Returns the path of the image if it can
        """
        if not self.image_size:
            return None

        if notify_type not in NOTIFY_TYPES:
            return None

        return self.asset.image_path(
            notify_type=notify_type,
            image_size=self.image_size,
            extension=extension,
        )

    def image_raw(self, notify_type, extension=None):
        """
        Returns the raw image if it can
        """
        if not self.image_size:
            return None

        if notify_type not in NOTIFY_TYPES:
            return None

        return self.asset.image_raw(
            notify_type=notify_type,
            image_size=self.image_size,
            extension=extension,
        )

    def color(self, notify_type, color_type=None):
        """
        Returns the html color (hex code) associated with the notify_type
        """
        if notify_type not in NOTIFY_TYPES:
            return None

        return self.asset.color(
            notify_type=notify_type,
            color_type=color_type,
        )

    def notify(self, body, title=None, notify_type=NotifyType.INFO,
               overflow=None, **kwargs):
        """
        Performs notification

        """

        # Handle situations where the title is None
        title = '' if not title else title

        # Apply our overflow (if defined)
        for chunk in self._apply_overflow(body=body, title=title,
                                          overflow=overflow):
            # Send notification
            if not self.send(body=chunk['body'], title=chunk['title'],
                             notify_type=notify_type):

                # Toggle our return status flag
                return False

        return True

    def _apply_overflow(self, body, title=None, overflow=None):
        """
        Takes the message body and title as input.  This function then
        applies any defined overflow restrictions associated with the
        notification service and may alter the message if/as required.

        The function will always return a list object in the following
        structure:
            [
                {
                    title: 'the title goes here',
                    body: 'the message body goes here',
                },
                {
                    title: 'the title goes here',
                    body: 'the message body goes here',
                },

            ]
        """

        response = list()

        # tidy
        title = '' if not title else title.strip()
        body = '' if not body else body.rstrip()

        if overflow is None:
            # default
            overflow = self.overflow_mode

        if self.title_maxlen <= 0 and len(title) > 0:
            if self.notify_format == NotifyFormat.MARKDOWN:
                # Content is appended to body as markdown
                body = '**{}**\r\n{}'.format(title, body)

            elif self.notify_format == NotifyFormat.HTML:
                # Content is appended to body as html
                body = '<{open_tag}>{title}</{close_tag}>' \
                    '<br />\r\n{body}'.format(
                        open_tag=self.default_html_tag_id,
                        title=self.escape_html(title),
                        close_tag=self.default_html_tag_id,
                        body=body)
            else:
                # Content is appended to body as text
                body = '{}\r\n{}'.format(title, body)

            title = ''

        # Enforce the line count first always
        if self.body_max_line_count > 0:
            # Limit results to just the first 2 line otherwise
            # there is just to much content to display
            body = re.split(r'\r*\n', body)
            body = '\r\n'.join(body[0:self.body_max_line_count])

        if overflow == OverflowMode.UPSTREAM:
            # Nothing more to do
            response.append({'body': body, 'title': title})
            return response

        elif len(title) > self.title_maxlen:
            # Truncate our Title
            title = title[:self.title_maxlen]

        if self.body_maxlen > 0 and len(body) <= self.body_maxlen:
            response.append({'body': body, 'title': title})
            return response

        if overflow == OverflowMode.TRUNCATE:
            # Truncate our body and return
            response.append({
                'body': body[:self.body_maxlen],
                'title': title,
            })
            # For truncate mode, we're done now
            return response

        # If we reach here, then we are in SPLIT mode.
        # For here, we want to split the message as many times as we have to
        # in order to fit it within the designated limits.
        response = [{
            'body': body[i: i + self.body_maxlen],
            'title': title} for i in range(0, len(body), self.body_maxlen)]

        return response

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Should preform the actual notification itself.

        """
        raise NotImplementedError(
            "send() is not implimented by the child class.")

    @staticmethod
    def parse_url(url, verify_host=True):
        """Parses the URL and returns it broken apart into a dictionary.

        This is very specific and customized for Apprise.


        Args:
            url (str): The URL you want to fully parse.
            verify_host (:obj:`bool`, optional): a flag kept with the parsed
                 URL which some child classes will later use to verify SSL
                 keys (if SSL transactions take place).  Unless under very
                 specific circumstances, it is strongly recomended that
                 you leave this default value set to True.

        Returns:
            A dictionary is returned containing the URL fully parsed if
            successful, otherwise None is returned.
        """
        results = URLBase.parse_url(url, verify_host=verify_host)

        if not results:
            # We're done; we failed to parse our url
            return results

        # Allow overriding the default format
        if 'format' in results['qsd']:
            results['format'] = results['qsd'].get('format')
            if results['format'] not in NOTIFY_FORMATS:
                URLBase.logger.warning(
                    'Unsupported format specified {}'.format(
                        results['format']))
                del results['format']

        # Allow overriding the default overflow
        if 'overflow' in results['qsd']:
            results['overflow'] = results['qsd'].get('overflow')
            if results['overflow'] not in OVERFLOW_MODES:
                URLBase.logger.warning(
                    'Unsupported overflow specified {}'.format(
                        results['overflow']))
                del results['overflow']

        return results
