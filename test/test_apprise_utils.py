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
import sys
from inspect import cleandoc
from urllib.parse import unquote

from apprise import utils
from apprise import common

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Ensure we don't create .pyc files for these tests
sys.dont_write_bytecode = True


def test_parse_qsd():
    "utils: parse_qsd() testing """

    result = utils.parse_qsd('a=1&b=&c&d=abcd')
    assert isinstance(result, dict) is True
    assert len(result) == 4
    assert 'qsd' in result
    assert 'qsd+' in result
    assert 'qsd-' in result
    assert 'qsd:' in result

    assert len(result['qsd']) == 4
    assert 'a' in result['qsd']
    assert 'b' in result['qsd']
    assert 'c' in result['qsd']
    assert 'd' in result['qsd']

    assert len(result['qsd-']) == 0
    assert len(result['qsd+']) == 0
    assert len(result['qsd:']) == 0


def test_parse_url_general():
    "utils: parse_url() testing """

    result = utils.parse_url('http://hostname')
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url('http://hostname/')
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['query'] is None
    assert result['url'] == 'http://hostname/'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # colon after hostname without port number is no good
    assert utils.parse_url('http://hostname:') is None

    # An invalid port
    result = utils.parse_url(
        'http://hostname:invalid', verify_host=False, strict_port=True)
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 'invalid'
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname:invalid'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # However if we don't verify the host, it is okay
    result = utils.parse_url('http://hostname:', verify_host=False)
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname:'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname:'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # A port of Zero is not valid with strict port checking
    assert utils.parse_url('http://hostname:0', strict_port=True) is None

    # Without strict port checking however, it is okay
    result = utils.parse_url('http://hostname:0', strict_port=False)
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 0
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname:0'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # A negative port is not valid
    assert utils.parse_url('http://hostname:-92', strict_port=True) is None
    result = utils.parse_url(
        'http://hostname:-92', verify_host=False, strict_port=True)
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == -92
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname:-92'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # A port that is too large is not valid
    assert utils.parse_url('http://hostname:65536', strict_port=True) is None

    # This is an accetable port (the maximum)
    result = utils.parse_url('http://hostname:65535', strict_port=True)
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 65535
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname:65535'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # This is an accetable port (the maximum)
    result = utils.parse_url('http://hostname:1', strict_port=True)
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 1
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname:1'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # A port that was identfied as a string is invalid
    assert utils.parse_url('http://hostname:invalid', strict_port=True) is None
    result = utils.parse_url(
        'http://hostname:invalid', verify_host=False, strict_port=True)
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 'invalid'
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname:invalid'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url(
        'http://hostname:invalid', verify_host=False, strict_port=False)
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname:invalid'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname:invalid'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url(
        'http://hostname:invalid?key=value&-minuskey=mvalue',
        verify_host=False, strict_port=False)
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname:invalid'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname:invalid'
    assert unquote(result['qsd']['-minuskey']) == 'mvalue'
    assert unquote(result['qsd']['key']) == 'value'
    assert unquote(result['qsd-']['minuskey']) == 'mvalue'
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # Handling of floats
    assert utils.parse_url('http://hostname:4.2', strict_port=True) is None
    result = utils.parse_url(
        'http://hostname:4.2', verify_host=False, strict_port=True)
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == '4.2'
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname:4.2'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # A Port of zero is not acceptable for a regular hostname
    assert utils.parse_url('http://hostname:0', strict_port=True) is None

    # No host verification (zero is an acceptable port when this is the case
    result = utils.parse_url('http://hostname:0', verify_host=False)
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 0
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname:0'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url(
        'http://[2001:db8:002a:3256:adfe:05c0:0003:0006]:8080',
        verify_host=False)
    assert result['schema'] == 'http'
    assert result['host'] == '[2001:db8:002a:3256:adfe:05c0:0003:0006]'
    assert result['port'] == 8080
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == \
        'http://[2001:db8:002a:3256:adfe:05c0:0003:0006]:8080'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url(
        'http://hostname:0', verify_host=False, strict_port=True)
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 0
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://hostname:0'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url('http://hostname/?-KeY=Value')
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['query'] is None
    assert result['url'] == 'http://hostname/'
    assert '-key' in result['qsd']
    assert unquote(result['qsd']['-key']) == 'Value'
    assert 'KeY' in result['qsd-']
    assert unquote(result['qsd-']['KeY']) == 'Value'
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url('http://hostname/?+KeY=Value')
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['query'] is None
    assert result['url'] == 'http://hostname/'
    assert '+key' in result['qsd']
    assert 'KeY' in result['qsd+']
    assert result['qsd+']['KeY'] == 'Value'
    assert result['qsd-'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url('http://hostname/?:kEy=vALUE')
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['query'] is None
    assert result['url'] == 'http://hostname/'
    assert ':key' in result['qsd']
    assert 'kEy' in result['qsd:']
    assert result['qsd:']['kEy'] == 'vALUE'
    assert result['qsd+'] == {}
    assert result['qsd-'] == {}

    result = utils.parse_url(
        'http://hostname/?+KeY=ValueA&-kEy=ValueB&KEY=Value%20+C&:colon=y')
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['query'] is None
    assert result['url'] == 'http://hostname/'
    assert '+key' in result['qsd']
    assert '-key' in result['qsd']
    assert ':colon' in result['qsd']
    assert result['qsd:']['colon'] == 'y'
    assert 'key' in result['qsd']
    assert 'KeY' in result['qsd+']
    assert result['qsd+']['KeY'] == 'ValueA'
    assert 'kEy' in result['qsd-']
    assert result['qsd-']['kEy'] == 'ValueB'
    assert result['qsd']['key'] == 'Value  C'
    assert result['qsd']['+key'] == result['qsd+']['KeY']
    assert result['qsd']['-key'] == result['qsd-']['kEy']

    result = utils.parse_url('http://hostname////')
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['query'] is None
    assert result['url'] == 'http://hostname/'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url('http://hostname:40////')
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 40
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['query'] is None
    assert result['url'] == 'http://hostname:40/'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url('HTTP://HoStNaMe:40/test.php')
    assert result['schema'] == 'http'
    assert result['host'] == 'HoStNaMe'
    assert result['port'] == 40
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] == '/test.php'
    assert result['path'] == '/'
    assert result['query'] == 'test.php'
    assert result['url'] == 'http://HoStNaMe:40/test.php'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url('HTTPS://user@hostname/test.py')
    assert result['schema'] == 'https'
    assert result['host'] == 'hostname'
    assert result['port'] is None
    assert result['user'] == 'user'
    assert result['password'] is None
    assert result['fullpath'] == '/test.py'
    assert result['path'] == '/'
    assert result['query'] == 'test.py'
    assert result['url'] == 'https://user@hostname/test.py'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url('  HTTPS://///user@@@hostname///test.py  ')
    assert result['schema'] == 'https'
    assert result['host'] == 'hostname'
    assert result['port'] is None
    assert result['user'] == 'user'
    assert result['password'] is None
    assert result['fullpath'] == '/test.py'
    assert result['path'] == '/'
    assert result['query'] == 'test.py'
    assert result['url'] == 'https://user@hostname/test.py'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url(
        'HTTPS://user:password@otherHost/full///path/name/',
    )
    assert result['schema'] == 'https'
    assert result['host'] == 'otherHost'
    assert result['port'] is None
    assert result['user'] == 'user'
    assert result['password'] == 'password'
    assert result['fullpath'] == '/full/path/name/'
    assert result['path'] == '/full/path/name/'
    assert result['query'] is None
    assert result['url'] == 'https://user:password@otherHost/full/path/name/'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url(
        'HTTPS://hostname/a/path/ending/with/slash/?key=value',
    )
    assert result['schema'] == 'https'
    assert result['host'] == 'hostname'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] == '/a/path/ending/with/slash/'
    assert result['path'] == '/a/path/ending/with/slash/'
    assert result['query'] is None
    assert result['url'] == 'https://hostname/a/path/ending/with/slash/'
    assert result['qsd'] == {'key': 'value'}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # Handle garbage
    assert utils.parse_url(None) is None

    result = utils.parse_url(
        'mailto://user:password@otherHost/lead2gold@gmail.com' +
        '?from=test@test.com&name=Chris%20Caron&format=text'
    )
    assert result['schema'] == 'mailto'
    assert result['host'] == 'otherHost'
    assert result['port'] is None
    assert result['user'] == 'user'
    assert result['password'] == 'password'
    assert unquote(result['fullpath']) == '/lead2gold@gmail.com'
    assert result['path'] == '/'
    assert unquote(result['query']) == 'lead2gold@gmail.com'
    assert unquote(result['url']) == \
        'mailto://user:password@otherHost/lead2gold@gmail.com'
    assert len(result['qsd']) == 3
    assert 'name' in result['qsd']
    assert unquote(result['qsd']['name']) == 'Chris Caron'
    assert 'from' in result['qsd']
    assert unquote(result['qsd']['from']) == 'test@test.com'
    assert 'format' in result['qsd']
    assert unquote(result['qsd']['format']) == 'text'
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # Test Passwords with question marks ?; not supported
    result = utils.parse_url(
        'http://user:pass.with.?question@host'
    )
    assert result is None

    # just hostnames
    result = utils.parse_url(
        'nuxref.com'
    )
    assert result['schema'] == 'http'
    assert result['host'] == 'nuxref.com'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'http://nuxref.com'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # just host and path
    result = utils.parse_url('invalid/host')
    assert result['schema'] == 'http'
    assert result['host'] == 'invalid'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] == '/host'
    assert result['path'] == '/'
    assert result['query'] == 'host'
    assert result['url'] == 'http://invalid/host'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # just all out invalid
    assert utils.parse_url('?') is None
    assert utils.parse_url('/') is None

    # Test some illegal strings
    result = utils.parse_url(object, verify_host=False)
    assert result is None
    result = utils.parse_url(None, verify_host=False)
    assert result is None

    # Just a schema; invalid host
    result = utils.parse_url('test://')
    assert result is None

    # Do it again without host validation
    result = utils.parse_url('test://', verify_host=False)
    assert result['schema'] == 'test'
    # It's worth noting that the hostname is an empty string and is NEVER set
    # to None if it wasn't specified.
    assert result['host'] == ''
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    assert result['url'] == 'test://'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url('testhostname')
    assert result['schema'] == 'http'
    assert result['host'] == 'testhostname'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    # The default_schema kicks in here
    assert result['url'] == 'http://testhostname'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url('example.com', default_schema='unknown')
    assert result['schema'] == 'unknown'
    assert result['host'] == 'example.com'
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    # The default_schema kicks in here
    assert result['url'] == 'unknown://example.com'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # An empty string without a hostame is still valid if verify_host is set
    result = utils.parse_url('', verify_host=False)
    assert result['schema'] == 'http'
    assert result['host'] == ''
    assert result['port'] is None
    assert result['user'] is None
    assert result['password'] is None
    assert result['fullpath'] is None
    assert result['path'] is None
    assert result['query'] is None
    # The default_schema kicks in here
    assert result['url'] == 'http://'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    # A messed up URL
    result = utils.parse_url('test://:@/', verify_host=False)
    assert result['schema'] == 'test'
    assert result['host'] == ''
    assert result['port'] is None
    assert result['user'] == ''
    assert result['password'] == ''
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['query'] is None
    assert result['url'] == 'test://:@/'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}

    result = utils.parse_url('crazy://:@//_/@^&/jack.json', verify_host=False)
    assert result['schema'] == 'crazy'
    assert result['host'] == ''
    assert result['port'] is None
    assert result['user'] == ''
    assert result['password'] == ''
    assert unquote(result['fullpath']) == '/_/@^&/jack.json'
    assert unquote(result['path']) == '/_/@^&/'
    assert result['query'] == 'jack.json'
    assert unquote(result['url']) == 'crazy://:@/_/@^&/jack.json'
    assert result['qsd'] == {}
    assert result['qsd-'] == {}
    assert result['qsd+'] == {}
    assert result['qsd:'] == {}


def test_parse_url_simple():
    "utils: parse_url() testing """

    result = utils.parse_url('http://hostname', simple=True)
    assert len(result) == 3
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['url'] == 'http://hostname'

    result = utils.parse_url('http://hostname/', simple=True)
    assert len(result) == 5
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['url'] == 'http://hostname/'

    # colon after hostname without port number is no good
    assert utils.parse_url('http://hostname:', simple=True) is None

    # An invalid port
    result = utils.parse_url(
        'http://hostname:invalid', verify_host=False, strict_port=True,
        simple=True)
    assert len(result) == 4
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 'invalid'
    assert result['url'] == 'http://hostname:invalid'

    # However if we don't verify the host, it is okay
    result = utils.parse_url(
        'http://hostname:', verify_host=False, simple=True)
    assert len(result) == 3
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname:'
    assert result['url'] == 'http://hostname:'

    # A port of Zero is not valid with strict port checking
    assert utils.parse_url(
        'http://hostname:0', strict_port=True, simple=True) is None

    # Without strict port checking however, it is okay
    result = utils.parse_url(
        'http://hostname:0', strict_port=False, simple=True)
    assert len(result) == 4
    assert result['schema'] == 'http'
    assert result['port'] == 0
    assert result['host'] == 'hostname'
    assert result['url'] == 'http://hostname:0'

    # A negative port is not valid
    assert utils.parse_url(
        'http://hostname:-92', strict_port=True, simple=True) is None
    result = utils.parse_url(
        'http://hostname:-92', verify_host=False, strict_port=True,
        simple=True)
    assert len(result) == 4
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == -92
    assert result['url'] == 'http://hostname:-92'

    # A port that is too large is not valid
    assert utils.parse_url(
        'http://hostname:65536', strict_port=True, simple=True) is None

    # This is an accetable port (the maximum)
    result = utils.parse_url(
        'http://hostname:65535', strict_port=True, simple=True)
    assert len(result) == 4
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 65535
    assert result['url'] == 'http://hostname:65535'

    # This is an accetable port (the maximum)
    result = utils.parse_url(
        'http://hostname:1', strict_port=True, simple=True)
    assert len(result) == 4
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 1
    assert result['url'] == 'http://hostname:1'

    # A port that was identfied as a string is invalid
    assert utils.parse_url(
        'http://hostname:invalid', strict_port=True, simple=True) is None
    result = utils.parse_url(
        'http://hostname:invalid', verify_host=False, strict_port=True,
        simple=True)
    assert len(result) == 4
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 'invalid'
    assert result['url'] == 'http://hostname:invalid'

    result = utils.parse_url(
        'http://hostname:invalid', verify_host=False, strict_port=False,
        simple=True)
    assert len(result) == 3
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname:invalid'
    assert result['url'] == 'http://hostname:invalid'

    result = utils.parse_url(
        'http://hostname:invalid?key=value&-minuskey=mvalue',
        verify_host=False, strict_port=False, simple=True)
    assert len(result) == 4
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname:invalid'
    assert result['url'] == 'http://hostname:invalid'
    assert isinstance(result['qsd'], dict)
    assert len(result['qsd']) == 2
    assert unquote(result['qsd']['-minuskey']) == 'mvalue'
    assert unquote(result['qsd']['key']) == 'value'

    # Handling of floats
    assert utils.parse_url(
        'http://hostname:4.2', strict_port=True, simple=True) is None
    result = utils.parse_url(
        'http://hostname:4.2', verify_host=False, strict_port=True,
        simple=True)
    assert len(result) == 4
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == '4.2'
    assert result['url'] == 'http://hostname:4.2'

    # A Port of zero is not acceptable for a regular hostname
    assert utils.parse_url(
        'http://hostname:0', strict_port=True, simple=True) is None

    # No host verification (zero is an acceptable port when this is the case
    result = utils.parse_url(
        'http://hostname:0', verify_host=False, simple=True)
    assert len(result) == 4
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 0
    assert result['url'] == 'http://hostname:0'

    result = utils.parse_url(
        'http://[2001:db8:002a:3256:adfe:05c0:0003:0006]:8080',
        verify_host=False, simple=True)
    assert len(result) == 4
    assert result['schema'] == 'http'
    assert result['host'] == '[2001:db8:002a:3256:adfe:05c0:0003:0006]'
    assert result['port'] == 8080
    assert result['url'] == \
        'http://[2001:db8:002a:3256:adfe:05c0:0003:0006]:8080'

    result = utils.parse_url(
        'http://hostname:0', verify_host=False, strict_port=True, simple=True)
    assert len(result) == 4
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 0
    assert result['url'] == 'http://hostname:0'

    result = utils.parse_url('http://hostname/?-KeY=Value', simple=True)
    assert len(result) == 6
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['url'] == 'http://hostname/'
    assert '-key' in result['qsd']
    assert unquote(result['qsd']['-key']) == 'Value'

    result = utils.parse_url('http://hostname/?+KeY=Value', simple=True)
    assert len(result) == 6
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['url'] == 'http://hostname/'
    assert '+key' in result['qsd']
    assert result['qsd']['+key'] == 'Value'

    result = utils.parse_url('http://hostname/?:kEy=vALUE', simple=True)
    assert len(result) == 6
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['url'] == 'http://hostname/'
    assert ':key' in result['qsd']
    assert result['qsd'][':key'] == 'vALUE'

    result = utils.parse_url(
        'http://hostname/?+KeY=ValueA&-kEy=ValueB&KEY=Value%20+C&:colon=y',
        simple=True)
    assert len(result) == 6
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['url'] == 'http://hostname/'
    assert '+key' in result['qsd']
    assert '-key' in result['qsd']
    assert ':colon' in result['qsd']
    assert result['qsd'][':colon'] == 'y'
    assert result['qsd']['key'] == 'Value  C'
    assert result['qsd']['+key'] == 'ValueA'
    assert result['qsd']['-key'] == 'ValueB'

    result = utils.parse_url('http://hostname////', simple=True)
    assert len(result) == 5
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['url'] == 'http://hostname/'

    result = utils.parse_url('http://hostname:40////', simple=True)
    assert len(result) == 6
    assert result['schema'] == 'http'
    assert result['host'] == 'hostname'
    assert result['port'] == 40
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['url'] == 'http://hostname:40/'

    result = utils.parse_url('HTTP://HoStNaMe:40/test.php', simple=True)
    assert len(result) == 7
    assert result['schema'] == 'http'
    assert result['host'] == 'HoStNaMe'
    assert result['port'] == 40
    assert result['fullpath'] == '/test.php'
    assert result['path'] == '/'
    assert result['query'] == 'test.php'
    assert result['url'] == 'http://HoStNaMe:40/test.php'

    result = utils.parse_url('HTTPS://user@hostname/test.py', simple=True)
    assert len(result) == 7
    assert result['schema'] == 'https'
    assert result['host'] == 'hostname'
    assert result['user'] == 'user'
    assert result['fullpath'] == '/test.py'
    assert result['path'] == '/'
    assert result['query'] == 'test.py'
    assert result['url'] == 'https://user@hostname/test.py'

    result = utils.parse_url(
        '  HTTPS://///user@@@hostname///test.py  ', simple=True)
    assert len(result) == 7
    assert result['schema'] == 'https'
    assert result['host'] == 'hostname'
    assert result['user'] == 'user'
    assert result['fullpath'] == '/test.py'
    assert result['path'] == '/'
    assert result['query'] == 'test.py'
    assert result['url'] == 'https://user@hostname/test.py'

    result = utils.parse_url(
        'HTTPS://user:password@otherHost/full///path/name/',
        simple=True,
    )
    assert len(result) == 7
    assert result['schema'] == 'https'
    assert result['host'] == 'otherHost'
    assert result['user'] == 'user'
    assert result['password'] == 'password'
    assert result['fullpath'] == '/full/path/name/'
    assert result['path'] == '/full/path/name/'
    assert result['url'] == 'https://user:password@otherHost/full/path/name/'

    # Handle garbage
    assert utils.parse_url(None) is None

    result = utils.parse_url(
        'mailto://user:password@otherHost/lead2gold@gmail.com' +
        '?from=test@test.com&name=Chris%20Caron&format=text',
        simple=True,
    )
    assert len(result) == 9
    assert result['schema'] == 'mailto'
    assert result['host'] == 'otherHost'
    assert result['user'] == 'user'
    assert result['password'] == 'password'
    assert unquote(result['fullpath']) == '/lead2gold@gmail.com'
    assert result['path'] == '/'
    assert unquote(result['query']) == 'lead2gold@gmail.com'
    assert unquote(result['url']) == \
        'mailto://user:password@otherHost/lead2gold@gmail.com'
    assert len(result['qsd']) == 3
    assert 'name' in result['qsd']
    assert unquote(result['qsd']['name']) == 'Chris Caron'
    assert 'from' in result['qsd']
    assert unquote(result['qsd']['from']) == 'test@test.com'
    assert 'format' in result['qsd']
    assert unquote(result['qsd']['format']) == 'text'

    # Test Passwords with question marks ?; not supported
    result = utils.parse_url(
        'http://user:pass.with.?question@host',
        simple=True
    )
    assert result is None

    # just hostnames
    result = utils.parse_url(
        'nuxref.com', simple=True,
    )
    assert len(result) == 3
    assert result['schema'] == 'http'
    assert result['host'] == 'nuxref.com'
    assert result['url'] == 'http://nuxref.com'

    # just host and path
    result = utils.parse_url('invalid/host', simple=True)
    assert len(result) == 6
    assert result['schema'] == 'http'
    assert result['host'] == 'invalid'
    assert result['fullpath'] == '/host'
    assert result['path'] == '/'
    assert result['query'] == 'host'
    assert result['url'] == 'http://invalid/host'

    # just all out invalid
    assert utils.parse_url('?', simple=True) is None
    assert utils.parse_url('/', simple=True) is None

    # Test some illegal strings
    result = utils.parse_url(object, verify_host=False, simple=True)
    assert result is None
    result = utils.parse_url(None, verify_host=False, simple=True)
    assert result is None

    # Just a schema; invalid host
    result = utils.parse_url('test://', simple=True)
    assert result is None

    # Do it again without host validation
    result = utils.parse_url('test://', verify_host=False, simple=True)
    assert len(result) == 2
    assert result['schema'] == 'test'
    assert result['url'] == 'test://'

    result = utils.parse_url('testhostname', simple=True)
    assert len(result) == 3
    assert result['schema'] == 'http'
    assert result['host'] == 'testhostname'
    # The default_schema kicks in here
    assert result['url'] == 'http://testhostname'

    result = utils.parse_url(
        'example.com', default_schema='unknown', simple=True)
    assert len(result) == 3
    assert result['schema'] == 'unknown'
    assert result['host'] == 'example.com'
    # The default_schema kicks in here
    assert result['url'] == 'unknown://example.com'

    # An empty string without a hostame is still valid if verify_host is set
    result = utils.parse_url('', verify_host=False, simple=True)
    assert len(result) == 2
    assert result['schema'] == 'http'
    # The default_schema kicks in here
    assert result['url'] == 'http://'

    # A messed up URL
    result = utils.parse_url('test://:@/', verify_host=False, simple=True)
    assert len(result) == 6
    assert result['schema'] == 'test'
    assert result['user'] == ''
    assert result['password'] == ''
    assert result['fullpath'] == '/'
    assert result['path'] == '/'
    assert result['url'] == 'test://:@/'

    result = utils.parse_url(
        'crazy://:@//_/@^&/jack.json', verify_host=False, simple=True)
    assert len(result) == 7
    assert result['schema'] == 'crazy'
    assert result['user'] == ''
    assert result['password'] == ''
    assert unquote(result['fullpath']) == '/_/@^&/jack.json'
    assert unquote(result['path']) == '/_/@^&/'
    assert result['query'] == 'jack.json'
    assert unquote(result['url']) == 'crazy://:@/_/@^&/jack.json'


def test_url_assembly():
    """
    "utils: url_assembly() testing """

    url = 'schema://user:password@hostname:port/path/?key=value'
    assert utils.url_assembly(**utils.parse_url(url, verify_host=False)) == url

    # Same URL without trailing slash after path
    url = 'schema://user:password@hostname:port/path?key=value'
    assert utils.url_assembly(**utils.parse_url(url, verify_host=False)) == url

    url = 'schema://user@hostname:port/path?key=value'
    assert utils.url_assembly(**utils.parse_url(url, verify_host=False)) == url

    url = 'schema://hostname:10/a/file.php'
    assert utils.url_assembly(**utils.parse_url(url, verify_host=False)) == url


def test_parse_bool():
    "utils: parse_bool() testing """

    assert utils.parse_bool('Enabled', None) is True
    assert utils.parse_bool('Disabled', None) is False
    assert utils.parse_bool('Allow', None) is True
    assert utils.parse_bool('Deny', None) is False
    assert utils.parse_bool('Yes', None) is True
    assert utils.parse_bool('YES', None) is True
    assert utils.parse_bool('Always', None) is True
    assert utils.parse_bool('No', None) is False
    assert utils.parse_bool('NO', None) is False
    assert utils.parse_bool('NEVER', None) is False
    assert utils.parse_bool('TrUE', None) is True
    assert utils.parse_bool('tRUe', None) is True
    assert utils.parse_bool('FAlse', None) is False
    assert utils.parse_bool('F', None) is False
    assert utils.parse_bool('T', None) is True
    assert utils.parse_bool('0', None) is False
    assert utils.parse_bool('1', None) is True
    assert utils.parse_bool('True', None) is True
    assert utils.parse_bool('Yes', None) is True
    assert utils.parse_bool(1, None) is True
    assert utils.parse_bool(0, None) is False
    assert utils.parse_bool(True, None) is True
    assert utils.parse_bool(False, None) is False

    # only the int of 0 will return False since the function
    # casts this to a boolean
    assert utils.parse_bool(2, None) is True
    # An empty list is still false
    assert utils.parse_bool([], None) is False
    # But a list that contains something is True
    assert utils.parse_bool(['value', ], None) is True

    # Use Default (which is False)
    assert utils.parse_bool('OhYeah') is False
    # Adjust Default and get a different result
    assert utils.parse_bool('OhYeah', True) is True


def test_is_uuid():
    """
    API: is_uuid() function
    """
    # Invalid Entries
    assert utils.is_uuid('invalid') is False
    assert utils.is_uuid(None) is False
    assert utils.is_uuid(5) is False
    assert utils.is_uuid(object) is False

    # A slightly invalid uuid4 entry
    assert utils.is_uuid('591ed387-fa65-ac97-9712-b9d2a15e42a9') is False
    assert utils.is_uuid('591ed387-fa65-Jc97-9712-b9d2a15e42a9') is False

    # Valid UUID4 Entries
    assert utils.is_uuid('591ed387-fa65-4c97-9712-b9d2a15e42a9') is True
    assert utils.is_uuid('32b0b447-fe84-4df1-8368-81925e729265') is True


def test_is_hostname():
    """
    API: is_hostname() function

    """
    # Valid Hostnames
    assert utils.is_hostname('yahoo.ca') == 'yahoo.ca'
    assert utils.is_hostname('yahoo.ca.') == 'yahoo.ca'
    assert utils.is_hostname('valid-dashes-in-host.ca') == \
        'valid-dashes-in-host.ca'
    assert utils.is_hostname('valid-underscores_in_host.ca') == \
        'valid-underscores_in_host.ca'

    # Underscores are supported by default
    assert utils.is_hostname('valid_dashes_in_host.ca') == \
        'valid_dashes_in_host.ca'
    # However they are not if specified otherwise:
    assert utils.is_hostname(
        'valid_dashes_in_host.ca', underscore=False) is False

    # Invalid Hostnames
    assert utils.is_hostname('-hostname.that.starts.with.a.dash') is False
    assert utils.is_hostname('invalid-characters_#^.ca') is False
    assert utils.is_hostname('    spaces   ') is False
    assert utils.is_hostname('       ') is False
    assert utils.is_hostname('') is False

    # Valid IPv4 Addresses
    assert utils.is_hostname('127.0.0.1') == '127.0.0.1'
    assert utils.is_hostname('0.0.0.0') == '0.0.0.0'
    assert utils.is_hostname('255.255.255.255') == '255.255.255.255'

    # But not if we're not checking for this:
    assert utils.is_hostname('127.0.0.1', ipv4=False) is False
    assert utils.is_hostname('0.0.0.0', ipv4=False) is False
    assert utils.is_hostname('255.255.255.255', ipv4=False) is False

    # Invalid IPv4 Addresses
    assert utils.is_hostname('1.2.3') is False
    assert utils.is_hostname('256.256.256.256') is False
    assert utils.is_hostname('999.0.0.0') is False
    assert utils.is_hostname('1.2.3.4.5') is False
    assert utils.is_hostname('    127.0.0.1   ') is False
    assert utils.is_hostname('       ') is False
    assert utils.is_hostname('') is False

    # Valid IPv6 Addresses (square brakets supported for URL construction)
    assert utils.is_hostname('[2001:0db8:85a3:0000:0000:8a2e:0370:7334]') == \
        '[2001:0db8:85a3:0000:0000:8a2e:0370:7334]'
    assert utils.is_hostname('2001:0db8:85a3:0000:0000:8a2e:0370:7334') == \
        '[2001:0db8:85a3:0000:0000:8a2e:0370:7334]'
    assert utils.is_hostname('[2001:db8:002a:3256:adfe:05c0:0003:0006]') == \
        '[2001:db8:002a:3256:adfe:05c0:0003:0006]'

    # localhost
    assert utils.is_hostname('::1') == '[::1]'
    assert utils.is_hostname('0:0:0:0:0:0:0:1') == '[0:0:0:0:0:0:0:1]'

    # But not if we're not checking for this:
    assert utils.is_hostname(
        '[2001:0db8:85a3:0000:0000:8a2e:0370:7334]', ipv6=False) is False
    assert utils.is_hostname(
        '2001:0db8:85a3:0000:0000:8a2e:0370:7334', ipv6=False) is False

    # Test hostnames with a single character hostname
    assert utils.is_hostname(
        'cloud.a.example.com', ipv4=False, ipv6=False) == 'cloud.a.example.com'


def test_is_ipaddr():
    """
    API: is_ipaddr() function

    """
    # Valid IPv4 Addresses
    assert utils.is_ipaddr('127.0.0.1') == '127.0.0.1'
    assert utils.is_ipaddr('0.0.0.0') == '0.0.0.0'
    assert utils.is_ipaddr('255.255.255.255') == '255.255.255.255'

    # Invalid IPv4 Addresses
    assert utils.is_ipaddr('1.2.3') is False
    assert utils.is_ipaddr('256.256.256.256') is False
    assert utils.is_ipaddr('999.0.0.0') is False
    assert utils.is_ipaddr('1.2.3.4.5') is False
    assert utils.is_ipaddr('    127.0.0.1   ') is False
    assert utils.is_ipaddr('       ') is False
    assert utils.is_ipaddr('') is False

    # Valid IPv6 Addresses (square brakets supported for URL construction)
    assert utils.is_ipaddr('[2001:0db8:85a3:0000:0000:8a2e:0370:7334]') == \
        '[2001:0db8:85a3:0000:0000:8a2e:0370:7334]'
    assert utils.is_ipaddr('2001:0db8:85a3:0000:0000:8a2e:0370:7334') == \
        '[2001:0db8:85a3:0000:0000:8a2e:0370:7334]'
    assert utils.is_ipaddr('[2001:db8:002a:3256:adfe:05c0:0003:0006]') == \
        '[2001:db8:002a:3256:adfe:05c0:0003:0006]'

    # localhost
    assert utils.is_ipaddr('::1') == '[::1]'
    assert utils.is_ipaddr('0:0:0:0:0:0:0:1') == '[0:0:0:0:0:0:0:1]'


def test_is_email():
    """
    API: is_email() function

    """
    # Valid Emails
    results = utils.is_email('test@gmail.com')
    assert '' == results['name']
    assert 'test@gmail.com' == results['email']
    assert 'test@gmail.com' == results['full_email']
    assert 'gmail.com' == results['domain']
    assert 'test' == results['user']
    assert '' == results['label']

    results = utils.is_email('test@my-valid_host.com')
    assert '' == results['name']
    assert 'test@my-valid_host.com' == results['email']
    assert 'test@my-valid_host.com' == results['full_email']
    assert 'my-valid_host.com' == results['domain']
    assert 'test' == results['user']
    assert '' == results['label']

    results = utils.is_email('tag+test@gmail.com')
    assert '' == results['name']
    assert 'test@gmail.com' == results['email']
    assert 'tag+test@gmail.com' == results['full_email']
    assert 'gmail.com' == results['domain']
    assert 'test' == results['user']
    assert 'tag' == results['label']

    # Support Full Names as well
    results = utils.is_email('Bill Gates: bgates@microsoft.com')
    assert 'Bill Gates' == results['name']
    assert 'bgates@microsoft.com' == results['email']
    assert 'bgates@microsoft.com' == results['full_email']
    assert 'microsoft.com' == results['domain']
    assert 'bgates' == results['user']
    assert '' == results['label']

    results = utils.is_email('Bill Gates <bgates@microsoft.com>')
    assert 'Bill Gates' == results['name']
    assert 'bgates@microsoft.com' == results['email']
    assert 'bgates@microsoft.com' == results['full_email']
    assert 'microsoft.com' == results['domain']
    assert 'bgates' == results['user']
    assert '' == results['label']

    results = utils.is_email('Bill Gates: <bgates@microsoft.com>')
    assert 'Bill Gates' == results['name']
    assert 'bgates@microsoft.com' == results['email']
    assert 'bgates@microsoft.com' == results['full_email']
    assert 'microsoft.com' == results['domain']
    assert 'bgates' == results['user']
    assert '' == results['label']

    results = utils.is_email('Sundar Pichai <ceo+spichai@gmail.com>')
    assert 'Sundar Pichai' == results['name']
    assert 'spichai@gmail.com' == results['email']
    assert 'ceo+spichai@gmail.com' == results['full_email']
    assert 'gmail.com' == results['domain']
    assert 'spichai' == results['user']
    assert 'ceo' == results['label']

    # Support Quotes
    results = utils.is_email('"Chris Hemsworth" <ch@test.com>')
    assert 'Chris Hemsworth' == results['name']
    assert 'ch@test.com' == results['email']
    assert 'ch@test.com' == results['full_email']
    assert 'test.com' == results['domain']
    assert 'ch' == results['user']
    assert '' == results['label']

    # An email without name, but contains delimiters
    results = utils.is_email('      <spichai@gmail.com>')
    assert '' == results['name']
    assert 'spichai@gmail.com' == results['email']
    assert 'spichai@gmail.com' == results['full_email']
    assert 'gmail.com' == results['domain']
    assert 'spichai' == results['user']
    assert '' == results['label']

    # a valid email not properly delimited with a colon or angle bracket
    # We do a best guess and still parse it correctly
    results = utils.is_email("Name valid@example.com")
    assert 'Name' == results['name']
    assert 'valid@example.com' == results['email']
    assert 'valid@example.com' == results['full_email']
    assert 'example.com' == results['domain']
    assert 'valid' == results['user']
    assert '' == results['label']

    # a valid email not properly delimited with a colon or angle bracket
    # We do a best guess and still parse it correctly
    results = utils.is_email("Руслан Эра russian+russia@example.ru")
    assert 'Руслан Эра' == results['name']
    assert 'russia@example.ru' == results['email']
    assert 'russian+russia@example.ru' == results['full_email']
    assert 'example.ru' == results['domain']
    assert 'russia' == results['user']
    assert 'russian' == results['label']

    # Invalid Emails
    assert utils.is_email('invalid.com') is False
    assert utils.is_email(object()) is False
    assert utils.is_email(None) is False
    assert utils.is_email("Just A Name") is False
    assert utils.is_email("Name <bademail>") is False


def test_is_call_sign_no():
    """
    API: is_call_sign() function

    """
    # Invalid numbers
    assert utils.is_call_sign(None) is False
    assert utils.is_call_sign(42) is False
    assert utils.is_call_sign(object) is False
    assert utils.is_call_sign('') is False
    assert utils.is_call_sign('1') is False
    assert utils.is_call_sign('12') is False
    assert utils.is_call_sign('abc') is False
    assert utils.is_call_sign('+()') is False
    assert utils.is_call_sign('+') is False
    assert utils.is_call_sign(None) is False
    assert utils.is_call_sign(42) is False

    # To short or 2 long
    assert utils.is_call_sign('DF1AB') is False
    assert utils.is_call_sign('DF1ABCX') is False
    assert utils.is_call_sign('DF1ABCEFG') is False
    assert utils.is_call_sign('1ABCX') is False
    # 4th character is not an number
    assert utils.is_call_sign('XXXXXX') is False

    # Some valid checks
    result = utils.is_call_sign('DF1ABC')
    assert isinstance(result, dict)
    assert 'DF1ABC' == result['callsign']
    assert '' == result['ssid']

    # Get our SSID
    result = utils.is_call_sign('DF1ABC-14')
    assert 'DF1ABC' == result['callsign']
    assert '-14' == result['ssid']


def test_is_phone_no():
    """
    API: is_phone_no() function

    """
    # Invalid numbers
    assert utils.is_phone_no(None) is False
    assert utils.is_phone_no(42) is False
    assert utils.is_phone_no(object) is False
    assert utils.is_phone_no('') is False
    assert utils.is_phone_no('1') is False
    assert utils.is_phone_no('12') is False
    assert utils.is_phone_no('abc') is False
    assert utils.is_phone_no('+()') is False
    assert utils.is_phone_no('+') is False
    assert utils.is_phone_no(None) is False
    assert utils.is_phone_no(42) is False
    assert utils.is_phone_no(object, min_len=0) is False
    assert utils.is_phone_no('', min_len=1) is False
    assert utils.is_phone_no('abc', min_len=0) is False
    assert utils.is_phone_no('', min_len=0) is False

    # Ambigious, but will document it here in this test as such
    results = utils.is_phone_no('+((()))--+', min_len=0)
    assert '' == results['country']
    assert '' == results['area']
    assert '' == results['line']
    assert '' == results['pretty']
    assert '' == results['full']

    # Valid phone numbers
    assert utils.is_phone_no('+(0)') is False
    results = utils.is_phone_no('+(0)', min_len=1)
    assert '' == results['country']
    assert '' == results['area']
    assert '0' == results['line']
    assert '0' == results['pretty']
    assert '0' == results['full']

    assert utils.is_phone_no('1') is False
    results = utils.is_phone_no('1', min_len=1)
    assert '' == results['country']
    assert '' == results['area']
    assert '1' == results['line']
    assert '1' == results['pretty']
    assert '1' == results['full']

    assert utils.is_phone_no('12') is False
    results = utils.is_phone_no('12', min_len=2)
    assert '' == results['country']
    assert '' == results['area']
    assert '12' == results['line']
    assert '12' == results['pretty']
    assert '12' == results['full']

    assert utils.is_phone_no('911') is False
    results = utils.is_phone_no('911', min_len=3)
    assert isinstance(results, dict)
    assert '' == results['country']
    assert '' == results['area']
    assert '911' == results['line']
    assert '911' == results['pretty']
    assert '911' == results['full']

    assert utils.is_phone_no('1234') is False
    results = utils.is_phone_no('1234', min_len=4)
    assert isinstance(results, dict)
    assert '' == results['country']
    assert '' == results['area']
    assert '1234' == results['line']
    assert '1234' == results['pretty']
    assert '1234' == results['full']

    assert utils.is_phone_no('12345') is False
    results = utils.is_phone_no('12345', min_len=5)
    assert isinstance(results, dict)
    assert '' == results['country']
    assert '' == results['area']
    assert '12345' == results['line']
    assert '12345' == results['pretty']
    assert '12345' == results['full']

    assert utils.is_phone_no('123456') is False
    results = utils.is_phone_no('123456', min_len=6)
    assert isinstance(results, dict)
    assert '' == results['country']
    assert '' == results['area']
    assert '123456' == results['line']
    assert '123456' == results['pretty']
    assert '123456' == results['full']

    # at 7 digits, the format hyphenates in the `pretty` section
    assert utils.is_phone_no('1234567') is False
    results = utils.is_phone_no('1234567', min_len=7)
    assert isinstance(results, dict)
    assert '' == results['country']
    assert '' == results['area']
    assert '1234567' == results['line']
    assert '123-4567' == results['pretty']
    assert '1234567' == results['full']

    results = utils.is_phone_no('1(800) 123-4567')
    assert isinstance(results, dict)
    assert '1' == results['country']
    assert '800' == results['area']
    assert '1234567' == results['line']
    assert '+1 800-123-4567' == results['pretty']
    assert '18001234567' == results['full']


def test_parse_call_sign():
    """utils: parse_call_sign() testing """
    # A simple single array entry (As str)
    results = utils.parse_call_sign('')
    assert isinstance(results, list)
    assert len(results) == 0

    # just delimeters
    results = utils.parse_call_sign(',  ,, , ,,, ')
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_call_sign(None)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_call_sign(42)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_call_sign('this is not a parseable call sign at all')
    assert isinstance(results, list)
    assert len(results) == 9

    results = utils.parse_call_sign(
        'this is not a parseable call sign at all', store_unparseable=False)
    assert isinstance(results, list)
    assert len(results) == 0

    # Now test valid call signs
    results = utils.parse_call_sign('0A1DEF')
    assert isinstance(results, list)
    assert len(results) == 1
    assert '0A1DEF' in results

    results = utils.parse_call_sign('0A1DEF, DF1ABC')
    assert isinstance(results, list)
    assert len(results) == 2
    assert '0A1DEF' in results
    assert 'DF1ABC' in results


def test_parse_phone_no():
    """utils: parse_phone_no() testing """
    # A simple single array entry (As str)
    results = utils.parse_phone_no('')
    assert isinstance(results, list)
    assert len(results) == 0

    # just delimeters
    results = utils.parse_phone_no(',  ,, , ,,, ')
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_phone_no(',')
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_phone_no(None)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_phone_no(42)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_phone_no('this is not a parseable phoneno at all')
    assert isinstance(results, list)
    assert len(results) == 8
    # Now we do it again with the store_unparsable flag set to False
    results = utils.parse_phone_no(
        'this is not a parseable email at all', store_unparseable=False)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_phone_no('+', store_unparseable=False)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_phone_no('(', store_unparseable=False)
    assert isinstance(results, list)
    assert len(results) == 0

    # Number is too short
    results = utils.parse_phone_no('0', store_unparseable=False)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_phone_no('12', store_unparseable=False)
    assert isinstance(results, list)
    assert len(results) == 0

    # Now test valid phone numbers
    results = utils.parse_phone_no('+1 (124) 245 2345')
    assert isinstance(results, list)
    assert len(results) == 1
    assert '+1 (124) 245 2345' in results

    results = utils.parse_phone_no('911', store_unparseable=False)
    assert isinstance(results, list)
    assert len(results) == 1
    assert '911' in results

    results = utils.parse_phone_no(
        '911, 123-123-1234', store_unparseable=False)
    assert isinstance(results, list)
    assert len(results) == 2
    assert '911' in results
    assert '123-123-1234' in results

    # Space variations
    results = utils.parse_phone_no(' 911  , +1 (123) 123-1234')
    assert isinstance(results, list)
    assert len(results) == 2
    assert '911' in results
    assert '+1 (123) 123-1234' in results

    results = utils.parse_phone_no(' 911  , + 1 ( 123 ) 123-1234')
    assert isinstance(results, list)
    assert len(results) == 2
    assert '911' in results
    assert '+ 1 ( 123 ) 123-1234' in results


def test_parse_emails():
    """utils: parse_emails() testing """
    # A simple single array entry (As str)
    results = utils.parse_emails('')
    assert isinstance(results, list)
    assert len(results) == 0

    # just delimeters
    results = utils.parse_emails(',  ,, , ,,, ')
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_emails(',')
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_emails(None)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_emails(42)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_emails('this is not a parseable email at all')
    assert isinstance(results, list)
    assert len(results) == 8
    # Now we do it again with the store_unparsable flag set to False
    results = utils.parse_emails(
        'this is not a parseable email at all', store_unparseable=False)
    assert isinstance(results, list)
    assert len(results) == 0

    # Now test valid emails
    results = utils.parse_emails('user@example.com')
    assert isinstance(results, list)
    assert len(results) == 1
    assert 'user@example.com' in results

    results = utils.parse_emails('a@')
    assert isinstance(results, list)
    assert len(results) == 1
    assert 'a@' in results

    results = utils.parse_emails('user1@example.com user2@example.com')
    assert isinstance(results, list)
    assert len(results) == 2
    assert 'user1@example.com' in results
    assert 'user2@example.com' in results

    # Commas and spaces found inside URLs are ignored
    emails = [
        'user1@example.com,',
        'test1@example.com,,, abcd@example.com',
        'Chuck Norris roundhouse@kick.com',
        'David Spade dspade@example.com, Yours Truly yours@truly.com',
    ]

    results = utils.parse_emails(', '.join(emails))
    assert isinstance(results, list)
    assert len(results) == 6
    assert 'user1@example.com' in results
    assert 'test1@example.com' in results
    assert 'abcd@example.com' in results
    assert 'Chuck Norris roundhouse@kick.com' in results
    assert 'David Spade dspade@example.com' in results
    assert 'Yours Truly yours@truly.com' in results

    # Test triangle bracket parsing
    # Commas and spaces found inside URLs are ignored
    emails = [
        'User1 user1@example.com',
        'User 2 user2@example.com',
        'User Three <user3@example.com>',
        'The Forth User: <user4@example.com>',
        '5th User: user4@example.com',
    ]

    results = utils.parse_emails(', '.join(emails))
    assert isinstance(results, list)
    assert len(results) == len(emails)
    for email in emails:
        assert email in results

    # pass the entries in as a list
    results = utils.parse_emails(emails)
    assert isinstance(results, list)
    assert len(results) == len(emails)
    for email in emails:
        assert email in results

    # Pass in some unparseables
    results = utils.parse_emails('garbage')
    assert isinstance(results, list)
    assert len(results) == 1

    results = utils.parse_emails('garbage', store_unparseable=False)
    assert isinstance(results, list)
    assert len(results) == 0

    # Pass in garbage
    results = utils.parse_emails(object)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_emails(42)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_emails([None, object, 42])
    assert isinstance(results, list)
    assert len(results) == 0


def test_parse_urls():
    """utils: parse_urls() testing """
    # A simple single array entry (As str)
    results = utils.parse_urls('')
    assert isinstance(results, list)
    assert len(results) == 0

    # just delimeters
    results = utils.parse_urls(',  ,, , ,,, ')
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_urls(',')
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_urls(None)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_urls(42)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_urls('this is not a parseable url at all')
    assert isinstance(results, list)
    # we still end up returning this
    assert len(results) == 8

    results = utils.parse_urls(
        'this is not a parseable url at all', store_unparseable=False)
    assert isinstance(results, list)
    assert len(results) == 0

    # Now test valid URLs
    results = utils.parse_urls('windows://')
    assert isinstance(results, list)
    assert len(results) == 1
    assert 'windows://' in results

    results = utils.parse_urls('windows:// gnome://')
    assert isinstance(results, list)
    assert len(results) == 2
    assert 'windows://' in results
    assert 'gnome://' in results

    # We don't want to parse out URLs that are part of another URL's arguments
    results = utils.parse_urls('discord://host?url=https://localhost')
    assert isinstance(results, list)
    assert len(results) == 1
    assert 'discord://host?url=https://localhost' in results

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

    results = utils.parse_urls(', '.join(urls))
    assert isinstance(results, list)
    assert len(results) == len(urls)
    for url in urls:
        assert rstrip_re.sub('', url) in results

    # However if a comma is found at the end of a single url without a new
    # match to hit, it is saved and not lost

    # The comma at the end of the password will not be lost if we're
    # dealing with a single entry:
    url = 'http://hostname?password=,abcd,'
    results = utils.parse_urls(url)
    assert isinstance(results, list)
    assert len(results) == 1
    assert url in results

    # however if we have multiple entries, commas and spaces between
    # URLs will be lost, however the last URL will not lose the comma
    urls = [
        'schema1://hostname?password=,abcd,',
        'schema2://hostname?password=,abcd,',
    ]
    results = utils.parse_urls(', '.join(urls))
    assert isinstance(results, list)
    assert len(results) == len(urls)

    # No match because the comma is gone in the results entry
    # schema1://hostname?password=,abcd
    assert urls[0] not in results
    assert urls[0][:-1] in results

    # However we wouldn't have lost the comma in the second one:
    # schema2://hostname?password=,abcd,
    assert urls[1] in results

    # Pass the list in (as a list); results are the same
    results = utils.parse_urls(urls)
    assert isinstance(results, list)
    assert len(results) == len(urls)

    # Pass in garbage
    results = utils.parse_urls(object)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_urls(42)
    assert isinstance(results, list)
    assert len(results) == 0

    results = utils.parse_urls([None, object, 42])
    assert isinstance(results, list)
    assert len(results) == 0


def test_dict_full_update():
    """utils: dict_full_update() testing """
    dict_1 = {
        'a': 1,
        'b': 2,
        'c': 3,
        'd': {
            'z': 27,
            'y': 26,
            'x': 25,
        }
    }

    dict_2 = {
        'd': {
            'x': 'updated',
            'w': 24,
        },
        'c': 'updated',
        'e': 5,
    }
    utils.dict_full_update(dict_1, dict_2)
    # Dictionary 2 is untouched
    assert len(dict_2) == 3
    assert dict_2['c'] == 'updated'
    assert dict_2['d']['w'] == 24
    assert dict_2['d']['x'] == 'updated'
    assert dict_2['e'] == 5

    # Dictionary 3 however has entries from Dict 2 applied
    # without disrupting entries that were not matched.
    assert len(dict_1) == 5
    assert dict_1['a'] == 1
    assert dict_1['b'] == 2
    assert dict_1['c'] == 'updated'
    assert dict_1['d']['w'] == 24
    assert dict_1['d']['x'] == 'updated'
    assert dict_1['d']['y'] == 26
    assert dict_1['d']['z'] == 27
    assert dict_1['e'] == 5


def test_parse_list():
    """utils: parse_list() testing """

    # A simple single array entry (As str)
    results = utils.parse_list(
        '.mkv,.avi,.divx,.xvid,.mov,.wmv,.mp4,.mpg,.mpeg,.vob,.iso')

    assert results == sorted([
        '.divx', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.mpeg', '.vob',
        '.xvid', '.wmv', '.mp4',
    ])

    class StrangeObject:
        def __str__(self):
            return '.avi'

    # Now 2 lists with lots of duplicates and other delimiters
    results = utils.parse_list(
        '.mkv,.avi,.divx,.xvid,.mov,.wmv,.mp4,.mpg .mpeg,.vob,,; ;',
        ('.mkv,.avi,.divx,.xvid,.mov    ', '    .wmv,.mp4;.mpg,.mpeg,'),
        '.vob,.iso', ['.vob', ['.vob', '.mkv', StrangeObject(), ], ],
        StrangeObject())

    assert results == sorted([
        '.divx', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.mpeg', '.vob',
        '.xvid', '.wmv', '.mp4',
    ])

    # Garbage in is removed
    assert utils.parse_list(object(), 42, None) == []

    # Now a list with extras we want to add as strings
    # empty entries are removed
    results = utils.parse_list([
        '.divx', '.iso', '.mkv', '.mov', '', '  ', '.avi', '.mpeg', '.vob',
        '.xvid', '.mp4'], '.mov,.wmv,.mp4,.mpg')

    assert results == sorted([
        '.divx', '.wmv', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.vob',
        '.xvid', '.mpeg', '.mp4',
    ])


def test_module_detection(tmpdir):
    """utils: test_module_detection() testing
    """

    # Clear our working variables so they don't obstruct with the tests here
    utils.PATHS_PREVIOUSLY_SCANNED.clear()
    common.NOTIFY_CUSTOM_MODULE_MAP.clear()

    # Test case where we load invalid data
    utils.module_detection(None)

    # Invalid data does not load anything
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 0
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 0

    # Prepare ourselves a file to work with
    notify_hook_a_base = tmpdir.mkdir('a')
    notify_hook_a = notify_hook_a_base.join('hook.py')
    notify_hook_a.write(cleandoc("""
    from apprise.decorators import notify

    @notify(on="clihook")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        pass
    """))

    # Not previously loaded
    assert 'clihook' not in common.NOTIFY_SCHEMA_MAP

    # load entry by string
    utils.module_detection(str(notify_hook_a))

    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 1
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 1

    # Now loaded
    assert 'clihook' in common.NOTIFY_SCHEMA_MAP

    # load entry by array
    utils.module_detection([str(notify_hook_a)])

    # No changes to our path
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 1
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 1

    # Reset our variables for the next test
    utils.PATHS_PREVIOUSLY_SCANNED.clear()
    common.NOTIFY_CUSTOM_MODULE_MAP.clear()
    del common.NOTIFY_SCHEMA_MAP['clihook']

    # Hidden files are ignored
    notify_hook_b_base = tmpdir.mkdir('b')
    notify_hook_b = notify_hook_b_base.join('.hook.py')
    notify_hook_b.write(cleandoc("""
    from apprise.decorators import notify

    # this is in a hidden file so it will not load
    @notify(on="hidden")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        pass
    """))

    assert 'hidden' not in common.NOTIFY_SCHEMA_MAP

    utils.module_detection([str(notify_hook_b)])

    # Verify that it did not load
    assert 'hidden' not in common.NOTIFY_SCHEMA_MAP

    # Path was scanned; nothing loaded
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 1
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 0

    # Reset our variables for the next test
    utils.PATHS_PREVIOUSLY_SCANNED.clear()
    common.NOTIFY_CUSTOM_MODULE_MAP.clear()

    # modules with no hooks found are ignored
    notify_hook_c_base = tmpdir.mkdir('c')
    notify_hook_c = notify_hook_c_base.join('empty.py')
    notify_hook_c.write("")

    utils.module_detection([str(notify_hook_c)])

    # File was found, no custom modules
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 1
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 0

    # A new path scanned
    utils.module_detection([str(notify_hook_c_base)])
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 2
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 0

    def create_hook(tdir, cache=True, on="valid1"):
        """
        Just a temporary hook creation tool for writing a working notify hook
        """
        tdir.write(cleandoc("""
        from apprise.decorators import notify

        # this is a good hook but burried in hidden directory which won't
        # be accessed unless the file is pointed to via absolute path
        @notify(on="{}")
        def mywrapper(body, title, notify_type, *args, **kwargs):
            pass
        """.format(on)))

        utils.module_detection([str(tdir)], cache=cache)

    create_hook(notify_hook_c, on='valid1')
    assert 'valid1' not in common.NOTIFY_SCHEMA_MAP

    # Even if we correct our empty file; the fact the directory has been
    # scanned and failed to load (same with file), it won't be loaded
    # a second time. This is intentional since module_detection() get's
    # called for every AppriseAsset() object creation.  This prevents us
    # from reloading conent over and over again wasting resources
    assert 'valid1' not in common.NOTIFY_SCHEMA_MAP
    utils.module_detection([str(notify_hook_c)])
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 2
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 0

    # Even by absolute path...
    utils.module_detection([str(notify_hook_c)])
    assert 'valid1' not in common.NOTIFY_SCHEMA_MAP
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 2
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 0

    # However we can bypass the cache if we really want to
    utils.module_detection([str(notify_hook_c_base)], cache=False)
    assert 'valid1' in common.NOTIFY_SCHEMA_MAP
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 2
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 1

    # Bypassing it twice causes the module to load twice (not very efficient)
    # However we can bypass the cache if we really want to
    utils.module_detection([str(notify_hook_c_base)], cache=False)
    assert 'valid1' in common.NOTIFY_SCHEMA_MAP
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 2
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 1

    # If you update the module (corrupting it in the process and reload)
    notify_hook_c.write(cleandoc("""
    raise ValueError
    """))

    # Force no cache to cause the file to be replaced
    utils.module_detection([str(notify_hook_c_base)], cache=False)

    # Our valid entry is no longer loaded
    assert 'valid1' not in common.NOTIFY_SCHEMA_MAP

    # No change to scanned paths
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 2
    # The previously loaded module is now gone
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 0

    # Reload our valid1 entry
    create_hook(notify_hook_c, on='valid1', cache=False)
    assert 'valid1' in common.NOTIFY_SCHEMA_MAP
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 2
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 1

    # Prepare an empty file
    notify_hook_c.write("")
    utils.module_detection([str(notify_hook_c_base)], cache=False)

    # Our valid entry is no longer loaded
    assert 'valid1' not in common.NOTIFY_SCHEMA_MAP
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 2
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 0

    # Now reload our module again (this time rather then an exception, the
    # module is read back and swaps `valid1` for `valid2`
    create_hook(notify_hook_c, on='valid1', cache=False)
    assert 'valid1' in common.NOTIFY_SCHEMA_MAP
    assert 'valid2' not in common.NOTIFY_SCHEMA_MAP
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 2
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 1

    create_hook(notify_hook_c, on='valid2', cache=False)
    assert 'valid1' not in common.NOTIFY_SCHEMA_MAP
    assert 'valid2' in common.NOTIFY_SCHEMA_MAP
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 2
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 1

    # Reset our variables for the next test
    create_hook(notify_hook_c, on='valid1', cache=False)
    del common.NOTIFY_SCHEMA_MAP['valid1']
    utils.PATHS_PREVIOUSLY_SCANNED.clear()
    common.NOTIFY_CUSTOM_MODULE_MAP.clear()

    notify_hook_d = notify_hook_c_base.join('.ignore.py')
    notify_hook_d.write("")
    notify_hook_e_base = notify_hook_c_base.mkdir('.ignore')
    notify_hook_e = notify_hook_e_base.join('__init__.py')
    notify_hook_e.write(cleandoc("""
    from apprise.decorators import notify

    # this is a good hook but burried in hidden directory which won't
    # be accessed unless the file is pointed to via absolute path
    @notify(on="valid2")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        pass
    """))

    # Try to load our base directory again; this time we search by the
    # directory; the only edge case we're testing here is it will not
    # even look at the .ignore.py file found since it is invalid
    utils.module_detection([str(notify_hook_c_base)])
    assert 'valid1' in common.NOTIFY_SCHEMA_MAP
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 2
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 1

    # Reset our variables for the next test
    del common.NOTIFY_SCHEMA_MAP['valid1']
    utils.PATHS_PREVIOUSLY_SCANNED.clear()
    common.NOTIFY_CUSTOM_MODULE_MAP.clear()

    # Try to load our base directory again
    utils.module_detection([str(notify_hook_c)])
    assert 'valid1' in common.NOTIFY_SCHEMA_MAP

    # Hidden directories are not scanned
    assert 'valid2' not in common.NOTIFY_SCHEMA_MAP

    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 1
    assert str(notify_hook_c) in utils.PATHS_PREVIOUSLY_SCANNED
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 1

    # However a direct reference to the hidden directory is okay
    utils.module_detection([str(notify_hook_e_base)])

    # We loaded our module
    assert 'valid2' in common.NOTIFY_SCHEMA_MAP
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 3
    assert str(notify_hook_c) in utils.PATHS_PREVIOUSLY_SCANNED
    assert str(notify_hook_e) in utils.PATHS_PREVIOUSLY_SCANNED
    assert str(notify_hook_e_base) in utils.PATHS_PREVIOUSLY_SCANNED
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 2

    # Reset our variables for the next test
    del common.NOTIFY_SCHEMA_MAP['valid1']
    del common.NOTIFY_SCHEMA_MAP['valid2']
    utils.PATHS_PREVIOUSLY_SCANNED.clear()
    common.NOTIFY_CUSTOM_MODULE_MAP.clear()

    # Load our file directly
    assert 'valid2' not in common.NOTIFY_SCHEMA_MAP
    utils.module_detection([str(notify_hook_e)])

    # Now we have it loaded as expected
    assert 'valid2' in common.NOTIFY_SCHEMA_MAP
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 1
    assert str(notify_hook_e) in utils.PATHS_PREVIOUSLY_SCANNED
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 1

    # however if we try to load the base directory where the __init__.py
    # was already loaded from, it will not change anything
    utils.module_detection([str(notify_hook_e_base)])
    assert 'valid2' in common.NOTIFY_SCHEMA_MAP
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 2
    assert str(notify_hook_e) in utils.PATHS_PREVIOUSLY_SCANNED
    assert str(notify_hook_e_base) in utils.PATHS_PREVIOUSLY_SCANNED
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 1

    # Tidy up for the next test
    del common.NOTIFY_SCHEMA_MAP['valid2']
    utils.PATHS_PREVIOUSLY_SCANNED.clear()
    common.NOTIFY_CUSTOM_MODULE_MAP.clear()

    assert 'valid1' not in common.NOTIFY_SCHEMA_MAP
    assert 'valid2' not in common.NOTIFY_SCHEMA_MAP
    assert 'valid3' not in common.NOTIFY_SCHEMA_MAP
    notify_hook_f_base = tmpdir.mkdir('f')
    notify_hook_f = notify_hook_f_base.join('invalid.py')
    notify_hook_f.write(cleandoc("""
    from apprise.decorators import notify

    # A very invalid hook type... on should not be None
    @notify(on=None)
    def mywrapper(body, title, notify_type, *args, **kwargs):
        pass

    # An invalid name
    @notify(on='valid1', name=None)
    def mywrapper(body, title, notify_type, *args, **kwargs):
        pass

    # Another invalid name (so it's ignored)
    @notify(on='valid2', name=object)
    def mywrapper(body, title, notify_type, *args, **kwargs):
        pass

    # Simply put... the name has to be a string to be referenced
    # however this will still be loaded
    @notify(on='valid3', name=4)
    def mywrapper(body, title, notify_type, *args, **kwargs):
        pass

    """))

    utils.module_detection([str(notify_hook_f)])

    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 1
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 1
    assert 'valid1' in common.NOTIFY_SCHEMA_MAP
    assert 'valid2' in common.NOTIFY_SCHEMA_MAP
    assert 'valid3' in common.NOTIFY_SCHEMA_MAP

    # Reset our variables for the next test
    del common.NOTIFY_SCHEMA_MAP['valid1']
    del common.NOTIFY_SCHEMA_MAP['valid2']
    del common.NOTIFY_SCHEMA_MAP['valid3']
    utils.PATHS_PREVIOUSLY_SCANNED.clear()
    common.NOTIFY_CUSTOM_MODULE_MAP.clear()

    # Now test the handling of just bad data entirely
    notify_hook_g_base = tmpdir.mkdir('g')
    notify_hook_g = notify_hook_g_base.join('binary.py')
    with open(str(notify_hook_g), 'wb') as fout:
        fout.write(os.urandom(512))

    utils.module_detection([str(notify_hook_g)])
    assert len(utils.PATHS_PREVIOUSLY_SCANNED) == 1
    assert len(common.NOTIFY_CUSTOM_MODULE_MAP) == 0

    # Reset our variables before we leave
    utils.PATHS_PREVIOUSLY_SCANNED.clear()
    common.NOTIFY_CUSTOM_MODULE_MAP.clear()


def test_exclusive_match():
    """utils: is_exclusive_match() testing
    """

    # No Logic always returns True if there is also no data
    assert utils.is_exclusive_match(data=None, logic=None) is True
    assert utils.is_exclusive_match(data=None, logic=set()) is True
    assert utils.is_exclusive_match(data='', logic=set()) is True
    assert utils.is_exclusive_match(data=u'', logic=set()) is True

    # however, once data is introduced, True is no longer returned
    # if no logic has been specified
    assert utils.is_exclusive_match(data=u'check', logic=set()) is False
    assert utils.is_exclusive_match(
        data=['check', 'checkb'], logic=set()) is False

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

    # match_all matches everything
    assert utils.is_exclusive_match(logic='all', data=data) is True
    assert utils.is_exclusive_match(logic=['all'], data=data) is True

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

    #
    # Empty data set
    #
    data = set()
    assert utils.is_exclusive_match(logic=['www'], data=data) is False
    assert utils.is_exclusive_match(logic='all', data=data) is True

    #
    # Update our data set so we can do more advance checks
    #
    data = set(['always', 'entry1'])
    # We'll always match on the with keyword always
    assert utils.is_exclusive_match(logic='always', data=data) is True
    assert utils.is_exclusive_match(logic='garbage', data=data) is True
    # However we will not match if we turn this feature off
    assert utils.is_exclusive_match(
        logic='garbage', data=data, match_always=False) is False

    # Change default value from 'all' to 'match_me'. Logic matches
    # so we pass
    assert utils.is_exclusive_match(
        logic='match_me', data=data, match_all='match_me') is True


def test_apprise_validate_regex():
    """
    API: Apprise() Validate Regex tests

    """
    assert utils.validate_regex(None) is None
    assert utils.validate_regex(object) is None
    assert utils.validate_regex(42) is None
    assert utils.validate_regex("") is None
    assert utils.validate_regex("  ") is None
    assert utils.validate_regex("abc") == "abc"

    # value is a keyword that is extracted (if found)
    assert utils.validate_regex(
        "- abcd -", r'-(?P<value>[^-]+)-', fmt="{value}") == "abcd"
    assert utils.validate_regex(
        "- abcd -", r'-(?P<value>[^-]+)-', strip=False,
        fmt="{value}") == " abcd "

    # String flags supported in addition to numeric
    assert utils.validate_regex(
        "- abcd -", r'-(?P<value>[^-]+)-', 'i', fmt="{value}") == "abcd"
    assert utils.validate_regex(
        "- abcd -", r'-(?P<value>[^-]+)-', re.I, fmt="{value}") == "abcd"

    # Test multiple flag settings
    assert utils.validate_regex(
        "- abcd -", r'-(?P<value>[^-]+)-', 'isax', fmt="{value}") == "abcd"

    # Invalid flags are just ignored. The below fails to match
    # because the default value of 'i' is over-ridden by what is
    # identfied below, and no flag is set at the end of the day
    assert utils.validate_regex(
        "- abcd -", r'-(?P<value>[ABCD]+)-', '-%2gb', fmt="{value}") is None
    assert utils.validate_regex(
        "- abcd -", r'-(?P<value>[ABCD]+)-', '', fmt="{value}") is None
    assert utils.validate_regex(
        "- abcd -", r'-(?P<value>[ABCD]+)-', None, fmt="{value}") is None


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


def test_apply_templating():
    """utils: apply_template() testing
    """

    template = "Hello {{fname}}, How are you {{whence}}?"

    result = utils.apply_template(
        template, **{'fname': 'Chris', 'whence': 'this morning'})
    assert isinstance(result, str) is True
    assert result == "Hello Chris, How are you this morning?"

    # In this example 'whence' isn't provided, so it isn't swapped
    result = utils.apply_template(
        template, **{'fname': 'Chris'})
    assert isinstance(result, str) is True
    assert result == "Hello Chris, How are you {{whence}}?"

    # white space won't cause any ill affects:
    template = "Hello {{ fname }}, How are you {{   whence}}?"
    result = utils.apply_template(
        template, **{'fname': 'Chris', 'whence': 'this morning'})
    assert isinstance(result, str) is True
    assert result == "Hello Chris, How are you this morning?"

    # No arguments won't cause any problems
    template = "Hello {{fname}}, How are you {{whence}}?"
    result = utils.apply_template(template)
    assert isinstance(result, str) is True
    assert result == template

    # Wrong elements are simply ignored
    result = utils.apply_template(
        template,
        **{'fname': 'l2g', 'whence': 'this evening', 'ignore': 'me'})
    assert isinstance(result, str) is True
    assert result == "Hello l2g, How are you this evening?"

    # Empty template makes things easy
    result = utils.apply_template(
        "", **{'fname': 'l2g', 'whence': 'this evening'})
    assert isinstance(result, str) is True
    assert result == ""

    # Regular expressions are safely escapped and act as normal
    # tokens:
    template = "Hello {{.*}}, How are you {{[A-Z0-9]+}}?"
    result = utils.apply_template(
        template, **{'.*': 'l2g', '[A-Z0-9]+': 'this afternoon'})
    assert result == "Hello l2g, How are you this afternoon?"

    # JSON is handled too such as escaping quotes
    template = '{value: "{{ value }}"}'
    result = utils.apply_template(
        template, app_mode=utils.TemplateType.JSON,
        **{'value': '"quotes are escaped"'})
    assert result == '{value: "\\"quotes are escaped\\""}'


def test_cwe312_word():
    """utils: cwe312_word() testing
    """
    assert utils.cwe312_word(None) is None
    assert utils.cwe312_word(42) == 42
    assert utils.cwe312_word('') == ''
    assert utils.cwe312_word(' ') == ' '
    assert utils.cwe312_word('!') == '!'

    assert utils.cwe312_word('a') == 'a'
    assert utils.cwe312_word('ab') == 'ab'
    assert utils.cwe312_word('abc') == 'abc'
    assert utils.cwe312_word('abcd') == 'abcd'
    assert utils.cwe312_word('abcd', force=True) == 'a...d'

    assert utils.cwe312_word('abc--d') == 'abc--d'
    assert utils.cwe312_word('a-domain.ca') == 'a...a'

    # Variances to still catch domain
    assert utils.cwe312_word('a-domain.ca', advanced=False) == 'a-domain.ca'
    assert utils.cwe312_word('a-domain.ca', threshold=6) == 'a-domain.ca'


def test_cwe312_url():
    """utils: cwe312_url() testing
    """
    assert utils.cwe312_url(None) is None
    assert utils.cwe312_url(42) == 42
    assert utils.cwe312_url('http://') == 'http://'
    assert utils.cwe312_url('discord://') == 'discord://'
    assert utils.cwe312_url('path') == 'http://path'
    assert utils.cwe312_url('path/') == 'http://path/'

    # Now test http:// private data
    assert utils.cwe312_url(
        'http://user:pass123@localhost') == 'http://user:p...3@localhost'
    assert utils.cwe312_url(
        'http://user@localhost') == 'http://user@localhost'
    assert utils.cwe312_url(
        'http://user@localhost?password=abc123') == \
        'http://user@localhost?password=a...3'
    assert utils.cwe312_url(
        'http://user@localhost?secret=secret-.12345') == \
        'http://user@localhost?secret=s...5'

    # Now test other:// private data
    assert utils.cwe312_url(
        'gitter://b5637831f563aa846bb5b2c27d8fe8f633b8f026/apprise') == \
        'gitter://b...6/apprise'
    assert utils.cwe312_url(
        'gitter://b5637831f563aa846bb5b2c27d8fe8f633b8f026'
        '/apprise/?pass=abc123') == \
        'gitter://b...6/apprise/?pass=a...3'

    assert utils.cwe312_url(
        'slack://mybot@xoxb-43598234231-3248932482278-BZK5Wj15B9mPh1RkShJoCZ44'
        '/lead2gold@gmail.com') == 'slack://mybot@x...4/l...m'
    assert utils.cwe312_url(
        'slack://test@B4QP3WWB4/J3QWT41JM/XIl2ffpqXkzkwMXrJdevi7W3/'
        '#random') == 'slack://test@B...4/J...M/X...3/'
