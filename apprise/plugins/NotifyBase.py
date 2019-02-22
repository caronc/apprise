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
import logging
from time import sleep
from datetime import datetime

try:
    # Python 2.7
    from urllib import unquote as _unquote
    from urllib import quote as _quote
    from urllib import urlencode as _urlencode

except ImportError:
    # Python 3.x
    from urllib.parse import unquote as _unquote
    from urllib.parse import quote as _quote
    from urllib.parse import urlencode as _urlencode

from ..utils import parse_url
from ..utils import parse_bool
from ..utils import parse_list
from ..utils import is_hostname
from ..common import NotifyType
from ..common import NOTIFY_TYPES
from ..common import NotifyFormat
from ..common import NOTIFY_FORMATS
from ..common import OverflowMode
from ..common import OVERFLOW_MODES

from ..AppriseAsset import AppriseAsset

# use sax first because it's faster
from xml.sax.saxutils import escape as sax_escape


HTTP_ERROR_MAP = {
    400: 'Bad Request - Unsupported Parameters.',
    401: 'Verification Failed.',
    404: 'Page not found.',
    405: 'Method not allowed.',
    500: 'Internal server error.',
    503: 'Servers are overloaded.',
}

# HTML New Line Delimiter
NOTIFY_NEWLINE = '\r\n'

# Used to break a path list into parts
PATHSPLIT_LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')

# Regular expression retrieved from:
# http://www.regular-expressions.info/email.html
IS_EMAIL_RE = re.compile(
    r"((?P<label>[^+]+)\+)?"
    r"(?P<userid>[a-z0-9$%=_~-]+"
    r"(?:\.[a-z0-9$%+=_~-]+)"
    r"*)@(?P<domain>(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]*"
    r"[a-z0-9]))?",
    re.IGNORECASE,
)


class NotifyBase(object):
    """
    This is the base class for all notification services
    """

    # The default descriptive name associated with the Notification
    service_name = None

    # The services URL
    service_url = None

    # The default simple (insecure) protocol
    # all inheriting entries must provide their protocol lookup
    # protocol:// (in this example they would specify 'protocol')
    protocol = None

    # The default secure protocol
    # all inheriting entries must provide their protocol lookup
    # protocols:// (in this example they would specify 'protocols')
    # This value can be the same as the defined protocol.
    secure_protocol = None

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = None

    # Most Servers do not like more then 1 request per 5 seconds, so 5.5 gives
    # us a safe play range.
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

    # Maintain a set of tags to associate with this specific notification
    tags = set()

    # Logging
    logger = logging.getLogger(__name__)

    def __init__(self, **kwargs):
        """
        Initialize some general logging and common server arguments that will
        keep things consistent when working with the notifiers that will
        inherit this class.

        """

        # Prepare our Assets
        self.asset = AppriseAsset()

        # Certificate Verification (for SSL calls); default to being enabled
        self.verify_certificate = kwargs.get('verify', True)

        # Secure Mode
        self.secure = kwargs.get('secure', False)

        self.host = kwargs.get('host', '')
        self.port = kwargs.get('port')
        if self.port:
            try:
                self.port = int(self.port)

            except (TypeError, ValueError):
                self.port = None

        self.user = kwargs.get('user')
        self.password = kwargs.get('password')

        if 'format' in kwargs:
            # Store the specified format if specified
            notify_format = kwargs.get('format', '')
            if notify_format.lower() not in NOTIFY_FORMATS:
                self.logger.error(
                    'Invalid notification format %s' % notify_format,
                )
                raise TypeError(
                    'Invalid notification format %s' % notify_format,
                )
            # Provide override
            self.notify_format = notify_format

        if 'overflow' in kwargs:
            # Store the specified format if specified
            overflow = kwargs.get('overflow', '')
            if overflow.lower() not in OVERFLOW_MODES:
                self.logger.error(
                    'Invalid overflow method %s' % overflow,
                )
                raise TypeError(
                    'Invalid overflow method %s' % overflow,
                )
            # Provide override
            self.overflow_mode = overflow

        if 'tag' in kwargs:
            # We want to associate some tags with our notification service.
            # the code below gets the 'tag' argument if defined, otherwise
            # it just falls back to whatever was already defined globally
            self.tags = set(parse_list(kwargs.get('tag', self.tags)))

        # Tracks the time any i/o was made to the remote server.  This value
        # is automatically set and controlled through the throttle() call.
        self._last_io_datetime = None

    def throttle(self, last_io=None):
        """
        A common throttle control
        """

        if last_io is not None:
            # Assume specified last_io
            self._last_io_datetime = last_io

        # Get ourselves a reference time of 'now'
        reference = datetime.now()

        if self._last_io_datetime is None:
            # Set time to 'now' and no need to throttle
            self._last_io_datetime = reference
            return

        if self.request_rate_per_sec <= 0.0:
            # We're done if there is no throttle limit set
            return

        # If we reach here, we need to do additional logic.
        # If the difference between the reference time and 'now' is less than
        # the defined request_rate_per_sec then we need to throttle for the
        # remaining balance of this time.

        elapsed = (reference - self._last_io_datetime).total_seconds()

        if elapsed < self.request_rate_per_sec:
            self.logger.debug('Throttling for {}s...'.format(
                self.request_rate_per_sec - elapsed))
            sleep(self.request_rate_per_sec - elapsed)

        # Update our timestamp before we leave
        self._last_io_datetime = reference
        return

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

        if self.title_maxlen <= 0:
            # Content is appended to body
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
        raise NotImplementedError("send() is implimented by the child class.")

    def url(self):
        """
        Assembles the URL associated with the notification based on the
        arguments provied.

        """
        raise NotImplementedError("url() is implimented by the child class.")

    def __contains__(self, tags):
        """
        Returns true if the tag specified is associated with this notification.

        tag can also be a tuple, set, and/or list

        """
        if isinstance(tags, (tuple, set, list)):
            return bool(set(tags) & self.tags)

        # return any match
        return tags in self.tags

    @property
    def app_id(self):
        return self.asset.app_id

    @property
    def app_desc(self):
        return self.asset.app_desc

    @property
    def app_url(self):
        return self.asset.app_url

    @staticmethod
    def escape_html(html, convert_new_lines=False, whitespace=True):
        """
        Takes html text as input and escapes it so that it won't
        conflict with any xml/html wrapping characters.

        Args:
            html (str): The HTML code to escape
            convert_new_lines (:obj:`bool`, optional): escape new lines (\n)
            whitespace (:obj:`bool`, optional): escape whitespace

        Returns:
            str: The escaped html
        """
        if not html:
            # nothing more to do; return object as is
            return html

        # Escape HTML
        escaped = sax_escape(html, {"'": "&apos;", "\"": "&quot;"})

        if whitespace:
            # Tidy up whitespace too
            escaped = escaped\
                .replace(u'\t', u'&emsp;')\
                .replace(u' ', u'&nbsp;')

        if convert_new_lines:
            return escaped.replace(u'\n', u'&lt;br/&gt;')

        return escaped

    @staticmethod
    def unquote(content, encoding='utf-8', errors='replace'):
        """
        Replace %xx escapes by their single-character equivalent. The optional
        encoding and errors parameters specify how to decode percent-encoded
        sequences.

        Wrapper to Python's unquote while remaining compatible with both
        Python 2 & 3 since the reference to this function changed between
        versions.

        Note: errors set to 'replace' means that invalid sequences are
              replaced by a placeholder character.

        Args:
            content (str): The quoted URI string you wish to unquote
            encoding (:obj:`str`, optional): encoding type
            errors (:obj:`str`, errors): how to handle invalid character found
                in encoded string (defined by encoding)

        Returns:
            str: The unquoted URI string
        """
        if not content:
            return ''

        try:
            # Python v3.x
            return _unquote(content, encoding=encoding, errors=errors)

        except TypeError:
            # Python v2.7
            return _unquote(content)

    @staticmethod
    def quote(content, safe='/', encoding=None, errors=None):
        """ Replaces single character non-ascii characters and URI specific
        ones by their %xx code.

        Wrapper to Python's unquote while remaining compatible with both
        Python 2 & 3 since the reference to this function changed between
        versions.

        Args:
            content (str): The URI string you wish to quote
            safe (str): non-ascii characters and URI specific ones that you
                        do not wish to escape (if detected). Setting this
                        string to an empty one causes everything to be
                        escaped.
            encoding (:obj:`str`, optional): encoding type
            errors (:obj:`str`, errors): how to handle invalid character found
                in encoded string (defined by encoding)

        Returns:
            str: The quoted URI string
        """
        if not content:
            return ''

        try:
            # Python v3.x
            return _quote(content, safe=safe, encoding=encoding, errors=errors)

        except TypeError:
            # Python v2.7
            return _quote(content, safe=safe)

    @staticmethod
    def urlencode(query, doseq=False, safe='', encoding=None, errors=None):
        """Convert a mapping object or a sequence of two-element tuples

        Wrapper to Python's unquote while remaining compatible with both
        Python 2 & 3 since the reference to this function changed between
        versions.

        The resulting string is a series of key=value pairs separated by '&'
        characters, where both key and value are quoted using the quote()
        function.

        Note: If the dictionary entry contains an entry that is set to None
              it is not included in the final result set. If you want to
              pass in an empty variable, set it to an empty string.

        Args:
            query (str): The dictionary to encode
            doseq (:obj:`bool`, optional): Handle sequences
            safe (:obj:`str`): non-ascii characters and URI specific ones that
                you do not wish to escape (if detected). Setting this string
                to an empty one causes everything to be escaped.
            encoding (:obj:`str`, optional): encoding type
            errors (:obj:`str`, errors): how to handle invalid character found
                in encoded string (defined by encoding)

        Returns:
            str: The escaped parameters returned as a string
        """
        # Tidy query by eliminating any records set to None
        _query = {k: v for (k, v) in query.items() if v is not None}
        try:
            # Python v3.x
            return _urlencode(
                _query, doseq=doseq, safe=safe, encoding=encoding,
                errors=errors)

        except TypeError:
            # Python v2.7
            return _urlencode(_query)

    @staticmethod
    def split_path(path, unquote=True):
        """Splits a URL up into a list object.

        Parses a specified URL and breaks it into a list.

        Args:
            path (str): The path to split up into a list.
            unquote (:obj:`bool`, optional): call unquote on each element
                 added to the returned list.

        Returns:
            list: A list containing all of the elements in the path
        """

        if unquote:
            return PATHSPLIT_LIST_DELIM.split(
                NotifyBase.unquote(path).lstrip('/'))
        return PATHSPLIT_LIST_DELIM.split(path.lstrip('/'))

    @staticmethod
    def is_email(address):
        """Determine if the specified entry is an email address

        Args:
            address (str): The string you want to check.

        Returns:
            bool: Returns True if the address specified is an email address
                  and False if it isn't.
        """

        return IS_EMAIL_RE.match(address) is not None

    @staticmethod
    def is_hostname(hostname):
        """Determine if the specified entry is a hostname

        Args:
            hostname (str): The string you want to check.

        Returns:
            bool: Returns True if the hostname specified is in fact a hostame
                  and False if it isn't.
        """
        return is_hostname(hostname)

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

        results = parse_url(
            url, default_schema='unknown', verify_host=verify_host)

        if not results:
            # We're done; we failed to parse our url
            return results

        # if our URL ends with an 's', then assueme our secure flag is set.
        results['secure'] = (results['schema'][-1] == 's')

        # Support SSL Certificate 'verify' keyword. Default to being enabled
        results['verify'] = verify_host

        if 'verify' in results['qsd']:
            results['verify'] = parse_bool(
                results['qsd'].get('verify', True))

        # Allow overriding the default format
        if 'format' in results['qsd']:
            results['format'] = results['qsd'].get('format')
            if results['format'] not in NOTIFY_FORMATS:
                NotifyBase.logger.warning(
                    'Unsupported format specified {}'.format(
                        results['format']))
                del results['format']

        # Allow overriding the default overflow
        if 'overflow' in results['qsd']:
            results['overflow'] = results['qsd'].get('overflow')
            if results['overflow'] not in OVERFLOW_MODES:
                NotifyBase.logger.warning(
                    'Unsupported overflow specified {}'.format(
                        results['overflow']))
                del results['overflow']

        # Password overrides
        if 'pass' in results['qsd']:
            results['password'] = results['qsd']['pass']

        # User overrides
        if 'user' in results['qsd']:
            results['user'] = results['qsd']['user']

        return results
