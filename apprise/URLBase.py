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
import six
import logging
from time import sleep
from datetime import datetime
from xml.sax.saxutils import escape as sax_escape

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

from .AppriseAsset import AppriseAsset
from .utils import parse_url
from .utils import parse_bool
from .utils import parse_list

# Used to break a path list into parts
PATHSPLIT_LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')

# Define the HTML Lookup Table
HTML_LOOKUP = {
    400: 'Bad Request - Unsupported Parameters.',
    401: 'Verification Failed.',
    404: 'Page not found.',
    405: 'Method not allowed.',
    500: 'Internal server error.',
    503: 'Servers are overloaded.',
}


class URLBase(object):
    """
    This is the base class for all URL Manipulation
    """

    # The default descriptive name associated with the URL
    service_name = None

    # The default simple (insecure) protocol
    # all inheriting entries must provide their protocol lookup
    # protocol:// (in this example they would specify 'protocol')
    protocol = None

    # The default secure protocol
    # all inheriting entries must provide their protocol lookup
    # protocols:// (in this example they would specify 'protocols')
    # This value can be the same as the defined protocol.
    secure_protocol = None

    # Throttle
    request_rate_per_sec = 0

    # Maintain a set of tags to associate with this specific notification
    tags = set()

    # Logging
    logger = logging.getLogger(__name__)

    def __init__(self, asset=None, **kwargs):
        """
        Initialize some general logging and common server arguments that will
        keep things consistent when working with the children that
        inherit this class.

        """
        # Prepare our Asset Object
        self.asset = \
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()

        # Certificate Verification (for SSL calls); default to being enabled
        self.verify_certificate = kwargs.get('verify', True)

        # Secure Mode
        self.secure = kwargs.get('secure', False)

        self.host = URLBase.unquote(kwargs.get('host'))
        self.port = kwargs.get('port')
        if self.port:
            try:
                self.port = int(self.port)

            except (TypeError, ValueError):
                self.port = None

        self.user = kwargs.get('user')
        if self.user:
            # Always unquote user if it exists
            self.user = URLBase.unquote(self.user)

        self.password = kwargs.get('password')
        if self.password:
            # Always unquote the password if it exists
            self.password = URLBase.unquote(self.password)

        if 'tag' in kwargs:
            # We want to associate some tags with our notification service.
            # the code below gets the 'tag' argument if defined, otherwise
            # it just falls back to whatever was already defined globally
            self.tags = set(parse_list(kwargs.get('tag'), self.tags))

        # Tracks the time any i/o was made to the remote server.  This value
        # is automatically set and controlled through the throttle() call.
        self._last_io_datetime = None

    def throttle(self, last_io=None, wait=None):
        """
        A common throttle control

        if a wait is specified, then it will force a sleep of the
        specified time if it is larger then the calculated throttle
        time.
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

        if wait is not None:
            self.logger.debug('Throttling forced for {}s...'.format(wait))
            sleep(wait)

        elif elapsed < self.request_rate_per_sec:
            self.logger.debug('Throttling for {}s...'.format(
                self.request_rate_per_sec - elapsed))
            sleep(self.request_rate_per_sec - elapsed)

        # Update our timestamp before we leave
        self._last_io_datetime = datetime.now()
        return

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
        if not isinstance(html, six.string_types) or not html:
            return ''

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

        try:
            paths = PATHSPLIT_LIST_DELIM.split(path.lstrip('/'))
            if unquote:
                paths = \
                    [URLBase.unquote(x) for x in filter(bool, paths)]

        except AttributeError:
            # path is not useable, we still want to gracefully return an
            # empty list
            paths = []

        return paths

    @staticmethod
    def parse_list(content, unquote=True):
        """A wrapper to utils.parse_list() with unquoting support

        Parses a specified set of data and breaks it into a list.

        Args:
            content (str): The path to split up into a list. If a list is
                 provided, then it's individual entries are processed.

            unquote (:obj:`bool`, optional): call unquote on each element
                 added to the returned list.

        Returns:
            list: A unique list containing all of the elements in the path
        """

        content = parse_list(content)
        if unquote:
            content = \
                [URLBase.unquote(x) for x in filter(bool, content)]

        return content

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
        results['verify'] = True

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

    @staticmethod
    def http_response_code_lookup(code, response_mask=None):
        """Parses the interger response code returned by a remote call from
        a web request into it's human readable string version.

        You can over-ride codes or add new ones by providing your own
        response_mask that contains a dictionary of integer -> string mapped
        variables
        """
        if isinstance(response_mask, dict):
            # Apply any/all header over-rides defined
            HTML_LOOKUP.update(response_mask)

        # Look up our response
        try:
            response = HTML_LOOKUP[code]

        except KeyError:
            response = ''

        return response
