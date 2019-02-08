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
from ..utils import is_hostname
from ..common import NOTIFY_TYPES
from ..common import NotifyFormat
from ..common import NOTIFY_FORMATS

from ..AppriseAsset import AppriseAsset

# use sax first because it's faster
from xml.sax.saxutils import escape as sax_escape


def _escape(text):
    """
    saxutil escape tool
    """
    return sax_escape(text, {"'": "&apos;", "\"": "&quot;"})


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
    # us a safe play range...
    throttle_attempt = 5.5

    # Allows the user to specify the NotifyImageSize object
    image_size = None

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 32768

    # Defines the maximum allowable characters in the title
    title_maxlen = 250

    # Default Notify Format
    notify_format = NotifyFormat.TEXT

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

    def throttle(self, throttle_time=None):
        """
        A common throttle control
        """
        self.logger.debug('Throttling...')

        throttle_time = throttle_time \
            if throttle_time is not None else self.throttle_attempt

        # Perform throttle
        if throttle_time > 0:
            sleep(throttle_time)

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
        """
        if not html:
            # nothing more to do; return object as is
            return html

        escaped = _escape(html)

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
        common unquote function

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
        """
        common quote function

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
        """
        common urlencode function

        """
        try:
            # Python v3.x
            return _urlencode(
                query, doseq=doseq, safe=safe, encoding=encoding,
                errors=errors)

        except TypeError:
            # Python v2.7
            return _urlencode(query)

    @staticmethod
    def split_path(path, unquote=True):
        """
        Splits a URL up into a list object.

        """
        if unquote:
            return PATHSPLIT_LIST_DELIM.split(
                NotifyBase.unquote(path).lstrip('/'))
        return PATHSPLIT_LIST_DELIM.split(path.lstrip('/'))

    @staticmethod
    def is_email(address):
        """
        Returns True if specified entry is an email address

        """
        return IS_EMAIL_RE.match(address) is not None

    @staticmethod
    def is_hostname(hostname):
        """
        Returns True if specified entry is a hostname

        """
        return is_hostname(hostname)

    @staticmethod
    def parse_url(url, verify_host=True):
        """
        Parses the URL and returns it broken apart into a dictionary.

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

        # Password overrides
        if 'pass' in results['qsd']:
            results['password'] = results['qsd']['pass']

        # User overrides
        if 'user' in results['qsd']:
            results['user'] = results['qsd']['user']

        return results
