"""API properties.

"""

from __future__ import print_function
from __future__ import unicode_literals
from urllib import unquote
from apprise import utils


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

    # Test Passwords with question marks ?; not supported
    result = utils.parse_url(
        'http://user:pass.with.?question@host'
    )
    assert(result is None)


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


def test_parse_list():
    "utils: parse_list() testing """

    # A simple single array entry (As str)
    results = utils.parse_list(
        '.mkv,.avi,.divx,.xvid,.mov,.wmv,.mp4,.mpg,.mpeg,.vob,.iso')

    assert(results == [
        '.divx', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.mpeg', '.vob',
        '.xvid', '.wmv', '.mp4',
    ])

    # Now 2 lists with lots of duplicates and other delimiters
    results = utils.parse_list(
        '.mkv,.avi,.divx,.xvid,.mov,.wmv,.mp4,.mpg .mpeg,.vob,,; ;',
        '.mkv,.avi,.divx,.xvid,.mov        .wmv,.mp4;.mpg,.mpeg,'
        '.vob,.iso')

    assert(results == [
        '.divx', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.mpeg', '.vob',
        '.xvid', '.wmv', '.mp4',
    ])

    # Now a list with extras we want to add as strings
    # empty entries are removed
    results = utils.parse_list([
        '.divx', '.iso', '.mkv', '.mov', '', '  ', '.avi', '.mpeg', '.vob',
        '.xvid', '.mp4'], '.mov,.wmv,.mp4,.mpg')

    assert(results == [
        '.divx', '.wmv', '.iso', '.mkv', '.mov', '.mpg', '.avi', '.vob',
        '.xvid', '.mpeg', '.mp4',
    ])
