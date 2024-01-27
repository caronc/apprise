# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

import re
import sys
import json
import contextlib
import os
import locale
from itertools import chain
from os.path import expanduser
from functools import reduce
from . import common
from .logger import logger
from urllib.parse import unquote
from urllib.parse import quote
from urllib.parse import urlparse
from urllib.parse import urlencode as _urlencode

import importlib.util


def import_module(path, name):
    """
    Load our module based on path
    """
    spec = importlib.util.spec_from_file_location(name, path)
    try:
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module

        spec.loader.exec_module(module)

    except Exception as e:
        # module isn't loadable
        try:
            del sys.modules[name]

        except KeyError:
            # nothing to clean up
            pass

        module = None

        logger.debug(
            'Module exception raised from %s (name=%s) %s',
            path, name, str(e))

    return module


# URL Indexing Table for returns via parse_url()
# The below accepts and scans for:
#  - schema://
#  - schema://path
#  - schema://path?kwargs
#
VALID_URL_RE = re.compile(
    r'^[\s]*((?P<schema>[^:\s]+):[/\\]+)?((?P<path>[^?]+)'
    r'(\?(?P<kwargs>.+))?)?[\s]*$',
)
VALID_QUERY_RE = re.compile(r'^(?P<path>.*[/\\])(?P<query>[^/\\]+)?$')

# delimiters used to separate values when content is passed in by string.
# This is useful when turning a string into a list
STRING_DELIMITERS = r'[\[\]\;,\s]+'

# String Delimiters without the whitespace
STRING_DELIMITERS_NO_WS = r'[\[\]\;,]+'

# Pre-Escape content since we reference it so much
ESCAPED_PATH_SEPARATOR = re.escape('\\/')
ESCAPED_WIN_PATH_SEPARATOR = re.escape('\\')
ESCAPED_NUX_PATH_SEPARATOR = re.escape('/')

TIDY_WIN_PATH_RE = re.compile(
    r'(^[%s]{2}|[^%s\s][%s]|[\s][%s]{2}])([%s]+)' % (
        ESCAPED_WIN_PATH_SEPARATOR,
        ESCAPED_WIN_PATH_SEPARATOR,
        ESCAPED_WIN_PATH_SEPARATOR,
        ESCAPED_WIN_PATH_SEPARATOR,
        ESCAPED_WIN_PATH_SEPARATOR,
    ),
)
TIDY_WIN_TRIM_RE = re.compile(
    r'^(.+[^:][^%s])[\s%s]*$' % (
        ESCAPED_WIN_PATH_SEPARATOR,
        ESCAPED_WIN_PATH_SEPARATOR,
    ),
)

TIDY_NUX_PATH_RE = re.compile(
    r'([%s])([%s]+)' % (
        ESCAPED_NUX_PATH_SEPARATOR,
        ESCAPED_NUX_PATH_SEPARATOR,
    ),
)

TIDY_NUX_TRIM_RE = re.compile(
    r'([^%s])[\s%s]+$' % (
        ESCAPED_NUX_PATH_SEPARATOR,
        ESCAPED_NUX_PATH_SEPARATOR,
    ),
)

# The handling of custom arguments passed in the URL; we treat any
# argument (which would otherwise appear in the qsd area of our parse_url()
# function differently if they start with a +, - or : value
NOTIFY_CUSTOM_ADD_TOKENS = re.compile(r'^( |\+)(?P<key>.*)\s*')
NOTIFY_CUSTOM_DEL_TOKENS = re.compile(r'^-(?P<key>.*)\s*')
NOTIFY_CUSTOM_COLON_TOKENS = re.compile(r'^:(?P<key>.*)\s*')

# Used for attempting to acquire the schema if the URL can't be parsed.
GET_SCHEMA_RE = re.compile(r'\s*(?P<schema>[a-z0-9]{1,12})://.*$', re.I)

# Used for validating that a provided entry is indeed a schema
# this is slightly different then the GET_SCHEMA_RE above which
# insists the schema is only valid with a :// entry.  this one
# extrapolates the individual entries
URL_DETAILS_RE = re.compile(
    r'\s*(?P<schema>[a-z0-9]{1,12})(://(?P<base>.*))?$', re.I)

# Regular expression based and expanded from:
# http://www.regular-expressions.info/email.html
# Extended to support colon (:) delimiter for parsing names from the URL
# such as:
#   - 'Optional Name':user@example.com
#   - 'Optional Name' <user@example.com>
#
# The expression also parses the general email as well such as:
#   - user@example.com
#   - label+user@example.com
GET_EMAIL_RE = re.compile(
    r'(([\s"\']+)?(?P<name>[^:<\'"]+)?[:<\s\'"]+)?'
    r'(?P<full_email>((?P<label>[^+]+)\+)?'
    r'(?P<email>(?P<userid>[a-z0-9_!#$%&*/=?%`{|}~^-]+'
    r'(?:\.[a-z0-9_!#$%&\'*/=?%`{|}~^-]+)'
    r'*)@(?P<domain>('
    r'(?:[a-z0-9](?:[a-z0-9_-]*[a-z0-9])?\.)+'
    r'[a-z0-9](?:[a-z0-9_-]*[a-z0-9]))|'
    r'[a-z0-9][a-z0-9_-]{5,})))'
    r'\s*>?', re.IGNORECASE)

# A simple verification check to make sure the content specified
# rougly conforms to a phone number before we parse it further
IS_PHONE_NO = re.compile(r'^\+?(?P<phone>[0-9\s)(+-]+)\s*$')

# Regular expression used to destinguish between multiple phone numbers
PHONE_NO_DETECTION_RE = re.compile(
    r'\s*([+(\s]*[0-9][0-9()\s-]+[0-9])(?=$|[\s,+(]+[0-9])', re.I)

# A simple verification check to make sure the content specified
# rougly conforms to a ham radio call sign before we parse it further
IS_CALL_SIGN = re.compile(
    r'^(?P<callsign>[a-z0-9]{2,3}[0-9][a-z0-9]{3})'
    r'(?P<ssid>-[a-z0-9]{1,2})?\s*$', re.I)

# Regular expression used to destinguish between multiple ham radio call signs
CALL_SIGN_DETECTION_RE = re.compile(
    r'\s*([a-z0-9]{2,3}[0-9][a-z0-9]{3}(?:-[a-z0-9]{1,2})?)'
    r'(?=$|[\s,]+[a-z0-9]{4,6})', re.I)

# Regular expression used to destinguish between multiple URLs
URL_DETECTION_RE = re.compile(
    r'([a-z0-9]+?:\/\/.*?)(?=$|[\s,]+[a-z0-9]{1,12}?:\/\/)', re.I)

EMAIL_DETECTION_RE = re.compile(
    r'[\s,]*([^@]+@.*?)(?=$|[\s,]+'
    r'(?:[^:<]+?[:<\s]+?)?'
    r'[^@\s,]+@[^\s,]+)',
    re.IGNORECASE)

# Used to prepare our UUID regex matching
UUID4_RE = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}',
    re.IGNORECASE)

# Validate if we're a loadable Python file or not
VALID_PYTHON_FILE_RE = re.compile(r'.+\.py(o|c)?$', re.IGNORECASE)

# validate_regex() utilizes this mapping to track and re-use pre-complied
# regular expressions
REGEX_VALIDATE_LOOKUP = {}


class Singleton(type):
    """
    Our Singleton MetaClass
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        """
        instantiate our singleton meta entry
        """
        if cls not in cls._instances:
            # we have not every built an instance before.  Build one now.
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class TemplateType:
    """
    Defines the different template types we can perform parsing on
    """
    # RAW does nothing at all to the content being parsed
    # data is taken at it's absolute value
    RAW = 'raw'

    # Data is presumed to be of type JSON and is therefore escaped
    # if required to do so (such as single quotes)
    JSON = 'json'


def is_ipaddr(addr, ipv4=True, ipv6=True):
    """
    Validates against IPV4 and IPV6 IP Addresses
    """

    if ipv4:
        # Based on https://stackoverflow.com/questions/5284147/\
        #       validating-ipv4-addresses-with-regexp
        re_ipv4 = re.compile(
            r'^(?P<ip>((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
            r'(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?))$'
        )
        match = re_ipv4.match(addr)
        if match is not None:
            # Return our matched IP
            return match.group('ip')

    if ipv6:
        # Based on https://stackoverflow.com/questions/53497/\
        #              regular-expression-that-matches-valid-ipv6-addresses
        #
        # IPV6 URLs should be enclosed in square brackets when placed on a URL
        #   Source: https://tools.ietf.org/html/rfc2732
        #   - For this reason, they are additionally checked for existance
        re_ipv6 = re.compile(
            r'\[?(?P<ip>(([0-9a-f]{1,4}:){7,7}[0-9a-f]{1,4}|([0-9a-f]{1,4}:)'
            r'{1,7}:|([0-9a-f]{1,4}:){1,6}:[0-9a-f]{1,4}|([0-9a-f]{1,4}:){1,5}'
            r'(:[0-9a-f]{1,4}){1,2}|([0-9a-f]{1,4}:){1,4}'
            r'(:[0-9a-f]{1,4}){1,3}|([0-9a-f]{1,4}:){1,3}'
            r'(:[0-9a-f]{1,4}){1,4}|([0-9a-f]{1,4}:){1,2}'
            r'(:[0-9a-f]{1,4}){1,5}|[0-9a-f]{1,4}:'
            r'((:[0-9a-f]{1,4}){1,6})|:((:[0-9a-f]{1,4}){1,7}|:)|'
            r'fe80:(:[0-9a-f]{0,4}){0,4}%[0-9a-z]{1,}|::'
            r'(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]'
            r'|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|'
            r'1{0,1}[0-9]){0,1}[0-9])|([0-9a-f]{1,4}:){1,4}:((25[0-5]|'
            r'(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|'
            r'1{0,1}[0-9]){0,1}[0-9])))\]?', re.I,
        )

        match = re_ipv6.match(addr)
        if match is not None:
            # Return our matched IP between square brackets since that is
            # required for URL formatting as per RFC 2732.
            return '[{}]'.format(match.group('ip'))

    # There was no match
    return False


def is_hostname(hostname, ipv4=True, ipv6=True, underscore=True):
    """
    Validate hostname
    """
    # The entire hostname, including the delimiting dots, has a maximum of 253
    # ASCII characters.
    if len(hostname) > 253 or len(hostname) == 0:
        return False

    # Strip trailing period on hostname (if one exists)
    if hostname[-1] == ".":
        hostname = hostname[:-1]

    # Split our hostname up
    labels = hostname.split(".")

    # ipv4 check
    if len(labels) == 4 and re.match(r'[0-9.]+', hostname):
        return is_ipaddr(hostname, ipv4=ipv4, ipv6=False)

    # - RFC 1123 permits hostname labels to start with digits
    #     - digit must be followed by alpha/numeric so we don't end up
    #       processing IP addresses here
    # - Hostnames can ony be comprised of alpha-numeric characters and the
    #   hyphen (-) character.
    # - Hostnames can not start with the hyphen (-) character.
    # - as a workaround for https://github.com/docker/compose/issues/229 to
    #   being able to address services in other stacks, we also allow
    #   underscores in hostnames (if flag is set accordingly)
    # - labels can not exceed 63 characters
    # - allow single character alpha characters
    allowed = re.compile(
        r'^([a-z0-9][a-z0-9_-]{1,62}|[a-z_-])(?<![_-])$' if underscore else
        r'^([a-z0-9][a-z0-9-]{1,62}|[a-z-])(?<!-)$',
        re.IGNORECASE,
    )

    if not all(allowed.match(x) for x in labels):
        return is_ipaddr(hostname, ipv4=ipv4, ipv6=ipv6)

    return hostname


def is_uuid(uuid):
    """Determine if the specified entry is uuid v4 string

    Args:
        address (str): The string you want to check.

    Returns:
        bool: Returns False if the specified element is not a uuid otherwise
              it returns True
    """

    try:
        match = UUID4_RE.match(uuid)

    except TypeError:
        # not parseable content
        return False

    return True if match else False


def is_phone_no(phone, min_len=10):
    """Determine if the specified entry is a phone number

    Args:
        phone (str): The string you want to check.
        min_len (int): Defines the smallest expected length of the phone
                       before it's to be considered invalid. By default
                       the phone number can't be any larger then 14

    Returns:
        bool: Returns False if the address specified is not a phone number
              and a dictionary of the parsed phone number if it is as:
                {
                    'country': '1',
                    'area': '800',
                    'line': '1234567',
                    'full': '18001234567',
                    'pretty': '+1 800-123-4567',
                }

        Non conventional numbers such as 411 would look like provided that
        `min_len` is set to at least a 3:
                {
                    'country': '',
                    'area': '',
                    'line': '411',
                    'full': '411',
                    'pretty': '411',
                }

    """

    try:
        if not IS_PHONE_NO.match(phone):
            # not parseable content as it does not even conform closely to a
            # phone number)
            return False

    except TypeError:
        return False

    # Tidy phone number up first
    phone = re.sub(r'[^\d]+', '', phone)
    if len(phone) > 14 or len(phone) < min_len:
        # Invalid phone number
        return False

    # Full phone number without any markup is as is now
    full = phone

    # Break apart our phone number
    line = phone[-7:]
    phone = phone[:len(phone) - 7] if len(phone) > 7 else ''

    # the area code (if present)
    area = phone[-3:] if phone else ''

    # The country code is the leftovers
    country = phone[:len(phone) - 3] if len(phone) > 3 else ''

    # Prepare a nicely (consistently) formatted phone number
    pretty = ''

    if country:
        # The leftover is the country code
        pretty += '+{} '.format(country)

    if area:
        pretty += '{}-'.format(area)

    if len(line) >= 7:
        pretty += '{}-{}'.format(line[:3], line[3:])

    else:
        pretty += line

    return {
        # The line code (last 7 digits)
        'line': line,
        # Area code
        'area': area,
        # The country code (if identified)
        'country': country,

        # A nicely formatted phone no
        'pretty': pretty,

        # All digits in-line
        'full': full,
    }


def is_call_sign(callsign):
    """Determine if the specified entry is a ham radio call sign

    Args:
        callsign (str): The string you want to check.

    Returns:
        bool: Returns False if the address specified is not a phone number
    """

    try:
        result = IS_CALL_SIGN.match(callsign)
        if not result:
            # not parseable content as it does not even conform closely to a
            # callsign
            return False

    except TypeError:
        # not parseable content
        return False

    ssid = result.group('ssid')
    return {
        # always treat call signs as uppercase content
        'callsign': result.group('callsign').upper(),
        # Prevent the storing of the None keyword in the event the SSID was
        # not detected
        'ssid': ssid if ssid else '',
    }


def is_email(address):
    """Determine if the specified entry is an email address

    Args:
        address (str): The string you want to check.

    Returns:
        bool: Returns False if the address specified is not an email address
              and a dictionary of the parsed email if it is as:
                {
                    'name': 'Parse Name'
                    'email': 'user@domain.com'
                    'full_email': 'label+user@domain.com'
                    'label': 'label'
                    'user': 'user',
                    'domain': 'domain.com'
                }

    """

    try:
        match = GET_EMAIL_RE.match(address)

    except TypeError:
        # not parseable content
        return False

    if match:
        return {
            # The name parsed from the URL (if one exists)
            'name': '' if match.group('name') is None
            else match.group('name').strip(),
            # The email address
            'email': match.group('email'),
            # The full email address (includes label if specified)
            'full_email': match.group('full_email'),
            # The label (if specified) e.g: label+user@example.com
            'label': '' if match.group('label') is None
            else match.group('label').strip(),
            # The user (which does not include the label) from the email
            # parsed.
            'user': match.group('userid'),
            # The domain associated with the email address
            'domain': match.group('domain'),
        }

    return False


def tidy_path(path):
    """take a filename and or directory and attempts to tidy it up by removing
    trailing slashes and correcting any formatting issues.

    For example: ////absolute//path// becomes:
        /absolute/path

    """
    # Windows
    path = TIDY_WIN_PATH_RE.sub('\\1', path.strip())
    # Linux
    path = TIDY_NUX_PATH_RE.sub('\\1', path)

    # Windows Based (final) Trim
    path = expanduser(TIDY_WIN_TRIM_RE.sub('\\1', path))
    return path


def parse_qsd(qs, simple=False, plus_to_space=False):
    """
    Query String Dictionary Builder

    A custom implimentation of the parse_qsl() function already provided
    by Python.  This function is slightly more light weight and gives us
    more control over parsing out arguments such as the plus/+ symbol
    at the head of a key/value pair.

    qs should be a query string part made up as part of the URL such as
       a=1&c=2&d=

        a=1 gets interpreted as { 'a': '1' }
        a=  gets interpreted as { 'a': '' }
        a   gets interpreted as { 'a': '' }


    This function returns a result object that fits with the apprise
    expected parameters (populating the 'qsd' portion of the dictionary

    if simple is set to true, then a ONE dictionary is returned and is not
    sub-parsed for additional elements

    plus_to_space will cause all `+` references to become a space as
    per normal URL Encoded defininition. Normal URL parsing applies
    this, but `+` is very actively used character with passwords,
    api keys, tokens, etc.  So Apprise does not do this by default.
    """

    # Our return result set:
    result = {
        # The arguments passed in (the parsed query). This is in a dictionary
        # of {'key': 'val', etc }.  Keys are all made lowercase before storing
        # to simplify access to them.
        'qsd': {},

        # Detected Entries that start with + or - are additionally stored in
        # these values (un-touched).  The :,+,- however are stripped from their
        # name before they are stored here.
        'qsd+': {},
        'qsd-': {},
        'qsd:': {},
    } if not simple else {'qsd': {}}

    pairs = [s2 for s1 in qs.split('&') for s2 in s1.split(';')]
    for name_value in pairs:
        nv = name_value.split('=', 1)
        # Handle case of a control-name with no equal sign
        if len(nv) != 2:
            nv.append('')

        # Apprise keys can start with a + symbol; so we need to skip over
        # the very first entry
        key = '{}{}'.format(
            '' if len(nv[0]) == 0 else nv[0][0],
            '' if len(nv[0]) <= 1 else nv[0][1:].replace('+', ' '),
        )

        key = unquote(key)
        key = '' if not key else key

        val = nv[1].replace('+', ' ') if plus_to_space else nv[1]
        val = unquote(val)
        val = '' if not val else val.strip()

        # Always Query String Dictionary (qsd) for every entry we have
        # content is always made lowercase for easy indexing
        result['qsd'][key.lower().strip()] = val

        if simple:
            # move along
            continue

        # Check for tokens that start with a addition/plus symbol (+)
        k = NOTIFY_CUSTOM_ADD_TOKENS.match(key)
        if k is not None:
            # Store content 'as-is'
            result['qsd+'][k.group('key')] = val

        # Check for tokens that start with a subtraction/hyphen symbol (-)
        k = NOTIFY_CUSTOM_DEL_TOKENS.match(key)
        if k is not None:
            # Store content 'as-is'
            result['qsd-'][k.group('key')] = val

        # Check for tokens that start with a colon symbol (:)
        k = NOTIFY_CUSTOM_COLON_TOKENS.match(key)
        if k is not None:
            # Store content 'as-is'
            result['qsd:'][k.group('key')] = val

    return result


def parse_url(url, default_schema='http', verify_host=True, strict_port=False,
              simple=False, plus_to_space=False):
    """A function that greatly simplifies the parsing of a url
    specified by the end user.

     Valid syntaxes are:
        <schema>://<user>@<host>:<port>/<path>
        <schema>://<user>:<passwd>@<host>:<port>/<path>
        <schema>://<host>:<port>/<path>
        <schema>://<host>/<path>
        <schema>://<host>
        <host>

     Argument parsing is also supported:
        <schema>://<user>@<host>:<port>/<path>?key1=val&key2=val2
        <schema>://<user>:<passwd>@<host>:<port>/<path>?key1=val&key2=val2
        <schema>://<host>:<port>/<path>?key1=val&key2=val2
        <schema>://<host>/<path>?key1=val&key2=val2
        <schema>://<host>?key1=val&key2=val2

     The function returns a simple dictionary with all of
     the parsed content within it and returns 'None' if the
     content could not be extracted.

     The output of 'http://hostname' would look like:
        {
          'schema': 'http',
          'url': 'http://hostname',
          'host': 'hostname',

          'user': None,
          'password': None,
          'port': None,
          'fullpath': None,
          'path': None,
          'query': None,

          'qsd': {},

          'qsd+': {},
          'qsd-': {},
          'qsd:': {}
        }

     The simple switch cleans the dictionary response to only include the
     fields that were detected.

     The output of 'http://hostname' with the simple flag set would look like:
        {
          'schema': 'http',
          'url': 'http://hostname',
          'host': 'hostname',
        }

     If the URL can't be parsed then None is returned

    """

    if not isinstance(url, str):
        # Simple error checking
        return None

    # Default Results
    result = {
        # The username (if specified)
        'user': None,
        # The password (if specified)
        'password': None,
        # The port (if specified)
        'port': None,
        # The hostname
        'host': '',
        # The full path (query + path)
        'fullpath': None,
        # The path
        'path': None,
        # The query
        'query': None,
        # The schema
        'schema': None,
        # The schema
        'url': None,
        # The arguments passed in (the parsed query). This is in a dictionary
        # of {'key': 'val', etc }.  Keys are all made lowercase before storing
        # to simplify access to them.
        # qsd = Query String Dictionary
        'qsd': {},

        # Detected Entries that start with +, - or : are additionally stored in
        # these values (un-touched).  The +, -, and : however are stripped
        # from their name before they are stored here.
        'qsd+': {},
        'qsd-': {},
        'qsd:': {},
    } if not simple else {}

    qsdata = ''
    match = VALID_URL_RE.search(url)
    if match:
        # Extract basic results (with schema present)
        result['schema'] = match.group('schema').lower().strip() \
            if match.group('schema') else default_schema
        host = match.group('path').strip() \
            if match.group('path') else ''
        qsdata = match.group('kwargs').strip() \
            if match.group('kwargs') else None

    else:
        # Could not extract basic content from the URL
        return None

    # Parse Query Arugments ?val=key&key=val
    # while ensuring that all keys are lowercase
    if qsdata:
        result.update(parse_qsd(
            qsdata, simple=simple, plus_to_space=plus_to_space))

    # Now do a proper extraction of data; http:// is just substitued in place
    # to allow urlparse() to function as expected, we'll swap this back to the
    # expected schema after.
    parsed = urlparse('http://%s' % host)

    # Parse results
    result['host'] = parsed[1].strip()
    result['fullpath'] = quote(unquote(tidy_path(parsed[2].strip())))

    try:
        # Handle trailing slashes removed by tidy_path
        if result['fullpath'][-1] not in ('/', '\\') and \
           url[-1] in ('/', '\\'):
            result['fullpath'] += url.strip()[-1]

    except IndexError:
        # No problem, there simply isn't any returned results
        # and therefore, no trailing slash
        pass

    if not result['fullpath']:
        if not simple:
            # Default
            result['fullpath'] = None
        else:
            # Remove entry
            del result['fullpath']

    else:
        # Using full path, extract query from path
        match = VALID_QUERY_RE.search(result['fullpath'])
        result['path'] = match.group('path')
        result['query'] = match.group('query')
        if not result['query']:
            if not simple:
                result['query'] = None
            else:
                del result['query']

    try:
        (result['user'], result['host']) = \
            re.split(r'[@]+', result['host'])[:2]

    except ValueError:
        # no problem then, host only exists
        # and it's already assigned
        pass

    if result.get('user') is not None:
        try:
            (result['user'], result['password']) = \
                re.split(r'[:]+', result['user'])[:2]

        except ValueError:
            # no problem then, user only exists
            # and it's already assigned
            pass

    # Port Parsing
    pmatch = re.search(
        r'^(?P<host>(\[[0-9a-f:]+\]|[^:]+)):(?P<port>[^:]*)$',
        result['host'])

    if pmatch:
        # Separate our port from our hostname (if port is detected)
        result['host'] = pmatch.group('host')
        try:
            # If we're dealing with an integer, go ahead and convert it
            # otherwise return an 'x' which will raise a ValueError
            #
            # This small extra check allows us to treat floats/doubles
            # as strings. Hence a value like '4.2' won't be converted to a 4
            # (and the .2 lost)
            result['port'] = int(
                pmatch.group('port')
                if re.search(r'[0-9]', pmatch.group('port')) else 'x')

        except ValueError:
            if verify_host:
                # Invalid Host Specified
                return None

    # Acquire our port (if defined)
    _port = result.get('port')

    if verify_host:
        # Verify and Validate our hostname
        result['host'] = is_hostname(result['host'])
        if not result['host']:
            # Nothing more we can do without a hostname; give the user
            # some indication as to what went wrong
            return None

        # Max port is 65535 and min is 1
        if isinstance(_port, int) and not ((
            not strict_port or (
                strict_port and _port > 0 and _port <= 65535))):

            # An invalid port was specified
            return None

    elif pmatch and not isinstance(_port, int):
        if strict_port:
            # Store port
            result['port'] = pmatch.group('port').strip()

        else:
            # Fall back
            result['port'] = None
            result['host'] = '{}:{}'.format(
                pmatch.group('host'), pmatch.group('port'))

    # Re-assemble cleaned up version of the url
    result['url'] = '%s://' % result['schema']
    if isinstance(result.get('user'), str):
        result['url'] += result['user']

        if isinstance(result.get('password'), str):
            result['url'] += ':%s@' % result['password']

        else:
            result['url'] += '@'
    result['url'] += result['host']

    if result.get('port') is not None:
        try:
            result['url'] += ':%d' % result['port']

        except TypeError:
            result['url'] += ':%s' % result['port']

    elif 'port' in result and simple:
        # Eliminate empty fields
        del result['port']

    if result.get('fullpath'):
        result['url'] += result['fullpath']

    if simple and not result['host']:
        # simple mode does not carry over empty host names
        del result['host']

    return result


def parse_bool(arg, default=False):
    """
    Support string based boolean settings.

    If the content could not be parsed, then the default is returned.
    """

    if isinstance(arg, str):
        # no = no - False
        # of = short for off - False
        # 0  = int for False
        # fa = short for False - False
        # f  = short for False - False
        # n  = short for No or Never - False
        # ne  = short for Never - False
        # di  = short for Disable(d) - False
        # de  = short for Deny - False
        if arg.lower()[0:2] in (
                'de', 'di', 'ne', 'f', 'n', 'no', 'of', '0', 'fa'):
            return False
        # ye = yes - True
        # on = short for off - True
        # 1  = int for True
        # tr = short for True - True
        # t  = short for True - True
        # al = short for Always (and Allow) - True
        # en  = short for Enable(d) - True
        elif arg.lower()[0:2] in (
                'en', 'al', 't', 'y', 'ye', 'on', '1', 'tr'):
            return True
        # otherwise
        return default

    # Handle other types
    return bool(arg)


def parse_phone_no(*args, store_unparseable=True, **kwargs):
    """
    Takes a string containing phone numbers separated by comma's and/or spaces
    and returns a list.
    """

    result = []
    for arg in args:
        if isinstance(arg, str) and arg:
            _result = PHONE_NO_DETECTION_RE.findall(arg)
            if _result:
                result += _result

            elif not _result and store_unparseable:
                # we had content passed into us that was lost because it was
                # so poorly formatted that it didn't even come close to
                # meeting the regular expression we defined. We intentially
                # keep it as part of our result set so that parsing done
                # at a higher level can at least report this to the end user
                # and hopefully give them some indication as to what they
                # may have done wrong.
                result += \
                    [x for x in filter(bool, re.split(STRING_DELIMITERS, arg))]

        elif isinstance(arg, (set, list, tuple)):
            # Use recursion to handle the list of phone numbers
            result += parse_phone_no(
                *arg, store_unparseable=store_unparseable)

    return result


def parse_call_sign(*args, store_unparseable=True, **kwargs):
    """
    Takes a string containing ham radio call signs separated by
    comma and/or spacesand returns a list.
    """

    result = []
    for arg in args:
        if isinstance(arg, str) and arg:
            _result = CALL_SIGN_DETECTION_RE.findall(arg)
            if _result:
                result += _result

            elif not _result and store_unparseable:
                # we had content passed into us that was lost because it was
                # so poorly formatted that it didn't even come close to
                # meeting the regular expression we defined. We intentially
                # keep it as part of our result set so that parsing done
                # at a higher level can at least report this to the end user
                # and hopefully give them some indication as to what they
                # may have done wrong.
                result += \
                    [x for x in filter(bool, re.split(STRING_DELIMITERS, arg))]

        elif isinstance(arg, (set, list, tuple)):
            # Use recursion to handle the list of call signs
            result += parse_call_sign(
                *arg, store_unparseable=store_unparseable)

    return result


def parse_emails(*args, store_unparseable=True, **kwargs):
    """
    Takes a string containing emails separated by comma's and/or spaces and
    returns a list.
    """

    result = []
    for arg in args:
        if isinstance(arg, str) and arg:
            _result = EMAIL_DETECTION_RE.findall(arg)
            if _result:
                result += _result

            elif not _result and store_unparseable:
                # we had content passed into us that was lost because it was
                # so poorly formatted that it didn't even come close to
                # meeting the regular expression we defined. We intentially
                # keep it as part of our result set so that parsing done
                # at a higher level can at least report this to the end user
                # and hopefully give them some indication as to what they
                # may have done wrong.
                result += \
                    [x for x in filter(bool, re.split(STRING_DELIMITERS, arg))]

        elif isinstance(arg, (set, list, tuple)):
            # Use recursion to handle the list of Emails
            result += parse_emails(*arg, store_unparseable=store_unparseable)

    return result


def parse_urls(*args, store_unparseable=True, **kwargs):
    """
    Takes a string containing URLs separated by comma's and/or spaces and
    returns a list.
    """

    result = []
    for arg in args:
        if isinstance(arg, str) and arg:
            _result = URL_DETECTION_RE.findall(arg)
            if _result:
                result += _result

            elif not _result and store_unparseable:
                # we had content passed into us that was lost because it was
                # so poorly formatted that it didn't even come close to
                # meeting the regular expression we defined. We intentially
                # keep it as part of our result set so that parsing done
                # at a higher level can at least report this to the end user
                # and hopefully give them some indication as to what they
                # may have done wrong.
                result += \
                    [x for x in filter(bool, re.split(STRING_DELIMITERS, arg))]

        elif isinstance(arg, (set, list, tuple)):
            # Use recursion to handle the list of URLs
            result += parse_urls(*arg, store_unparseable=store_unparseable)

    return result


def url_assembly(**kwargs):
    """
    This function reverses the parse_url() function by taking in the provided
    result set and re-assembling a URL

    """
    # Determine Authentication
    auth = ''
    if kwargs.get('user') is not None and \
            kwargs.get('password') is not None:

        auth = '{user}:{password}@'.format(
            user=quote(kwargs.get('user'), safe=''),
            password=quote(kwargs.get('password'), safe=''),
        )

    elif kwargs.get('user') is not None:
        auth = '{user}@'.format(
            user=quote(kwargs.get('user'), safe=''),
        )

    return '{schema}://{auth}{hostname}{port}{fullpath}{params}'.format(
        schema='' if not kwargs.get('schema') else kwargs.get('schema'),
        auth=auth,
        # never encode hostname since we're expecting it to be a valid one
        hostname='' if not kwargs.get('host') else kwargs.get('host', ''),
        port='' if not kwargs.get('port')
        else ':{}'.format(kwargs.get('port')),
        fullpath=quote(kwargs.get('fullpath', ''), safe='/'),
        params='' if not kwargs.get('qsd')
        else '?{}'.format(urlencode(kwargs.get('qsd'))),
    )


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
    return _urlencode(
        _query, doseq=doseq, safe=safe, encoding=encoding,
        errors=errors)


def parse_list(*args, cast=None, allow_whitespace=True):
    """
    Take a string list and break it into a delimited
    list of arguments. This funciton also supports
    the processing of a list of delmited strings and will
    always return a unique set of arguments. Duplicates are
    always combined in the final results.

    You can append as many items to the argument listing for
    parsing.

    Hence: parse_list('.mkv, .iso, .avi') becomes:
        ['.mkv', '.iso', '.avi']

    Hence: parse_list('.mkv, .iso, .avi', ['.avi', '.mp4']) becomes:
        ['.mkv', '.iso', '.avi', '.mp4']

    The parsing is very forgiving and accepts spaces, slashes, commas
    semicolons, and pipes as delimiters
    """

    result = []
    for arg in args:
        if not isinstance(arg, (str, set, list, bool, tuple)) and arg and cast:
            arg = cast(arg)

        if isinstance(arg, str):
            result += re.split(
                STRING_DELIMITERS if allow_whitespace
                else STRING_DELIMITERS_NO_WS, arg)

        elif isinstance(arg, (set, list, tuple)):
            result += parse_list(*arg, allow_whitespace=allow_whitespace)

    #
    # filter() eliminates any empty entries
    #
    # Since Python v3 returns a filter (iterator) whereas Python v2 returned
    # a list, we need to change it into a list object to remain compatible with
    # both distribution types.
    return sorted([x for x in filter(bool, list(set(result)))]) \
        if allow_whitespace else sorted(
            [x.strip() for x in filter(bool, list(set(result))) if x.strip()])


def is_exclusive_match(logic, data, match_all=common.MATCH_ALL_TAG,
                       match_always=common.MATCH_ALWAYS_TAG):
    """

    The data variable should always be a set of strings that the logic can be
    compared against. It should be a set.  If it isn't already, then it will
    be converted as such. These identify the tags themselves.

    Our logic should be a list as well:
      - top level entries are treated as an 'or'
      - second level (or more) entries are treated as 'and'

      examples:
        logic="tagA, tagB"                = tagA or tagB
        logic=['tagA', 'tagB']            = tagA or tagB
        logic=[('tagA', 'tagC'), 'tagB']  = (tagA and tagC) or tagB
        logic=[('tagB', 'tagC')]          = tagB and tagC

    If `match_always` is not set to None, then its value is added as an 'or'
    to all specified logic searches.
    """

    if isinstance(logic, str):
        # Update our logic to support our delimiters
        logic = set(parse_list(logic))

    if not logic:
        # If there is no logic to apply then we're done early; we only match
        # if there is also no data to match against
        return not data

    if not isinstance(logic, (list, tuple, set)):
        # garbage input
        return False

    if match_always:
        # Add our match_always to our logic searching if secified
        logic = chain(logic, [match_always])

    # Track what we match against; but by default we do not match
    # against anything
    matched = False

    # Every entry here will be or'ed with the next
    for entry in logic:
        if not isinstance(entry, (str, list, tuple, set)):
            # Garbage entry in our logic found
            return False

        # treat these entries as though all elements found
        # must exist in the notification service
        entries = set(parse_list(entry))
        if not entries:
            # We got a bogus set of tags to parse
            # If there is no logic to apply then we're done early; we only
            # match if there is also no data to match against
            return not data

        if len(entries.intersection(data.union({match_all}))) == len(entries):
            # our set contains all of the entries found
            # in our notification data set
            matched = True
            break

        # else: keep looking

    # Return True if we matched against our logic (or simply none was
    # specified).
    return matched


def validate_regex(value, regex=r'[^\s]+', flags=re.I, strip=True, fmt=None):
    """
    A lot of the tokens, secrets, api keys, etc all have some regular
    expression validation they support.  This hashes the regex after it's
    compiled and returns it's content if matched, otherwise it returns None.

    This function greatly increases performance as it prevents apprise modules
    from having to pre-compile all of their regular expressions.

        value is the element being tested
        regex is the regular expression to be compiled and tested. By default
         we extract the first chunk of code while eliminating surrounding
         whitespace (if present)

        flags is the regular expression flags that should be applied
        format is used to alter the response format if the regular
         expression matches. You identify your format using {tags}.
         Effectively nesting your ID's between {}. Consider a regex of:
          '(?P<year>[0-9]{2})[0-9]+(?P<value>[A-Z])'
        to which you could set your format up as '{value}-{year}'. This
        would substitute the matched groups and format a response.
    """

    if flags:
        # Regex String -> Flag Lookup Map
        _map = {
            # Ignore Case
            'i': re.I,
            # Multi Line
            'm': re.M,
            # Dot Matches All
            's': re.S,
            # Locale Dependant
            'L': re.L,
            # Unicode Matching
            'u': re.U,
            # Verbose
            'x': re.X,
        }

        if isinstance(flags, str):
            # Convert a string of regular expression flags into their
            # respected integer (expected) Python values and perform
            # a bit-wise or on each match found:
            flags = reduce(
                lambda x, y: x | y,
                [0] + [_map[f] for f in flags if f in _map])

    else:
        # Handles None/False/'' cases
        flags = 0

    # A key is used to store our compiled regular expression
    key = '{}{}'.format(regex, flags)

    if key not in REGEX_VALIDATE_LOOKUP:
        REGEX_VALIDATE_LOOKUP[key] = re.compile(regex, flags)

    # Perform our lookup usig our pre-compiled result
    try:
        result = REGEX_VALIDATE_LOOKUP[key].match(value)
        if not result:
            # let outer exception handle this
            raise TypeError

        if fmt:
            # Map our format back to our response
            value = fmt.format(**result.groupdict())

    except (TypeError, AttributeError):
        return None

    # Return our response
    return value.strip() if strip else value


def cwe312_word(word, force=False, advanced=True, threshold=5):
    """
    This function was written to help mask secure/private information that may
    or may not be found within Apprise. The idea is to provide a presentable
    word response that the user who prepared it would understand, yet not
    reveal any private information for any potential intruder

    For more detail see CWE-312 @
       https://cwe.mitre.org/data/definitions/312.html

    The `force` is an optional argument used to keep the string formatting
    consistent and in one place. If set, the content passed in is presumed
    to be containing secret information and will be updated accordingly.

    If advanced is set to `True` then content is additionally checked for
    upper/lower/ascii/numerical variances. If an obscurity threshold is
    reached, then content is considered secret
    """

    class Variance:
        """
        A Simple List of Possible Character Variances
        """
        # An Upper Case Character (ABCDEF... etc)
        ALPHA_UPPER = '+'
        # An Lower Case Character (abcdef... etc)
        ALPHA_LOWER = '-'
        # A Special Character ($%^;... etc)
        SPECIAL = 's'
        # A Numerical Character (1234... etc)
        NUMERIC = 'n'

    if not (isinstance(word, str) and word.strip()):
        # not a password if it's not something we even support
        return word

    # Formatting
    word = word.strip()
    if force:
        # We're forcing the representation to be a secret
        # We do this for consistency
        return '{}...{}'.format(word[0:1], word[-1:])

    elif len(word) > 1 and \
            not is_hostname(word, ipv4=True, ipv6=True, underscore=False):
        # Verify if it is a hostname or not
        return '{}...{}'.format(word[0:1], word[-1:])

    elif len(word) >= 16:
        # an IP will be 15 characters so we don't want to use a smaller
        # value then 16 (e.g 101.102.103.104)
        # we can assume very long words are passwords otherwise
        return '{}...{}'.format(word[0:1], word[-1:])

    if advanced:
        #
        # Mark word a secret based on it's obscurity
        #

        # Our variances will increase depending on these variables:
        last_variance = None
        obscurity = 0

        for c in word:
            # Detect our variance
            if c.isdigit():
                variance = Variance.NUMERIC
            elif c.isalpha() and c.isupper():
                variance = Variance.ALPHA_UPPER
            elif c.isalpha() and c.islower():
                variance = Variance.ALPHA_LOWER
            else:
                variance = Variance.SPECIAL

            if last_variance != variance or variance == Variance.SPECIAL:
                obscurity += 1

                if obscurity >= threshold:
                    return '{}...{}'.format(word[0:1], word[-1:])

            last_variance = variance

    # Otherwise we're good; return our word
    return word


def cwe312_url(url):
    """
    This function was written to help mask secure/private information that may
    or may not be found on an Apprise URL. The idea is to not disrupt the
    structure of the previous URL too much, yet still protect the users
    private information from being logged directly to screen.

    For more detail see CWE-312 @
       https://cwe.mitre.org/data/definitions/312.html

    For example, consider the URL: http://user:password@localhost/

    When passed into this function, the return value would be:
      http://user:****@localhost/

    Since apprise allows you to put private information everywhere in it's
    custom URLs, it uses this function to manipulate the content before
    returning to any kind of logger.

    The idea is that the URL can still be interpreted by the person who
    constructed them, but not to an intruder.
    """
    # Parse our URL
    results = parse_url(url)
    if not results:
        # Nothing was returned (invalid data was fed in); return our
        # information as it was fed to us (without changing it)
        return url

    # Update our URL with values
    results['password'] = cwe312_word(results['password'], force=True)
    if not results['schema'].startswith('http'):
        results['user'] = cwe312_word(results['user'])
        results['host'] = cwe312_word(results['host'])

    else:
        results['host'] = cwe312_word(results['host'], advanced=False)
        results['user'] = cwe312_word(results['user'], advanced=False)

    # Apply our full path scan in all cases
    results['fullpath'] = '/' + \
        '/'.join([cwe312_word(x)
                 for x in re.split(
                     r'[\\/]+',
                     results['fullpath'].lstrip('/'))]) \
        if results['fullpath'] else ''

    #
    # Now re-assemble our URL for display purposes
    #

    # Determine Authentication
    auth = ''
    if results['user'] and results['password']:
        auth = '{user}:{password}@'.format(
            user=results['user'],
            password=results['password'],
        )
    elif results['user']:
        auth = '{user}@'.format(
            user=results['user'],
        )

    params = ''
    if results['qsd']:
        params = '?{}'.format(
            "&".join(["{}={}".format(k, cwe312_word(v, force=(
                k in ('password', 'secret', 'pass', 'token', 'key',
                      'id', 'apikey', 'to'))))
                      for k, v in results['qsd'].items()]))

    return '{schema}://{auth}{hostname}{port}{fullpath}{params}'.format(
        schema=results['schema'],
        auth=auth,
        # never encode hostname since we're expecting it to be a valid one
        hostname=results['host'],
        port='' if not results['port'] else ':{}'.format(results['port']),
        fullpath=results['fullpath'] if results['fullpath'] else '',
        params=params,
    )


@contextlib.contextmanager
def environ(*remove, **update):
    """
    Temporarily updates the ``os.environ`` dictionary in-place.

    The ``os.environ`` dictionary is updated in-place so that the modification
    is sure to work in all situations.

    :param remove: Environment variable(s) to remove.
    :param update: Dictionary of environment variables and values to
                   add/update.
    """

    # Create a backup of our environment for restoration purposes
    env_orig = os.environ.copy()
    loc_orig = locale.getlocale()
    try:
        os.environ.update(update)
        [os.environ.pop(k, None) for k in remove]
        yield

    finally:
        # Restore our snapshot
        os.environ = env_orig.copy()
        try:
            # Restore locale
            locale.setlocale(locale.LC_ALL, loc_orig)

        except locale.Error:
            # Thrown in py3.6
            pass


def apply_template(template, app_mode=TemplateType.RAW, **kwargs):
    """
    Takes a template in a str format and applies all of the keywords
    and their values to it.

    The app$mode is used to dictact any pre-processing that needs to take place
    to the escaped string prior to it being placed.  The idea here is for
    elements to be placed in a JSON response for example should be escaped
    early in their string format.

    The template must contain keywords wrapped in in double
    squirly braces like {{keyword}}.  These are matched to the respected
    kwargs passed into this function.

    If there is no match found, content is not swapped.

    """

    def _escape_raw(content):
        # No escaping necessary
        return content

    def _escape_json(content):
        # remove surounding quotes
        return json.dumps(content)[1:-1]

    # Our escape function
    fn = _escape_json if app_mode == TemplateType.JSON else _escape_raw

    lookup = [re.escape(x) for x in kwargs.keys()]

    # Compile this into a list
    mask_r = re.compile(
        re.escape('{{') + r'\s*(' + '|'.join(lookup) + r')\s*'
        + re.escape('}}'), re.IGNORECASE)

    # we index 2 characters off the head and 2 characters from the tail
    # to drop the '{{' and '}}' surrounding our match so that we can
    # re-index it back into our list
    return mask_r.sub(lambda x: fn(kwargs[x.group()[2:-2].strip()]), template)


def remove_suffix(value, suffix):
    """
    Removes a suffix from the end of a string.
    """
    return value[:-len(suffix)] if value.endswith(suffix) else value


def dict_full_update(dict1, dict2):
    """
    Takes 2 dictionaries (dict1 and dict2) that contain sub-dictionaries and
    gracefully merges them into dict1.

    This is similar to: dict1.update(dict2) except that internal dictionaries
    are also recursively applied.
    """
    def _merge(dict1, dict2):
        for k in dict2:
            if k in dict1 and isinstance(dict1[k], dict) \
                    and isinstance(dict2[k], dict):
                _merge(dict1[k], dict2[k])
            else:
                dict1[k] = dict2[k]

    _merge(dict1, dict2)
    return
