# -*- coding: utf-8 -*-
#
# Base Notify Wrapper
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

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
from ..common import NOTIFY_IMAGE_SIZES
from ..common import NOTIFY_TYPES

from ..AppriseAsset import AppriseAsset

# Define a general HTML Escaping
try:
    # use sax first because it's faster
    from xml.sax.saxutils import escape as sax_escape

    def _escape(text):
        """
        saxutil escape tool
        """
        return sax_escape(text, {"'": "&apos;", "\"": "&quot;"})

except ImportError:
    # if we can't, then fall back to cgi escape
    from cgi import escape as cgi_escape

    def _escape(text):
        """
        cgi escape tool
        """
        return cgi_escape(text, quote=True)


HTTP_ERROR_MAP = {
    400: 'Bad Request - Unsupported Parameters.',
    401: 'Verification Failed.',
    404: 'Page not found.',
    405: 'Method not allowed.',
    500: 'Internal server error.',
    503: 'Servers are overloaded.',
}

# HTML New Line Delimiter
NOTIFY_NEWLINE = '\n'

# Used to break a path list into parts
PATHSPLIT_LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')


class NotifyFormat(object):
    TEXT = 'text'
    HTML = 'html'
    MARKDOWN = 'markdown'


NOTIFY_FORMATS = (
    NotifyFormat.TEXT,
    NotifyFormat.HTML,
    NotifyFormat.MARKDOWN,
)

# Regular expression retrieved from:
# http://www.regular-expressions.info/email.html
IS_EMAIL_RE = re.compile(
    r"(?P<userid>[a-z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)"
    r"*)@(?P<domain>(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]*"
    r"[a-z0-9]))?",
    re.IGNORECASE,
)


class NotifyBase(object):
    """
    This is the base class for all notification services
    """

    # The default simple (insecure) protocol
    # all inheriting entries must provide their protocol lookup
    # protocol:// (in this example they would specify 'protocol')
    protocol = ''

    # The default secure protocol
    # all inheriting entries must provide their protocol lookup
    # protocols:// (in this example they would specify 'protocols')
    # This value can be the same as the defined protocol.
    secure_protocol = ''

    # our Application identifier
    app_id = 'Apprise'

    # our Application description
    app_desc = 'Apprise Notifications'

    # Most Servers do not like more then 1 request per 5 seconds, so 5.5 gives
    # us a safe play range...
    throttle_attempt = 5.5

    # Logging
    logger = logging.getLogger(__name__)

    def __init__(self, title_maxlen=100, body_maxlen=512,
                 notify_format=NotifyFormat.TEXT, image_size=None,
                 include_image=False, secure=False, throttle=None, **kwargs):
        """
        Initialize some general logging and common server arguments that will
        keep things consistent when working with the notifiers that will
        inherit this class.

        """

        if notify_format.lower() not in NOTIFY_FORMATS:
            self.logger.error(
                'Invalid notification format %s' % notify_format,
            )
            raise TypeError(
                'Invalid notification format %s' % notify_format,
            )

        if image_size and image_size not in NOTIFY_IMAGE_SIZES:
            self.logger.error(
                'Invalid image size %s' % image_size,
            )
            raise TypeError(
                'Invalid image size %s' % image_size,
            )

        # Prepare our Assets
        self.asset = AppriseAsset()

        self.notify_format = notify_format.lower()
        self.title_maxlen = title_maxlen
        self.body_maxlen = body_maxlen
        self.image_size = image_size
        self.include_image = include_image
        self.secure = secure

        if isinstance(throttle, (float, int)):
            # Custom throttle override
            self.throttle_attempt = throttle

        # Certificate Verification (for SSL calls); default to being enabled
        self.verify_certificate = kwargs.get('verify', True)

        self.host = kwargs.get('host', '')
        self.port = kwargs.get('port')
        if self.port:
            try:
                self.port = int(self.port)

            except (TypeError, ValueError):
                self.port = None

        self.user = kwargs.get('user')
        self.password = kwargs.get('password')

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

    def image_url(self, notify_type):
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
        )

    def image_path(self, notify_type):
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
        )

    def image_raw(self, notify_type):
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
        )

    @staticmethod
    def escape_html(html, convert_new_lines=False):
        """
        Takes html text as input and escapes it so that it won't
        conflict with any xml/html wrapping characters.
        """
        escaped = _escape(html).\
            replace(u'\t', u'&emsp;').\
            replace(u' ', u'&nbsp;')

        if convert_new_lines:
            return escaped.replace(u'\n', u'&lt;br/&gt;')

        return escaped

    @staticmethod
    def unquote(content, encoding='utf-8', errors='replace'):
        """
        common unquote function

        """
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
            return _urlencode(query, oseq=doseq)

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
    def parse_url(url):
        """
        Parses the URL and returns it broken apart into a dictionary.

        """
        results = parse_url(url, default_schema='unknown')

        if not results:
            # We're done; we failed to parse our url
            return results

        # if our URL ends with an 's', then assueme our secure flag is set.
        results['secure'] = (results['schema'][-1] == 's')

        # Our default notification format
        results['notify_format'] = NotifyFormat.TEXT

        # Support SSL Certificate 'verify' keyword. Default to being enabled
        results['verify'] = True

        if 'qsd' in results:
            if 'verify' in results['qsd']:
                results['verify'] = parse_bool(
                    results['qsd'].get('verify', True))

            # Password overrides
            if 'pass' in results['qsd']:
                results['password'] = results['qsd']['pass']

            # User overrides
            if 'user' in results['qsd']:
                results['user'] = results['qsd']['user']

        return results
