# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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
import re
from .logger import logger
import time
import hashlib
from datetime import datetime
from xml.sax.saxutils import escape as sax_escape

from urllib.parse import unquote as _unquote
from urllib.parse import quote as _quote

from .locale import gettext_lazy as _
from .asset import AppriseAsset
from .utils.parse import (
    urlencode, parse_url, parse_bool, parse_list, parse_phone_no)

# Used to break a path list into parts
PATHSPLIT_LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')


class PrivacyMode:
    # Defines different privacy modes strings can be printed as
    # Astrisk sets 4 of them: e.g. ****
    # This is used for passwords
    Secret = '*'

    # Outer takes the first and last character displaying them with
    # 3 dots between.  Hence, 'i-am-a-token' would become 'i...n'
    Outer = 'o'

    # Displays the last four characters
    Tail = 't'


# Define the HTML Lookup Table
HTML_LOOKUP = {
    400: 'Bad Request - Unsupported Parameters.',
    401: 'Verification Failed.',
    404: 'Page not found.',
    405: 'Method not allowed.',
    500: 'Internal server error.',
    503: 'Servers are overloaded.',
}


class URLBase:
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

    # The connect timeout is the number of seconds Requests will wait for your
    # client to establish a connection to a remote machine (corresponding to
    # the connect()) call on the socket.
    socket_connect_timeout = 4.0

    # The read timeout is the number of seconds the client will wait for the
    # server to send a response.
    socket_read_timeout = 4.0

    # provide the information required to allow for unique id generation when
    # calling url_id().  Over-ride this in calling classes. Calling classes
    # should set this to false if there can be no url_id generated
    url_identifier = None

    # Tracks the last generated url_id() to prevent regeneration; initializes
    # to False and is set thereafter.  This is an internal value for this class
    # only and should not be set to anything other then False below...
    __cached_url_identifier = False

    # Handle
    # Maintain a set of tags to associate with this specific notification
    tags = set()

    # Secure sites should be verified against a Certificate Authority
    verify_certificate = True

    # Logging to our global logger
    logger = logger

    # Define a default set of template arguments used for dynamically building
    # details about our individual plugins for developers.

    # Define object templates
    templates = ()

    # Provides a mapping of tokens, certain entries are fixed and automatically
    # configured if found (such as schema, host, user, pass, and port)
    template_tokens = {}

    # Here is where we define all of the arguments we accept on the url
    # such as: schema://whatever/?cto=5.0&rto=15
    # These act the same way as tokens except they are optional and/or
    # have default values set if mandatory. This rule must be followed
    template_args = {
        'verify': {
            'name': _('Verify SSL'),
            # SSL Certificate Authority Verification
            'type': 'bool',
            # Provide a default
            'default': verify_certificate,
            # look up default using the following parent class value at
            # runtime.
            '_lookup_default': 'verify_certificate',
        },
        'rto': {
            'name': _('Socket Read Timeout'),
            'type': 'float',
            # Provide a default
            'default': socket_read_timeout,
            # look up default using the following parent class value at
            # runtime. The variable name identified here (in this case
            # socket_read_timeout) is checked and it's result is placed
            # over-top of  the 'default'. This is done because once a parent
            # class inherits this one, the overflow_mode already set as a
            # default 'could' be potentially over-ridden and changed to a
            # different value.
            '_lookup_default': 'socket_read_timeout',
        },
        'cto': {
            'name': _('Socket Connect Timeout'),
            'type': 'float',
            # Provide a default
            'default': socket_connect_timeout,
            # look up default using the following parent class value at
            # runtime. The variable name identified here (in this case
            # socket_connect_timeout) is checked and it's result is placed
            # over-top of  the 'default'. This is done because once a parent
            # class inherits this one, the overflow_mode already set as a
            # default 'could' be potentially over-ridden and changed to a
            # different value.
            '_lookup_default': 'socket_connect_timeout',
        },
    }

    # kwargs are dynamically built because a prefix causes us to parse the
    # content slightly differently. The prefix is required and can be either
    # a (+ or -). Below would handle the +key=value:
    #    {
    #        'headers': {
    #           'name': _('HTTP Header'),
    #           'prefix': '+',
    #           'type': 'string',
    #        },
    #    },
    #
    # In a kwarg situation, the 'key' is always presumed to be treated as
    # a string.  When the 'type' is defined, it is being defined to respect
    # the 'value'.

    template_kwargs = {}

    # Internal Values

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
        self.verify_certificate = parse_bool(
            kwargs.get('verify', URLBase.verify_certificate))

        # Schema
        self.schema = kwargs.get('schema', 'unknown').lower()

        # Secure Mode
        self.secure = kwargs.get('secure', None)
        if not isinstance(self.secure, bool):
            # Attempt to detect
            self.secure = self.schema[-1:] == 's'

        self.host = URLBase.unquote(kwargs.get('host'))
        self.port = kwargs.get('port')
        if self.port:
            try:
                self.port = int(self.port)

            except (TypeError, ValueError):
                self.logger.warning(
                    'Invalid port number specified {}'
                    .format(self.port))
                self.port = None

        self.user = kwargs.get('user')
        if self.user:
            # Always unquote user if it exists
            self.user = URLBase.unquote(self.user)

        self.password = kwargs.get('password')
        if self.password:
            # Always unquote the password if it exists
            self.password = URLBase.unquote(self.password)

        # Store our full path consistently ensuring it ends with a `/'
        self.fullpath = URLBase.unquote(kwargs.get('fullpath'))
        if not isinstance(self.fullpath, str) or not self.fullpath:
            self.fullpath = '/'

        # Store our Timeout Variables
        if 'rto' in kwargs:
            try:
                self.socket_read_timeout = float(kwargs.get('rto'))
            except (TypeError, ValueError):
                self.logger.warning(
                    'Invalid socket read timeout (rto) was specified {}'
                    .format(kwargs.get('rto')))

        if 'cto' in kwargs:
            try:
                self.socket_connect_timeout = float(kwargs.get('cto'))

            except (TypeError, ValueError):
                self.logger.warning(
                    'Invalid socket connect timeout (cto) was specified {}'
                    .format(kwargs.get('cto')))

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

        if self.request_rate_per_sec <= 0.0 and not wait:
            # We're done if there is no throttle limit set
            return

        # If we reach here, we need to do additional logic.
        # If the difference between the reference time and 'now' is less than
        # the defined request_rate_per_sec then we need to throttle for the
        # remaining balance of this time.

        elapsed = (reference - self._last_io_datetime).total_seconds()

        if wait is not None:
            self.logger.debug('Throttling forced for {}s...'.format(wait))
            time.sleep(wait)

        elif elapsed < self.request_rate_per_sec:
            self.logger.debug('Throttling for {}s...'.format(
                self.request_rate_per_sec - elapsed))
            time.sleep(self.request_rate_per_sec - elapsed)

        # Update our timestamp before we leave
        self._last_io_datetime = datetime.now()
        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Assembles the URL associated with the notification based on the
        arguments provied.

        """

        # Our default parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=URLBase.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=URLBase.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}{fullpath}{params}'.format(
            schema='https' if self.secure else 'http',
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            fullpath=URLBase.quote(self.fullpath, safe='/')
            if self.fullpath else '/',
            params=('?' + URLBase.urlencode(params) if params else ''),
        )

    def url_id(self, lazy=True, hash_engine=hashlib.sha256):
        """
        Returns a unique URL identifier that representing the Apprise URL
        itself. The url_id is always a hash string or None if it can't
        be generated.

        The idea is to only build the ID based on the credentials or specific
        elements relative to the URL itself. The URL ID should never factor in
        (or else it's a bug) the following:
          - any targets defined
          - all GET parameters options unless they explicitly change the
            complete function of the code.

             For example: GET parameters like ?image=false&avatar=no should
             have no bearing in the uniqueness of the Apprise URL Identifier.

             Consider plugins where some get parameters completely change
             how the entire upstream comunication works such as slack:// and
             matrix:// which has a mode. In these circumstances, they should
             be considered in he unique generation.

        The intention of this function is to help align Apprise URLs that are
        common with one another and therefore can share the same persistent
        storage even when subtle changes are made to them.

        Hence the following would all return the same URL Identifier:
             json://abc/def/ghi?image=no
             json://abc/def/ghi/?test=yes&image=yes

        """

        if lazy and self.__cached_url_identifier is not False:
            return self.__cached_url_identifier \
                if not (self.__cached_url_identifier
                        and self.asset.storage_idlen) \
                else self.__cached_url_identifier[:self.asset.storage_idlen]

        # Python v3.9 introduces usedforsecurity argument
        kwargs = {'usedforsecurity': False} \
            if sys.version_info >= (3, 9) else {}

        if self.url_identifier is False:
            # Disabled
            self.__cached_url_identifier = None

        elif self.url_identifier in (None, True):

            # Prepare our object
            engine = hash_engine(
                self.asset.storage_salt + self.schema.encode(
                    self.asset.encoding), **kwargs)

            # We want to treat `None` differently then a blank entry
            engine.update(
                b'\0' if self.password is None
                else self.password.encode(self.asset.encoding))
            engine.update(
                b'\0' if self.user is None
                else self.user.encode(self.asset.encoding))
            engine.update(
                b'\0' if not self.host
                else self.host.encode(self.asset.encoding))
            engine.update(
                b'\0' if self.port is None
                else f'{self.port}'.encode(self.asset.encoding))
            engine.update(
                self.fullpath.rstrip('/').encode(self.asset.encoding))
            engine.update(b's' if self.secure else b'i')

            # Save our generated content
            self.__cached_url_identifier = engine.hexdigest()

        elif isinstance(self.url_identifier, str):
            self.__cached_url_identifier = hash_engine(
                self.asset.storage_salt + self.url_identifier.encode(
                    self.asset.encoding), **kwargs).hexdigest()

        elif isinstance(self.url_identifier, bytes):
            self.__cached_url_identifier = hash_engine(
                self.asset.storage_salt + self.url_identifier,
                **kwargs).hexdigest()

        elif isinstance(self.url_identifier, (list, tuple, set)):
            self.__cached_url_identifier = hash_engine(
                self.asset.storage_salt + b''.join([
                    (x if isinstance(x, bytes)
                     else str(x).encode(self.asset.encoding))
                    for x in self.url_identifier]), **kwargs).hexdigest()

        elif isinstance(self.url_identifier, dict):
            self.__cached_url_identifier = hash_engine(
                self.asset.storage_salt + b''.join([
                    (x if isinstance(x, bytes)
                     else str(x).encode(self.asset.encoding))
                    for x in self.url_identifier.values()]),
                **kwargs).hexdigest()

        else:
            self.__cached_url_identifier = hash_engine(
                self.asset.storage_salt + str(
                    self.url_identifier).encode(self.asset.encoding),
                **kwargs).hexdigest()

        return self.__cached_url_identifier \
            if not (self.__cached_url_identifier
                    and self.asset.storage_idlen) \
            else self.__cached_url_identifier[:self.asset.storage_idlen]

    def __contains__(self, tags):
        """
        Returns true if the tag specified is associated with this notification.

        tag can also be a tuple, set, and/or list

        """
        if isinstance(tags, (tuple, set, list)):
            return bool(set(tags) & self.tags)

        # return any match
        return tags in self.tags

    def __str__(self):
        """
        Returns the url path
        """
        return self.url(privacy=True)

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
        if not isinstance(html, str) or not html:
            return ''

        # Escape HTML
        escaped = sax_escape(html, {"'": "&apos;", "\"": "&quot;"})

        if whitespace:
            # Tidy up whitespace too
            escaped = escaped\
                .replace(u'\t', u'&emsp;')\
                .replace(u' ', u'&nbsp;')

        if convert_new_lines:
            return escaped.replace(u'\n', u'<br/>')

        return escaped

    @staticmethod
    def unquote(content, encoding='utf-8', errors='replace'):
        """
        Replace %xx escapes by their single-character equivalent. The optional
        encoding and errors parameters specify how to decode percent-encoded
        sequences.

        Wrapper to Python's `unquote` while remaining compatible with both
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

        return _unquote(content, encoding=encoding, errors=errors)

    @staticmethod
    def quote(content, safe='/', encoding=None, errors=None):
        """ Replaces single character non-ascii characters and URI specific
        ones by their %xx code.

        Wrapper to Python's `quote` while remaining compatible with both
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

        return _quote(content, safe=safe, encoding=encoding, errors=errors)

    @staticmethod
    def pprint(content, privacy=True, mode=PrivacyMode.Outer,
               # privacy print; quoting is ignored when privacy is set to True
               quote=True, safe='/', encoding=None, errors=None):
        """
        Privacy Print is used to mainpulate the string before passing it into
        part of the URL.  It is used to mask/hide private details such as
        tokens, passwords, apikeys, etc from on-lookers.  If the privacy=False
        is set, then the quote variable is the next flag checked.

        Quoting is never done if the privacy flag is set to true to avoid
        skewing the expected output.
        """

        if not privacy:
            if quote:
                # Return quoted string if specified to do so
                return URLBase.quote(
                    content, safe=safe, encoding=encoding, errors=errors)

                # Return content 'as-is'
            return content

        if mode is PrivacyMode.Secret:
            # Return 4 Asterisks
            return '****'

        if not isinstance(content, str) or not content:
            # Nothing more to do
            return ''

        if mode is PrivacyMode.Tail:
            # Return the trailing 4 characters
            return '...{}'.format(content[-4:])

        # Default mode is Outer Mode
        return '{}...{}'.format(content[0:1], content[-1:])

    @staticmethod
    def urlencode(query, doseq=False, safe='', encoding=None, errors=None):
        """Convert a mapping object or a sequence of two-element tuples

        Wrapper to Python's `urlencode` while remaining compatible with both
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
        return urlencode(
            query, doseq=doseq, safe=safe, encoding=encoding, errors=errors)

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
    def parse_list(content, allow_whitespace=True, unquote=True):
        """A wrapper to utils.parse_list() with unquoting support

        Parses a specified set of data and breaks it into a list.

        Args:
            content (str): The path to split up into a list. If a list is
                 provided, then it's individual entries are processed.

            allow_whitespace (:obj:`bool`, optional): whitespace is to be
                 treated as a delimiter

            unquote (:obj:`bool`, optional): call unquote on each element
                 added to the returned list.

        Returns:
            list: A unique list containing all of the elements in the path
        """

        content = parse_list(content, allow_whitespace=allow_whitespace)
        if unquote:
            content = \
                [URLBase.unquote(x) for x in filter(bool, content)]

        return content

    @staticmethod
    def parse_phone_no(content, unquote=True, prefix=False):
        """A wrapper to utils.parse_phone_no() with unquoting support

        Parses a specified set of data and breaks it into a list.

        Args:
            content (str): The path to split up into a list. If a list is
                 provided, then it's individual entries are processed.

            unquote (:obj:`bool`, optional): call unquote on each element
                 added to the returned list.

        Returns:
            list: A unique list containing all of the elements in the path
        """

        if unquote:
            try:
                content = URLBase.unquote(content)
            except TypeError:
                # Nothing further to do
                return []

        content = parse_phone_no(content, prefix=prefix)

        return content

    @property
    def app_id(self):
        return self.asset.app_id if self.asset.app_id else ''

    @property
    def app_desc(self):
        return self.asset.app_desc if self.asset.app_desc else ''

    @property
    def app_url(self):
        return self.asset.app_url if self.asset.app_url else ''

    @property
    def request_timeout(self):
        """This is primarily used to fullfill the `timeout` keyword argument
        that is used by requests.get() and requests.put() calls.
        """
        return (self.socket_connect_timeout, self.socket_read_timeout)

    @property
    def request_auth(self):
        """This is primarily used to fullfill the `auth` keyword argument
        that is used by requests.get() and requests.put() calls.
        """
        return (self.user, self.password) if self.user else None

    @property
    def request_url(self):
        """
        Assemble a simple URL that can be used by the requests library

        """

        # Acquire our schema
        schema = 'https' if self.secure else 'http'

        # Prepare our URL
        url = '%s://%s' % (schema, self.host)

        # Apply Port information if present
        if isinstance(self.port, int):
            url += ':%d' % self.port

        # Append our full path
        return url + self.fullpath

    def url_parameters(self, *args, **kwargs):
        """
        Provides a default set of args to work with. This can greatly
        simplify URL construction in the acommpanied url() function.

        The following property returns a dictionary (of strings) containing
        all of the parameters that can be set on a URL and managed through
        this class.
        """

        # parameters are only provided on demand to keep the URL short
        params = {}

        # The socket read timeout
        if self.socket_read_timeout != URLBase.socket_read_timeout:
            params['rto'] = str(self.socket_read_timeout)

        # The request/socket connect timeout
        if self.socket_connect_timeout != URLBase.socket_connect_timeout:
            params['cto'] = str(self.socket_connect_timeout)

        # Certificate verification
        if self.verify_certificate != URLBase.verify_certificate:
            params['verify'] = 'yes' if self.verify_certificate else 'no'

        return params

    @staticmethod
    def post_process_parse_url_results(results):
        """
        After parsing the URL, this function applies a bit of extra logic to
        support extra entries like `pass` becoming `password`, etc

        This function assumes that parse_url() was called previously setting
        up the basics to be checked
        """

        # if our URL ends with an 's', then assume our secure flag is set.
        results['secure'] = (results['schema'][-1] == 's')

        # QSD Checking (over-rides all)
        qsd_exists = True if isinstance(results.get('qsd'), dict) else False

        if qsd_exists and 'verify' in results['qsd']:
            # Pulled from URL String
            results['verify'] = parse_bool(
                results['qsd'].get('verify', True))

        elif 'verify' in results:
            # Pulled from YAML Configuratoin
            results['verify'] = parse_bool(results.get('verify', True))

        else:
            # Support SSL Certificate 'verify' keyword. Default to being
            # enabled
            results['verify'] = True

        # Password overrides
        if 'pass' in results:
            results['password'] = results['pass']
            del results['pass']

        if qsd_exists:
            if 'password' in results['qsd']:
                results['password'] = results['qsd']['password']
            if 'pass' in results['qsd']:
                results['password'] = results['qsd']['pass']

            # User overrides
            if 'user' in results['qsd']:
                results['user'] = results['qsd']['user']

            # parse_url() always creates a 'password' and 'user' entry in the
            # results returned.  Entries are set to None if they weren't
            # specified
            if results['password'] is None and 'user' in results['qsd']:
                # Handle cases where the user= provided in 2 locations, we want
                # the original to fall back as a being a password (if one
                # wasn't otherwise defined) e.g.
                #    mailtos://PASSWORD@hostname?user=admin@mail-domain.com
                # - in the above, the PASSWORD gets lost in the parse url()
                #   since a user= over-ride is specified.
                presults = parse_url(results['url'])
                if presults:
                    # Store our Password
                    results['password'] = presults['user']

            # Store our socket read timeout if specified
            if 'rto' in results['qsd']:
                results['rto'] = results['qsd']['rto']

            # Store our socket connect timeout if specified
            if 'cto' in results['qsd']:
                results['cto'] = results['qsd']['cto']

            if 'port' in results['qsd']:
                results['port'] = results['qsd']['port']

        return results

    @staticmethod
    def parse_url(url, verify_host=True, plus_to_space=False,
                  strict_port=False, sanitize=True):
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
            url, default_schema='unknown', verify_host=verify_host,
            plus_to_space=plus_to_space, strict_port=strict_port,
            sanitize=sanitize)

        if not results:
            # We're done; we failed to parse our url
            return results

        return URLBase.post_process_parse_url_results(results)

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

    def __len__(self):
        """
        Should be over-ridden and allows the tracking of how many targets
        are associated with each URLBase object.

        Default is always 1
        """
        return 1

    def schemas(self):
        """A simple function that returns a set of all schemas associated
        with this object based on the object.protocol and
        object.secure_protocol
        """

        schemas = set([])

        for key in ('protocol', 'secure_protocol'):
            schema = getattr(self, key, None)
            if isinstance(schema, str):
                schemas.add(schema)

            elif isinstance(schema, (set, list, tuple)):
                # Support iterables list types
                for s in schema:
                    if isinstance(s, str):
                        schemas.add(s)

        return schemas
