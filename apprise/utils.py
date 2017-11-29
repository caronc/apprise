# -*- coding: utf-8 -*-
#
# A simple collection of general functions
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
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

from os.path import expanduser

from urlparse import urlparse
from urlparse import parse_qsl
from urllib import quote
from urllib import unquote

import logging
logger = logging.getLogger(__name__)

# URL Indexing Table for returns via parse_url()
VALID_URL_RE = re.compile(r'^[\s]*([^:\s]+):[/\\]*([^?]+)(\?(.+))?[\s]*$')
VALID_HOST_RE = re.compile(r'^[\s]*([^:/\s]+)')
VALID_QUERY_RE = re.compile(r'^(.*[/\\])([^/\\]*)$')

# delimiters used to separate values when content is passed in by string.
# This is useful when turning a string into a list
STRING_DELIMITERS = r'[\[\]\;,\s]+'

# Pre-Escape content since we reference it so much
ESCAPED_PATH_SEPARATOR = re.escape('\\/')
ESCAPED_WIN_PATH_SEPARATOR = re.escape('\\')
ESCAPED_NUX_PATH_SEPARATOR = re.escape('/')

TIDY_WIN_PATH_RE = re.compile(
    '(^[%s]{2}|[^%s\s][%s]|[\s][%s]{2}])([%s]+)' % (
        ESCAPED_WIN_PATH_SEPARATOR,
        ESCAPED_WIN_PATH_SEPARATOR,
        ESCAPED_WIN_PATH_SEPARATOR,
        ESCAPED_WIN_PATH_SEPARATOR,
        ESCAPED_WIN_PATH_SEPARATOR,
    ),
)
TIDY_WIN_TRIM_RE = re.compile(
    '^(.+[^:][^%s])[\s%s]*$' % (
        ESCAPED_WIN_PATH_SEPARATOR,
        ESCAPED_WIN_PATH_SEPARATOR,
    ),
)

TIDY_NUX_PATH_RE = re.compile(
    '([%s])([%s]+)' % (
        ESCAPED_NUX_PATH_SEPARATOR,
        ESCAPED_NUX_PATH_SEPARATOR,
    ),
)

TIDY_NUX_TRIM_RE = re.compile(
    '([^%s])[\s%s]+$' % (
        ESCAPED_NUX_PATH_SEPARATOR,
        ESCAPED_NUX_PATH_SEPARATOR,
    ),
)


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


def parse_url(url, default_schema='http'):
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

    if not isinstance(url, basestring):
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
        # The arguments passed in (the parsed query)
        # This is in a dictionary of {'key': 'val', etc }
        # qsd = Query String Dictionary
        'qsd': {}
    }

    qsdata = ''
    match = VALID_URL_RE.search(url)
    if match:
        # Extract basic results
        result['schema'] = match.group(1).lower().strip()
        host = match.group(2).strip()
        try:
            qsdata = match.group(4).strip()
        except AttributeError:
            # No qsdata
            pass
    else:
        match = VALID_HOST_RE.search(url)
        if not match:
            return None
        result['schema'] = default_schema
        host = match.group(1).strip()

    if not result['schema']:
        result['schema'] = default_schema

    if not host:
        # Invalid Hostname
        return None

    # Now do a proper extraction of data
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

    # Parse Query Arugments ?val=key&key=val
    # while ensureing that all keys are lowercase
    if qsdata:
        result['qsd'] = dict([(k.lower().strip(), v.strip())
                              for k, v in parse_qsl(
            qsdata,
            keep_blank_values=True,
            strict_parsing=False,
        )])

    if not result['fullpath']:
        # Default
        result['fullpath'] = None
    else:
        # Using full path, extract query from path
        match = VALID_QUERY_RE.search(result['fullpath'])
        if match:
            result['path'] = match.group(1)
            result['query'] = match.group(2)
            if not result['path']:
                result['path'] = None
            if not result['query']:
                result['query'] = None
    try:
        (result['user'], result['host']) = \
            re.split('[\s@]+', result['host'])[:2]

    except ValueError:
        # no problem then, host only exists
        # and it's already assigned
        pass

    if result['user'] is not None:
        try:
            (result['user'], result['password']) = \
                re.split('[:\s]+', result['user'])[:2]

        except ValueError:
            # no problem then, user only exists
            # and it's already assigned
            pass

    try:
        (result['host'], result['port']) = \
            re.split('[\s:]+', result['host'])[:2]

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

    # Re-assemble cleaned up version of the url
    result['url'] = '%s://' % result['schema']
    if isinstance(result['user'], basestring):
        result['url'] += result['user']
        if isinstance(result['password'], basestring):
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

    if isinstance(arg, basestring):
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
        if isinstance(arg, basestring):
            result += re.split(STRING_DELIMITERS, arg)

        elif isinstance(arg, (list, tuple)):
            for _arg in arg:
                if isinstance(arg, basestring):
                    result += re.split(STRING_DELIMITERS, arg)
                # A list inside a list? - use recursion
                elif isinstance(_arg, (list, tuple)):
                    result += parse_list(_arg)
                else:
                    # Convert whatever it is to a string and work with it
                    result += parse_list(str(_arg))
        else:
            # Convert whatever it is to a string and work with it
            result += parse_list(str(arg))

    # apply as well as make the list unique by converting it
    # to a set() first. filter() eliminates any empty entries
    return filter(bool, list(set(result)))
