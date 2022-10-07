# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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
from unittest import mock

from json import dumps
from apprise import Apprise
from apprise import plugins
import requests
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    # Insecure Request; no hostname specified
    ('emby://', {
        'instance': None,
    }),
    # Secure Emby Request; no hostname specified
    ('embys://', {
        'instance': None,
    }),
    # No user specified
    ('emby://localhost', {
        # Missing a username
        'instance': TypeError,
    }),
    ('emby://:@/', {
        'instance': None,
    }),
    # Valid Authentication
    ('emby://l2g@localhost', {
        'instance': plugins.NotifyEmby,
        # our response will be False because our authentication can't be
        # tested very well using this matrix.
        'response': False,
    }),
    ('embys://l2g:password@localhost', {
        'instance': plugins.NotifyEmby,
        # our response will be False because our authentication can't be
        # tested very well using this matrix.
        'response': False,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'embys://l2g:****@localhost',
    }),
)


def test_plugin_template_urls():
    """
    NotifyTemplate() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('apprise.plugins.NotifyEmby.sessions')
@mock.patch('apprise.plugins.NotifyEmby.login')
@mock.patch('apprise.plugins.NotifyEmby.logout')
@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_emby_general(mock_post, mock_get, mock_logout,
                             mock_login, mock_sessions):
    """
    NotifyEmby General Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    req = requests.Request()
    req.status_code = requests.codes.ok
    req.content = ''
    mock_get.return_value = req
    mock_post.return_value = req

    # This is done so we don't obstruct our access_token and user_id values
    mock_login.return_value = True
    mock_logout.return_value = True
    mock_sessions.return_value = {'abcd': {}}

    obj = Apprise.instantiate('emby://l2g:l2gpass@localhost?modal=False')
    assert isinstance(obj, plugins.NotifyEmby)
    assert obj.notify('title', 'body', 'info') is True
    obj.access_token = 'abc'
    obj.user_id = '123'

    # Test Modal support
    obj = Apprise.instantiate('emby://l2g:l2gpass@localhost?modal=True')
    assert isinstance(obj, plugins.NotifyEmby)
    assert obj.notify('title', 'body', 'info') is True
    obj.access_token = 'abc'
    obj.user_id = '123'

    # Test our exception handling
    for _exception in AppriseURLTester.req_exceptions:
        mock_post.side_effect = _exception
        mock_get.side_effect = _exception
        # We'll fail to log in each time
        assert obj.notify('title', 'body', 'info') is False

    # Disable Exceptions
    mock_post.side_effect = None
    mock_get.side_effect = None

    # Our login flat out fails if we don't have proper parseable content
    mock_post.return_value.content = u''
    mock_get.return_value.content = mock_post.return_value.content

    # KeyError handling
    mock_post.return_value.status_code = 999
    mock_get.return_value.status_code = 999
    assert obj.notify('title', 'body', 'info') is False

    # General Internal Server Error
    mock_post.return_value.status_code = requests.codes.internal_server_error
    mock_get.return_value.status_code = requests.codes.internal_server_error
    assert obj.notify('title', 'body', 'info') is False

    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok
    mock_get.return_value.content = mock_post.return_value.content

    # Disable the port completely
    obj.port = None
    assert obj.notify('title', 'body', 'info') is True

    # An Empty return set (no query is made, but notification will still
    # succeed
    mock_sessions.return_value = {}
    assert obj.notify('title', 'body', 'info') is True

    # Tidy our object
    del obj


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_emby_login(mock_post, mock_get):
    """
    NotifyEmby() login()

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare Mock
    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()

    obj = Apprise.instantiate('emby://l2g:l2gpass@localhost')
    assert isinstance(obj, plugins.NotifyEmby)

    # Test our exception handling
    for _exception in AppriseURLTester.req_exceptions:
        mock_post.side_effect = _exception
        mock_get.side_effect = _exception
        # We'll fail to log in each time
        assert obj.login() is False

    # Disable Exceptions
    mock_post.side_effect = None
    mock_get.side_effect = None

    # Our login flat out fails if we don't have proper parseable content
    mock_post.return_value.content = u''
    mock_get.return_value.content = mock_post.return_value.content

    # KeyError handling
    mock_post.return_value.status_code = 999
    mock_get.return_value.status_code = 999
    assert obj.login() is False

    # General Internal Server Error
    mock_post.return_value.status_code = requests.codes.internal_server_error
    mock_get.return_value.status_code = requests.codes.internal_server_error
    assert obj.login() is False

    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok

    obj = Apprise.instantiate('emby://l2g:l2gpass@localhost:1234')
    # Set a different port (outside of default)
    assert isinstance(obj, plugins.NotifyEmby)
    assert obj.port == 1234

    # The login will fail because '' is not a parseable JSON response
    assert obj.login() is False

    # Disable the port completely
    obj.port = None
    assert obj.login() is False

    # Default port assignments
    obj = Apprise.instantiate('emby://l2g:l2gpass@localhost')
    assert isinstance(obj, plugins.NotifyEmby)
    assert obj.port == 8096

    # The login will (still) fail because '' is not a parseable JSON response
    assert obj.login() is False

    # Our login flat out fails if we don't have proper parseable content
    mock_post.return_value.content = dumps({
        u'AccessToken': u'0000-0000-0000-0000',
    })
    mock_get.return_value.content = mock_post.return_value.content

    obj = Apprise.instantiate('emby://l2g:l2gpass@localhost')
    assert isinstance(obj, plugins.NotifyEmby)

    # The login will fail because the 'User' or 'Id' field wasn't parsed
    assert obj.login() is False

    # Our text content (we intentionally reverse the 2 locations
    # that store the same thing; we do this so we can test which
    # one it defaults to if both are present
    mock_post.return_value.content = dumps({
        u'User': {
            u'Id': u'abcd123',
        },
        u'Id': u'123abc',
        u'AccessToken': u'0000-0000-0000-0000',
    })
    mock_get.return_value.content = mock_post.return_value.content

    obj = Apprise.instantiate('emby://l2g:l2gpass@localhost')
    assert isinstance(obj, plugins.NotifyEmby)

    # Login
    assert obj.login() is True
    assert obj.user_id == '123abc'
    assert obj.access_token == '0000-0000-0000-0000'

    # We're going to log in a second time which checks that we logout
    # first before logging in again. But this time we'll scrap the
    # 'Id' area and use the one found in the User area if detected
    mock_post.return_value.content = dumps({
        u'User': {
            u'Id': u'abcd123',
        },
        u'AccessToken': u'0000-0000-0000-0000',
    })
    mock_get.return_value.content = mock_post.return_value.content

    # Login
    assert obj.login() is True
    assert obj.user_id == 'abcd123'
    assert obj.access_token == '0000-0000-0000-0000'


@mock.patch('apprise.plugins.NotifyEmby.login')
@mock.patch('apprise.plugins.NotifyEmby.logout')
@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_emby_sessions(mock_post, mock_get, mock_logout, mock_login):
    """
    NotifyEmby() sessions()

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare Mock
    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()

    # This is done so we don't obstruct our access_token and user_id values
    mock_login.return_value = True
    mock_logout.return_value = True

    obj = Apprise.instantiate('emby://l2g:l2gpass@localhost')
    assert isinstance(obj, plugins.NotifyEmby)
    obj.access_token = 'abc'
    obj.user_id = '123'

    # Test our exception handling
    for _exception in AppriseURLTester.req_exceptions:
        mock_post.side_effect = _exception
        mock_get.side_effect = _exception
        # We'll fail to log in each time
        sessions = obj.sessions()
        assert isinstance(sessions, dict) is True
        assert len(sessions) == 0

    # Disable Exceptions
    mock_post.side_effect = None
    mock_get.side_effect = None

    # Our login flat out fails if we don't have proper parseable content
    mock_post.return_value.content = u''
    mock_get.return_value.content = mock_post.return_value.content

    # KeyError handling
    mock_post.return_value.status_code = 999
    mock_get.return_value.status_code = 999
    sessions = obj.sessions()
    assert isinstance(sessions, dict) is True
    assert len(sessions) == 0

    # General Internal Server Error
    mock_post.return_value.status_code = requests.codes.internal_server_error
    mock_get.return_value.status_code = requests.codes.internal_server_error
    sessions = obj.sessions()
    assert isinstance(sessions, dict) is True
    assert len(sessions) == 0

    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok
    mock_get.return_value.content = mock_post.return_value.content

    # Disable the port completely
    obj.port = None

    sessions = obj.sessions()
    assert isinstance(sessions, dict) is True
    assert len(sessions) == 0

    # Let's get some results
    mock_post.return_value.content = dumps([
        {
            u'Id': u'abc123',
        },
        {
            u'Id': u'def456',
        },
        {
            u'InvalidEntry': None,
        },
    ])
    mock_get.return_value.content = mock_post.return_value.content

    sessions = obj.sessions(user_controlled=True)
    assert isinstance(sessions, dict) is True
    assert len(sessions) == 2

    # Test it without setting user-controlled sessions
    sessions = obj.sessions(user_controlled=False)
    assert isinstance(sessions, dict) is True
    assert len(sessions) == 2

    # Triggers an authentication failure
    obj.user_id = None
    mock_login.return_value = False
    sessions = obj.sessions()
    assert isinstance(sessions, dict) is True
    assert len(sessions) == 0


@mock.patch('apprise.plugins.NotifyEmby.login')
@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_emby_logout(mock_post, mock_get, mock_login):
    """
    NotifyEmby() logout()

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare Mock
    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()

    # This is done so we don't obstruct our access_token and user_id values
    mock_login.return_value = True

    obj = Apprise.instantiate('emby://l2g:l2gpass@localhost')
    assert isinstance(obj, plugins.NotifyEmby)
    obj.access_token = 'abc'
    obj.user_id = '123'

    # Test our exception handling
    for _exception in AppriseURLTester.req_exceptions:
        mock_post.side_effect = _exception
        mock_get.side_effect = _exception
        # We'll fail to log in each time
        obj.logout()
        obj.access_token = 'abc'
        obj.user_id = '123'

    # Disable Exceptions
    mock_post.side_effect = None
    mock_get.side_effect = None

    # Our login flat out fails if we don't have proper parseable content
    mock_post.return_value.content = u''
    mock_get.return_value.content = mock_post.return_value.content

    # KeyError handling
    mock_post.return_value.status_code = 999
    mock_get.return_value.status_code = 999
    obj.logout()
    obj.access_token = 'abc'
    obj.user_id = '123'

    # General Internal Server Error
    mock_post.return_value.status_code = requests.codes.internal_server_error
    mock_get.return_value.status_code = requests.codes.internal_server_error
    obj.logout()
    obj.access_token = 'abc'
    obj.user_id = '123'

    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok
    mock_get.return_value.content = mock_post.return_value.content

    # Disable the port completely
    obj.port = None

    # Perform logout
    obj.logout()

    # Calling logout on an object already logged out
    obj.logout()

    # Test Python v3.5 LookupError Bug: https://bugs.python.org/issue29288
    mock_post.side_effect = LookupError()
    mock_get.side_effect = LookupError()
    obj.access_token = 'abc'
    obj.user_id = '123'

    # Tidy object
    del obj
