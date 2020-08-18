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
import contextlib
import os
from os.path import expanduser
from functools import reduce

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
# Extended to support colon (:) delimiter for parsing names from the URL
# such as:
#   - 'Optional Name':user@example.com
#   - 'Optional Name' <user@example.com>
#
# The expression also parses the general email as well such as:
#   - user@example.com
#   - label+user@example.com
GET_EMAIL_RE = re.compile(
    r'((?P<name>[^:<]+)?[:<\s]+)?'
    r'(?P<full_email>((?P<label>[^+]+)\+)?'
    r'(?P<email>(?P<userid>[a-z0-9$%=_~-]+'
    r'(?:\.[a-z0-9$%+=_~-]+)'
    r'*)@(?P<domain>('
    r'(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+'
    r'[a-z0-9](?:[a-z0-9-]*[a-z0-9]))|'
    r'[a-z0-9][a-z0-9-]{5,})))'
    r'\s*>?', re.IGNORECASE)

# Regular expression used to extract a phone number
GET_PHONE_NO_RE = re.compile(r'^\+?(?P<phone>[0-9\s)(+-]+)\s*$')

# Regular expression used to destinguish between multiple URLs
URL_DETECTION_RE = re.compile(
    r'([a-z0-9]+?:\/\/.*?)(?=$|[\s,]+[a-z0-9]{2,9}?:\/\/)', re.I)

EMAIL_DETECTION_RE = re.compile(
    r'[\s,]*([^@]+@.*?)(?=$|[\s,]+'
    + r'(?:[^:<]+?[:<\s]+?)?'
    r'[^@\s,]+@[^\s,]+)',
    re.IGNORECASE)

# validate_regex() utilizes this mapping to track and re-use pre-complied
# regular expressions
REGEX_VALIDATE_LOOKUP = {}


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


def is_hostname(hostname, ipv4=True, ipv6=True):
    """
    Validate hostname
    """
    # The entire hostname, including the delimiting dots, has a maximum of 253
    # ASCII characters.
    if len(hostname) > 253 or len(hostname) == 0:
        return False

    # Strip trailling period on hostname (if one exists)
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
    # - labels can not exceed 63 characters
    allowed = re.compile(
        r'(?!-)[a-z0-9][a-z0-9-]{1,62}(?<!-)$',
        re.IGNORECASE,
    )

    if not all(allowed.match(x) for x in labels):
        return is_ipaddr(hostname, ipv4=ipv4, ipv6=ipv6)

    return hostname


def is_email(address):
    """Determine if the specified entry is an email address

    Args:
        address (str): The string you want to check.

    Returns:
        bool: Returns True if the address specified is an email address
              and False if it isn't.
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

        # Detected Entries that start with + or - are additionally stored in
        # these values (un-touched).  The +/- however are stripped from their
        # name before they are stored here.
        'qsd+': {},
        'qsd-': {},
    }

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
        result.update(parse_qsd(qsdata))

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
        # Default
        result['fullpath'] = None

    else:
        # Using full path, extract query from path
        match = VALID_QUERY_RE.search(result['fullpath'])
        result['path'] = match.group('path')
        result['query'] = match.group('query')
        if not result['query']:
            result['query'] = None
    try:
        (result['user'], result['host']) = \
            re.split(r'[@]+', result['host'])[:2]

    except ValueError:
        # no problem then, host only exists
        # and it's already assigned
        pass

    if result['user'] is not None:
        try:
            (result['user'], result['password']) = \
                re.split(r'[:]+', result['user'])[:2]

        except ValueError:
            # no problem then, user only exists
            # and it's already assigned
            pass

    # Max port is 65535 so (1,5 digits)
    match = re.search(
        r'^(?P<host>.+):(?P<port>[1-9][0-9]{0,4})$', result['host'])
    if match:
        # Separate our port from our hostname (if port is detected)
        result['host'] = match.group('host')
        result['port'] = int(match.group('port'))

    if verify_host:
        # Verify and Validate our hostname
        result['host'] = is_hostname(result['host'])
        if not result['host']:
            # Nothing more we can do without a hostname; give the user
            # some indication as to what went wrong
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


def parse_emails(*args, **kwargs):
    """
    Takes a string containing URLs separated by comma's and/or spaces and
    returns a list.
    """

    # for Python 2.7 support, store_unparsable is not in the url above
    # as just parse_emails(*args, store_unparseable=True) since it is
    # an invalid syntax.  This is the workaround to be backards compatible:
    store_unparseable = kwargs.get('store_unparseable', True)

    result = []
    for arg in args:
        if isinstance(arg, six.string_types) and arg:
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


def parse_urls(*args, **kwargs):
    """
    Takes a string containing URLs separated by comma's and/or spaces and
    returns a list.
    """

    # for Python 2.7 support, store_unparsable is not in the url above
    # as just parse_urls(*args, store_unparseable=True) since it is
    # an invalid syntax.  This is the workaround to be backards compatible:
    store_unparseable = kwargs.get('store_unparseable', True)

    result = []
    for arg in args:
        if isinstance(arg, six.string_types) and arg:
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

    #
    # filter() eliminates any empty entries
    #
    # Since Python v3 returns a filter (iterator) where-as Python v2 returned
    # a list, we need to change it into a list object to remain compatible with
    # both distribution types.
    return sorted([x for x in filter(bool, list(set(result)))])


def is_exclusive_match(logic, data, match_all='all'):
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

    if isinstance(logic, six.string_types):
        # Update our logic to support our delimiters
        logic = set(parse_list(logic))

    if not logic:
        # If there is no logic to apply then we're done early; we only match
        # if there is also no data to match against
        return not data

    if not isinstance(logic, (list, tuple, set)):
        # garbage input
        return False

    # Track what we match against; but by default we do not match
    # against anything
    matched = False

    # Every entry here will be or'ed with the next
    for entry in logic:
        if not isinstance(entry, (six.string_types, list, tuple, set)):
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

        if isinstance(flags, six.string_types):
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

    try:
        os.environ.update(update)
        [os.environ.pop(k, None) for k in remove]
        yield

    finally:
        # Restore our snapshot
        os.environ = env_orig.copy()
