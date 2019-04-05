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
from os.path import expanduser

try:
    # Python 2.7
    from urllib import unquote
    from urllib import quote
    from urlparse import urlparse

except ImportError:
    # Python 3.x
    from urllib.parse import unquote
    from urllib.parse import quote
    from urllib.parse import urlparse

# URL Indexing Table for returns via parse_url()
VALID_URL_RE = re.compile(
    r'^[\s]*(?P<schema>[^:\s]+):[/\\]*(?P<path>[^?]+)'
    r'(\?(?P<kwargs>.+))?[\s]*$',
)
VALID_HOST_RE = re.compile(r'^[\s]*(?P<path>[^?\s]+)(\?(?P<kwargs>.+))?')
VALID_QUERY_RE = re.compile(r'^(?P<path>.*[/\\])(?P<query>[^/\\]*)$')

# delimiters used to separate values when content is passed in by string.
# This is useful when turning a string into a list
STRING_DELIMITERS = r'[\[\]\;,\s]+'

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
# function differently if they start with a + or - value
NOTIFY_CUSTOM_ADD_TOKENS = re.compile(r'^( |\+)(?P<key>.*)\s*')
NOTIFY_CUSTOM_DEL_TOKENS = re.compile(r'^-(?P<key>.*)\s*')

# Used for attempting to acquire the schema if the URL can't be parsed.
GET_SCHEMA_RE = re.compile(r'\s*(?P<schema>[a-z0-9]{2,9})://.*$', re.I)

# Regular expression based and expanded from:
# http://www.regular-expressions.info/email.html
GET_EMAIL_RE = re.compile(
    r"((?P<label>[^+]+)\+)?"
    r"(?P<userid>[a-z0-9$%=_~-]+"
    r"(?:\.[a-z0-9$%+=_~-]+)"
    r"*)@(?P<domain>(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]*"
    r"[a-z0-9]))?",
    re.IGNORECASE,
)


def is_hostname(hostname):
    """
    Validate hostname
    """
    if len(hostname) > 255 or len(hostname) == 0:
        return False

    if hostname[-1] == ".":
        hostname = hostname[:-1]

    allowed = re.compile(r'(?!-)[A-Z\d_-]{1,63}(?<!-)$', re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))


def is_email(address):
    """Determine if the specified entry is an email address

    Args:
        address (str): The string you want to check.

    Returns:
        bool: Returns True if the address specified is an email address
              and False if it isn't.
    """

    try:
        return GET_EMAIL_RE.match(address) is not None
    except TypeError:
        # invalid syntax
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
    path = TIDY_NUX_PATH_RE.sub('\\1', path.strip())

    # Linux Based Trim
    path = TIDY_NUX_TRIM_RE.sub('\\1', path.strip())
    # Windows Based Trim
    path = expanduser(TIDY_WIN_TRIM_RE.sub('\\1', path.strip()))
    return path


def parse_qsd(qs):
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
    """

    # Our return result set:
    result = {
        # The arguments passed in (the parsed query). This is in a dictionary
        # of {'key': 'val', etc }.  Keys are all made lowercase before storing
        # to simplify access to them.
        'qsd': {},

        # Detected Entries that start with + or - are additionally stored in
        # these values (un-touched).  The +/- however are stripped from their
        # name before they are stored here.
        'qsd+': {},
        'qsd-': {},
    }

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

        val = nv[1].replace('+', ' ')
        val = unquote(val)
        val = '' if not val else val.strip()

        # Always Query String Dictionary (qsd) for every entry we have
        # content is always made lowercase for easy indexing
        result['qsd'][key.lower().strip()] = val

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

    return result


def parse_url(url, default_schema='http', verify_host=True):
    """A function that greatly simplifies the parsing of a url
    specified by the end user.

     Valid syntaxes are:
        <schema>://<user>@<host>:<port>/<path>
        <schema>://<user>:<passwd>@<host>:<port>/<path>
        <schema>://<host>:<port>/<path>
        <schema>://<host>/<path>
        <schema>://<host>

     Argument parsing is also supported:
        <schema>://<user>@<host>:<port>/<path>?key1=val&key2=val2
        <schema>://<user>:<passwd>@<host>:<port>/<path>?key1=val&key2=val2
        <schema>://<host>:<port>/<path>?key1=val&key2=val2
        <schema>://<host>/<path>?key1=val&key2=val2
        <schema>://<host>?key1=val&key2=val2

     The function returns a simple dictionary with all of
     the parsed content within it and returns 'None' if the
     content could not be extracted.
    """

    if not isinstance(url, six.string_types):
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
        'host': None,
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

        # Detected Entries that start with + or - are additionally stored in
        # these values (un-touched).  The +/- however are stripped from their
        # name before they are stored here.
        'qsd+': {},
        'qsd-': {},
    }

    qsdata = ''
    match = VALID_URL_RE.search(url)
    if match:
        # Extract basic results
        result['schema'] = match.group('schema').lower().strip()
        host = match.group('path').strip()
        try:
            qsdata = match.group('kwargs').strip()
        except AttributeError:
            # No qsdata
            pass

    else:
        match = VALID_HOST_RE.search(url)
        if not match:
            return None
        result['schema'] = default_schema
        host = match.group('path').strip()
        try:
            qsdata = match.group('kwargs').strip()
        except AttributeError:
            # No qsdata
            pass

    # Parse Query Arugments ?val=key&key=val
    # while ensuring that all keys are lowercase
    if qsdata:
        result.update(parse_qsd(qsdata))

    # Now do a proper extraction of data
    parsed = urlparse('http://%s' % host)

    # Parse results
    result['host'] = parsed[1].strip()

    if not result['host']:
        # Nothing more we can do without a hostname
        return None

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
        # Default
        result['fullpath'] = None

    else:
        # Using full path, extract query from path
        match = VALID_QUERY_RE.search(result['fullpath'])
        if match:
            result['path'] = match.group('path')
            result['query'] = match.group('query')
            if not result['query']:
                result['query'] = None
    try:
        (result['user'], result['host']) = \
            re.split(r'[\s@]+', result['host'])[:2]

    except ValueError:
        # no problem then, host only exists
        # and it's already assigned
        pass

    if result['user'] is not None:
        try:
            (result['user'], result['password']) = \
                re.split(r'[:\s]+', result['user'])[:2]

        except ValueError:
            # no problem then, user only exists
            # and it's already assigned
            pass

    try:
        (result['host'], result['port']) = \
            re.split(r'[\s:]+', result['host'])[:2]

    except ValueError:
        # no problem then, user only exists
        # and it's already assigned
        pass

    if result['port']:
        try:
            result['port'] = int(result['port'])

        except (ValueError, TypeError):
            # Invalid Port Specified
            return None

        if result['port'] == 0:
            result['port'] = None

    if verify_host and not is_hostname(result['host']):
        # Nothing more we can do without a hostname
        return None

    # Re-assemble cleaned up version of the url
    result['url'] = '%s://' % result['schema']
    if isinstance(result['user'], six.string_types):
        result['url'] += result['user']

        if isinstance(result['password'], six.string_types):
            result['url'] += ':%s@' % result['password']

        else:
            result['url'] += '@'
    result['url'] += result['host']

    if result['port']:
        result['url'] += ':%d' % result['port']

    if result['fullpath']:
        result['url'] += result['fullpath']

    return result


def parse_bool(arg, default=False):
    """
    NZBGet uses 'yes' and 'no' as well as other strings such as 'on' or
    'off' etch to handle boolean operations from it's control interface.

    This method can just simplify checks to these variables.

    If the content could not be parsed, then the default is returned.
    """

    if isinstance(arg, six.string_types):
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


def parse_list(*args):
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
        if isinstance(arg, six.string_types):
            result += re.split(STRING_DELIMITERS, arg)

        elif isinstance(arg, (set, list, tuple)):
            result += parse_list(*arg)

        elif arg is None:
            # Ignore
            continue

        else:
            # Convert whatever it is to a string and work with it
            result += parse_list(str(arg))

    #
    # filter() eliminates any empty entries
    #
    # Since Python v3 returns a filter (iterator) where-as Python v2 returned
    # a list, we need to change it into a list object to remain compatible with
    # both distribution types.
    return sorted([x for x in filter(bool, list(set(result)))])


def is_exclusive_match(logic, data):
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
    """

    if logic is None:
        # If there is no logic to apply then we're done early
        return True

    elif isinstance(logic, six.string_types):
        # Update our logic to support our delimiters
        logic = set(parse_list(logic))

    if not isinstance(logic, (list, tuple, set)):
        # garbage input
        return False

    # using the data detected; determine if we'll allow the
    # notification to be sent or not
    matched = (len(logic) == 0)

    # Every entry here will be or'ed with the next
    for entry in logic:
        if not isinstance(entry, (six.string_types, list, tuple, set)):
            # Garbage entry in our logic found
            return False

        # treat these entries as though all elements found
        # must exist in the notification service
        entries = set(parse_list(entry))

        if len(entries.intersection(data)) == len(entries):
            # our set contains all of the entries found
            # in our notification data set
            matched = True
            break

        # else: keep looking

    # Return True if we matched against our logic (or simply none was
    # specified).
    return matched
