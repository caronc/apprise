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

from __future__ import print_function
import re
import os
try:
    # Python 2.7
    from urllib import unquote

except ImportError:
    # Python 3.x
    from urllib.parse import unquote

from apprise import utils

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_parse_qsd():
    "utils: parse_qsd() testing """

    result = utils.parse_qsd('a=1&b=&c&d=abcd')
    assert(isinstance(result, dict) is True)
    assert(len(result) == 3)
    assert 'qsd' in result
    assert 'qsd+' in result
    assert 'qsd-' in result

    assert(len(result['qsd']) == 4)
    assert 'a' in result['qsd']
    assert 'b' in result['qsd']
    assert 'c' in result['qsd']
    assert 'd' in result['qsd']

    assert(len(result['qsd-']) == 0)
    assert(len(result['qsd+']) == 0)


def test_parse_url():
    "utils: parse_url() testing """

    result = utils.parse_url('http://hostname')
    assert(result['schema'] == 'http')
    assert(result['host'] == 'hostname')
    assert(result['port'] is None)
    assert(result['user'] is None)
    assert(result['password'] is None)
    assert(result['fullpath'] is None)
    assert(result['path'] is None)
    assert(result['query'] is None)
    assert(result['url'] == 'http://hostname')
    assert(result['qsd'] == {})
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})

    result = utils.parse_url('http://hostname/')
    assert(result['schema'] == 'http')
    assert(result['host'] == 'hostname')
    assert(result['port'] is None)
    assert(result['user'] is None)
    assert(result['password'] is None)
    assert(result['fullpath'] == '/')
    assert(result['path'] == '/')
    assert(result['query'] is None)
    assert(result['url'] == 'http://hostname/')
    assert(result['qsd'] == {})
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})

    result = utils.parse_url('hostname')
    assert(result['schema'] == 'http')
    assert(result['host'] == 'hostname')
    assert(result['port'] is None)
    assert(result['user'] is None)
    assert(result['password'] is None)
    assert(result['fullpath'] is None)
    assert(result['path'] is None)
    assert(result['query'] is None)
    assert(result['url'] == 'http://hostname')
    assert(result['qsd'] == {})
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})

    result = utils.parse_url('http://hostname/?-KeY=Value')
    assert(result['schema'] == 'http')
    assert(result['host'] == 'hostname')
    assert(result['port'] is None)
    assert(result['user'] is None)
    assert(result['password'] is None)
    assert(result['fullpath'] == '/')
    assert(result['path'] == '/')
    assert(result['query'] is None)
    assert(result['url'] == 'http://hostname/')
    assert('-key' in result['qsd'])
    assert(unquote(result['qsd']['-key']) == 'Value')
    assert('KeY' in result['qsd-'])
    assert(unquote(result['qsd-']['KeY']) == 'Value')
    assert(result['qsd+'] == {})

    result = utils.parse_url('http://hostname/?+KeY=Value')
    assert(result['schema'] == 'http')
    assert(result['host'] == 'hostname')
    assert(result['port'] is None)
    assert(result['user'] is None)
    assert(result['password'] is None)
    assert(result['fullpath'] == '/')
    assert(result['path'] == '/')
    assert(result['query'] is None)
    assert(result['url'] == 'http://hostname/')
    assert('+key' in result['qsd'])
    assert('KeY' in result['qsd+'])
    assert(result['qsd+']['KeY'] == 'Value')
    assert(result['qsd-'] == {})

    result = utils.parse_url(
        'http://hostname/?+KeY=ValueA&-kEy=ValueB&KEY=Value%20+C')
    assert(result['schema'] == 'http')
    assert(result['host'] == 'hostname')
    assert(result['port'] is None)
    assert(result['user'] is None)
    assert(result['password'] is None)
    assert(result['fullpath'] == '/')
    assert(result['path'] == '/')
    assert(result['query'] is None)
    assert(result['url'] == 'http://hostname/')
    assert('+key' in result['qsd'])
    assert('-key' in result['qsd'])
    assert('key' in result['qsd'])
    assert('KeY' in result['qsd+'])
    assert(result['qsd+']['KeY'] == 'ValueA')
    assert('kEy' in result['qsd-'])
    assert(result['qsd-']['kEy'] == 'ValueB')
    assert(result['qsd']['key'] == 'Value  C')
    assert(result['qsd']['+key'] == result['qsd+']['KeY'])
    assert(result['qsd']['-key'] == result['qsd-']['kEy'])

    result = utils.parse_url('http://hostname////')
    assert(result['schema'] == 'http')
    assert(result['host'] == 'hostname')
    assert(result['port'] is None)
    assert(result['user'] is None)
    assert(result['password'] is None)
    assert(result['fullpath'] == '/')
    assert(result['path'] == '/')
    assert(result['query'] is None)
    assert(result['url'] == 'http://hostname/')
    assert(result['qsd'] == {})
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})

    result = utils.parse_url('http://hostname:40////')
    assert(result['schema'] == 'http')
    assert(result['host'] == 'hostname')
    assert(result['port'] == 40)
    assert(result['user'] is None)
    assert(result['password'] is None)
    assert(result['fullpath'] == '/')
    assert(result['path'] == '/')
    assert(result['query'] is None)
    assert(result['url'] == 'http://hostname:40/')
    assert(result['qsd'] == {})
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})

    result = utils.parse_url('HTTP://HoStNaMe:40/test.php')
    assert(result['schema'] == 'http')
    assert(result['host'] == 'HoStNaMe')
    assert(result['port'] == 40)
    assert(result['user'] is None)
    assert(result['password'] is None)
    assert(result['fullpath'] == '/test.php')
    assert(result['path'] == '/')
    assert(result['query'] == 'test.php')
    assert(result['url'] == 'http://HoStNaMe:40/test.php')
    assert(result['qsd'] == {})
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})

    result = utils.parse_url('HTTPS://user@hostname/test.py')
    assert(result['schema'] == 'https')
    assert(result['host'] == 'hostname')
    assert(result['port'] is None)
    assert(result['user'] == 'user')
    assert(result['password'] is None)
    assert(result['fullpath'] == '/test.py')
    assert(result['path'] == '/')
    assert(result['query'] == 'test.py')
    assert(result['url'] == 'https://user@hostname/test.py')
    assert(result['qsd'] == {})
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})

    result = utils.parse_url('  HTTPS://///user@@@hostname///test.py  ')
    assert(result['schema'] == 'https')
    assert(result['host'] == 'hostname')
    assert(result['port'] is None)
    assert(result['user'] == 'user')
    assert(result['password'] is None)
    assert(result['fullpath'] == '/test.py')
    assert(result['path'] == '/')
    assert(result['query'] == 'test.py')
    assert(result['url'] == 'https://user@hostname/test.py')
    assert(result['qsd'] == {})
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})

    result = utils.parse_url(
        'HTTPS://user:password@otherHost/full///path/name/',
    )
    assert(result['schema'] == 'https')
    assert(result['host'] == 'otherHost')
    assert(result['port'] is None)
    assert(result['user'] == 'user')
    assert(result['password'] == 'password')
    assert(result['fullpath'] == '/full/path/name/')
    assert(result['path'] == '/full/path/name/')
    assert(result['query'] is None)
    assert(result['url'] == 'https://user:password@otherHost/full/path/name/')
    assert(result['qsd'] == {})
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})

    # Handle garbage
    assert(utils.parse_url(None) is None)

    result = utils.parse_url(
        'mailto://user:password@otherHost/lead2gold@gmail.com' +
        '?from=test@test.com&name=Chris%20Caron&format=text'
    )
    assert(result['schema'] == 'mailto')
    assert(result['host'] == 'otherHost')
    assert(result['port'] is None)
    assert(result['user'] == 'user')
    assert(result['password'] == 'password')
    assert(unquote(result['fullpath']) == '/lead2gold@gmail.com')
    assert(result['path'] == '/')
    assert(unquote(result['query']) == 'lead2gold@gmail.com')
    assert(unquote(
        result['url']) ==
        'mailto://user:password@otherHost/lead2gold@gmail.com')
    assert(len(result['qsd']) == 3)
    assert('name' in result['qsd'])
    assert(unquote(result['qsd']['name']) == 'Chris Caron')
    assert('from' in result['qsd'])
    assert(unquote(result['qsd']['from']) == 'test@test.com')
    assert('format' in result['qsd'])
    assert(unquote(result['qsd']['format']) == 'text')
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})

    # Test Passwords with question marks ?; not supported
    result = utils.parse_url(
        'http://user:pass.with.?question@host'
    )
    assert(result is None)

    # just hostnames
    result = utils.parse_url(
        'nuxref.com'
    )
    assert(result['schema'] == 'http')
    assert(result['host'] == 'nuxref.com')
    assert(result['port'] is None)
    assert(result['user'] is None)
    assert(result['password'] is None)
    assert(result['fullpath'] is None)
    assert(result['path'] is None)
    assert(result['query'] is None)
    assert(result['url'] == 'http://nuxref.com')
    assert(result['qsd'] == {})
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})

    # just host and path
    result = utils.parse_url(
        'invalid/host'
    )
    assert(result['schema'] == 'http')
    assert(result['host'] == 'invalid')
    assert(result['port'] is None)
    assert(result['user'] is None)
    assert(result['password'] is None)
    assert(result['fullpath'] == '/host')
    assert(result['path'] == '/')
    assert(result['query'] == 'host')
    assert(result['url'] == 'http://invalid/host')
    assert(result['qsd'] == {})
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})

    # just all out invalid
    assert(utils.parse_url('?') is None)
    assert(utils.parse_url('/') is None)

    # A default port of zero is still considered valid, but
    # is removed in the response.
    result = utils.parse_url('http://nuxref.com:0')
    assert(result['schema'] == 'http')
    assert(result['host'] == 'nuxref.com')
    assert(result['port'] is None)
    assert(result['user'] is None)
    assert(result['password'] is None)
    assert(result['fullpath'] is None)
    assert(result['path'] is None)
    assert(result['query'] is None)
    assert(result['url'] == 'http://nuxref.com')
    assert(result['qsd'] == {})
    assert(result['qsd-'] == {})
    assert(result['qsd+'] == {})


def test_parse_bool():
    "utils: parse_bool() testing """

    assert(utils.parse_bool('Enabled', None) is True)
    assert(utils.parse_bool('Disabled', None) is False)
    assert(utils.parse_bool('Allow', None) is True)
    assert(utils.parse_bool('Deny', None) is False)
    assert(utils.parse_bool('Yes', None) is True)
    assert(utils.parse_bool('YES', None) is True)
    assert(utils.parse_bool('Always', None) is True)
    assert(utils.parse_bool('No', None) is False)
    assert(utils.parse_bool('NO', None) is False)
    assert(utils.parse_bool('NEVER', None) is False)
    assert(utils.parse_bool('TrUE', None) is True)
    assert(utils.parse_bool('tRUe', None) is True)
    assert(utils.parse_bool('FAlse', None) is False)
    assert(utils.parse_bool('F', None) is False)
    assert(utils.parse_bool('T', None) is True)
    assert(utils.parse_bool('0', None) is False)
    assert(utils.parse_bool('1', None) is True)
    assert(utils.parse_bool('True', None) is True)
    assert(utils.parse_bool('Yes', None) is True)
    assert(utils.parse_bool(1, None) is True)
    assert(utils.parse_bool(0, None) is False)
    assert(utils.parse_bool(True, None) is True)
    assert(utils.parse_bool(False, None) is False)

    # only the int of 0 will return False since the function
    # casts this to a boolean
    assert(utils.parse_bool(2, None) is True)
    # An empty list is still false
    assert(utils.parse_bool([], None) is False)
    # But a list that contains something is True
    assert(utils.parse_bool(['value', ], None) is True)

    # Use Default (which is False)
    assert(utils.parse_bool('OhYeah') is False)
    # Adjust Default and get a different result
    assert(utils.parse_bool('OhYeah', True) is True)


def test_is_hostname():
    """
    API: is_hostname() function

    """
    # Valid Hostnames
    assert utils.is_hostname('yahoo.ca') is True
    assert utils.is_hostname('yahoo.ca.') is True
    assert utils.is_hostname('valid-dashes-in-host.ca') is True
    assert utils.is_hostname('valid-underscores_in_host.ca') is True

    # Invalid Hostnames
    assert utils.is_hostname('invalid-characters_#^.ca') is False
    assert utils.is_hostname('    spaces   ') is False
    assert utils.is_hostname('       ') is False
    assert utils.is_hostname('') is False


def test_is_email():
    """
    API: is_email() function

    """
    # Valid Emails
    assert utils.is_email('test@gmail.com') is True
    assert utils.is_email('tag+test@gmail.com') is True

    # Invalid Emails
    assert utils.is_email('invalid.com') is False
    assert utils.is_email(object()) is False
    assert utils.is_email(None) is False


def test_split_urls():
    """utils: split_urls() testing """
    # A simple single array entry (As str)
    results = utils.split_urls('')
    assert isinstance(results, list)
    assert len(results) == 0

    # just delimeters
    results = utils.split_urls(',  ,, , ,,, ')
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.split_urls(',')
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.split_urls(None)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.split_urls(42)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.split_urls('this is not a parseable url at all')
    assert isinstance(results, list)
    assert len(results) == 0

    # Now test valid URLs
    results = utils.split_urls('windows://')
    assert isinstance(results, list)
    assert len(results) == 1
    assert 'windows://' in results

    results = utils.split_urls('windows:// gnome://')
    assert isinstance(results, list)
    assert len(results) == 2
    assert 'windows://' in results
    assert 'gnome://' in results

    # Commas and spaces found inside URLs are ignored
    urls = [
        'mailgun://noreply@sandbox.mailgun.org/apikey/?to=test@example.com,'
        'test2@example.com,, abcd@example.com',
        'mailgun://noreply@sandbox.another.mailgun.org/apikey/'
        '?to=hello@example.com,,hmmm@example.com,, abcd@example.com, ,',
        'windows://',
    ]

    # Since comma's and whitespace are the delimiters; they won't be
    # present at the end of the URL; so we just need to write a special
    # rstrip() as a regular exression to handle whitespace (\s) and comma
    # delimiter
    rstrip_re = re.compile(r'[\s,]+$')

    # Since a comma acts as a delimiter, we run a risk of a problem where the
    # comma exists as part of the URL and is therefore lost if it was found
    # at the end of it.

    results = utils.split_urls(', '.join(urls))
    assert isinstance(results, list)
    assert len(results) == len(urls)
    for url in urls:
        assert rstrip_re.sub('', url) in results

    # However if a comma is found at the end of a single url without a new
    # match to hit, it is saved and not lost

    # The comma at the end of the password will not be lost if we're
    # dealing with a single entry:
    url = 'http://hostname?password=,abcd,'
    results = utils.split_urls(url)
    assert isinstance(results, list)
    assert len(results) == 1
    assert url in results

    # however if we have multiple entries, commas and spaces between
    # URLs will be lost, however the last URL will not lose the comma
    urls = [
        'schema1://hostname?password=,abcd,',
        'schema2://hostname?password=,abcd,',
    ]
    results = utils.split_urls(', '.join(urls))
    assert isinstance(results, list)
    assert len(results) == len(urls)

    # No match because the comma is gone in the results entry
    # schema1://hostname?password=,abcd
    assert urls[0] not in results
    assert urls[0][:-1] in results

    # However we wouldn't have lost the comma in the second one:
    # schema2://hostname?password=,abcd,
    assert urls[1] in results


def test_parse_list():
    """utils: parse_list() testing """

    # A simple single array entry (As str)
    results = utils.parse_list(
        '.mkv,.avi,.divx,.xvid,.mov,.wmv,.mp4,.mpg,.mpeg,.vob,.iso')

    assert(results == sorted([
        '.divx', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.mpeg', '.vob',
        '.xvid', '.wmv', '.mp4',
    ]))

    class StrangeObject(object):
        def __str__(self):
            return '.avi'
    # Now 2 lists with lots of duplicates and other delimiters
    results = utils.parse_list(
        '.mkv,.avi,.divx,.xvid,.mov,.wmv,.mp4,.mpg .mpeg,.vob,,; ;',
        ('.mkv,.avi,.divx,.xvid,.mov    ', '    .wmv,.mp4;.mpg,.mpeg,'),
        '.vob,.iso', ['.vob', ['.vob', '.mkv', StrangeObject(), ], ],
        StrangeObject())

    assert(results == sorted([
        '.divx', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.mpeg', '.vob',
        '.xvid', '.wmv', '.mp4',
    ]))

    # Now a list with extras we want to add as strings
    # empty entries are removed
    results = utils.parse_list([
        '.divx', '.iso', '.mkv', '.mov', '', '  ', '.avi', '.mpeg', '.vob',
        '.xvid', '.mp4'], '.mov,.wmv,.mp4,.mpg')

    assert(results == sorted([
        '.divx', '.wmv', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.vob',
        '.xvid', '.mpeg', '.mp4',
    ]))


def test_exclusive_match():
    """utils: is_exclusive_match() testing
    """

    # No Logic always returns True
    assert utils.is_exclusive_match(data=None, logic=None) is True
    assert utils.is_exclusive_match(data=None, logic=set()) is True
    assert utils.is_exclusive_match(data='', logic=set()) is True
    assert utils.is_exclusive_match(data=u'', logic=set()) is True
    assert utils.is_exclusive_match(data=u'check', logic=set()) is True
    assert utils.is_exclusive_match(
        data=['check', 'checkb'], logic=set()) is True

    # String delimters are stripped out so that a list can be formed
    # the below is just an empty token list
    assert utils.is_exclusive_match(data=set(), logic=',;   ,') is True

    # garbage logic is never an exclusive match
    assert utils.is_exclusive_match(data=set(), logic=object()) is False
    assert utils.is_exclusive_match(data=set(), logic=[object(), ]) is False

    #
    # Test with logic:
    #
    data = set(['abc'])

    # def in data
    assert utils.is_exclusive_match(
        logic='def', data=data) is False
    # def in data
    assert utils.is_exclusive_match(
        logic=['def', ], data=data) is False
    # def in data
    assert utils.is_exclusive_match(
        logic=('def', ), data=data) is False
    # def in data
    assert utils.is_exclusive_match(
        logic=set(['def', ]), data=data) is False
    # abc in data
    assert utils.is_exclusive_match(
        logic=['abc', ], data=data) is True
    # abc in data
    assert utils.is_exclusive_match(
        logic=('abc', ), data=data) is True
    # abc in data
    assert utils.is_exclusive_match(
        logic=set(['abc', ]), data=data) is True
    # abc or def in data
    assert utils.is_exclusive_match(
        logic='abc, def', data=data) is True

    #
    # Update our data set so we can do more advance checks
    #
    data = set(['abc', 'def', 'efg', 'xyz'])

    # def and abc in data
    assert utils.is_exclusive_match(
        logic=[('abc', 'def')], data=data) is True

    # cba and abc in data
    assert utils.is_exclusive_match(
        logic=[('cba', 'abc')], data=data) is False

    # www or zzz or abc and xyz
    assert utils.is_exclusive_match(
        logic=['www', 'zzz', ('abc', 'xyz')], data=data) is True
    # www or zzz or abc and xyz (strings are valid too)
    assert utils.is_exclusive_match(
        logic=['www', 'zzz', ('abc, xyz')], data=data) is True

    # www or zzz or abc and jjj
    assert utils.is_exclusive_match(
        logic=['www', 'zzz', ('abc', 'jjj')], data=data) is False


def test_environ_temporary_change():
    """utils: environ() testing
    """

    e_key1 = 'APPRISE_TEMP1'
    e_key2 = 'APPRISE_TEMP2'
    e_key3 = 'APPRISE_TEMP3'

    e_val1 = 'ABCD'
    e_val2 = 'DEFG'
    e_val3 = 'HIJK'

    os.environ[e_key1] = e_val1
    os.environ[e_key2] = e_val2
    os.environ[e_key3] = e_val3

    # Ensure our environment variable stuck
    assert e_key1 in os.environ
    assert e_val1 in os.environ[e_key1]
    assert e_key2 in os.environ
    assert e_val2 in os.environ[e_key2]
    assert e_key3 in os.environ
    assert e_val3 in os.environ[e_key3]

    with utils.environ(e_key1, e_key3):
        # Eliminates Environment Variable 1 and 3
        assert e_key1 not in os.environ
        assert e_key2 in os.environ
        assert e_val2 in os.environ[e_key2]
        assert e_key3 not in os.environ

    # after with is over, environment is restored to normal
    assert e_key1 in os.environ
    assert e_val1 in os.environ[e_key1]
    assert e_key2 in os.environ
    assert e_val2 in os.environ[e_key2]
    assert e_key3 in os.environ
    assert e_val3 in os.environ[e_key3]

    d_key = 'APPRISE_NOT_SET'
    n_key = 'APPRISE_NEW_KEY'
    n_val = 'NEW_VAL'

    # Verify that our temporary variables (defined above) are not pre-existing
    # environemnt variables as we'll be setting them below
    assert n_key not in os.environ
    assert d_key not in os.environ

    # makes it easier to pass in the arguments
    updates = {
        e_key1: e_val3,
        e_key2: e_val1,
        n_key: n_val,
    }
    with utils.environ(d_key, e_key3, **updates):
        # Attempt to eliminate an undefined key (silently ignored)
        # Eliminates Environment Variable 3
        # Environment Variable 1 takes on the value of Env 3
        # Environment Variable 2 takes on the value of Env 1
        # Set a brand new variable that previously didn't exist
        assert e_key1 in os.environ
        assert e_val3 in os.environ[e_key1]
        assert e_key2 in os.environ
        assert e_val1 in os.environ[e_key2]
        assert e_key3 not in os.environ

        # Can't delete a variable that doesn't exist; so we're in the same
        # state here.
        assert d_key not in os.environ

        # Our temporary variables will be found now
        assert n_key in os.environ
        assert n_val in os.environ[n_key]

    # after with is over, environment is restored to normal
    assert e_key1 in os.environ
    assert e_val1 in os.environ[e_key1]
    assert e_key2 in os.environ
    assert e_val2 in os.environ[e_key2]
    assert e_key3 in os.environ
    assert e_val3 in os.environ[e_key3]

    # Even our temporary variables are now missing
    assert n_key not in os.environ
    assert d_key not in os.environ
