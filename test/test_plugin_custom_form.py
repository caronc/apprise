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
import os
import sys
import mock
import requests
from apprise import plugins
from helpers import AppriseURLTester
from apprise import Apprise
from apprise import NotifyType
from apprise import AppriseAttachment

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('form://:@/', {
        'instance': None,
    }),
    ('form://', {
        'instance': None,
    }),
    ('forms://', {
        'instance': None,
    }),
    ('form://localhost', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user@localhost?method=invalid', {
        'instance': TypeError,
    }),
    ('form://user:pass@localhost', {
        'instance': plugins.NotifyForm,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'form://user:****@localhost',
    }),
    ('form://user@localhost', {
        'instance': plugins.NotifyForm,
    }),

    # Test method variations
    ('form://user@localhost?method=put', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user@localhost?method=get', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user@localhost?method=post', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user@localhost?method=head', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user@localhost?method=delete', {
        'instance': plugins.NotifyForm,
    }),

    # Custom payload options
    ('form://localhost:8080?:key=value&:key2=value2', {
        'instance': plugins.NotifyForm,
    }),

    # Continue testing other cases
    ('form://localhost:8080', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user:pass@localhost:8080', {
        'instance': plugins.NotifyForm,
    }),
    ('forms://localhost', {
        'instance': plugins.NotifyForm,
    }),
    ('forms://user:pass@localhost', {
        'instance': plugins.NotifyForm,
    }),
    ('forms://localhost:8080/path/', {
        'instance': plugins.NotifyForm,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'forms://localhost:8080/path/',
    }),
    ('forms://user:password@localhost:8080', {
        'instance': plugins.NotifyForm,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'forms://user:****@localhost:8080',
    }),
    ('form://localhost:8080/path?-HeaderKey=HeaderValue', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user:pass@localhost:8081', {
        'instance': plugins.NotifyForm,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('form://user:pass@localhost:8082', {
        'instance': plugins.NotifyForm,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('form://user:pass@localhost:8083', {
        'instance': plugins.NotifyForm,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_custom_form_urls():
    """
    NotifyForm() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_custom_form_attachments(mock_post):
    """
    NotifyForm() Attachments

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    obj = Apprise.instantiate(
        'form://user@localhost.localdomain/?method=post')
    assert isinstance(obj, plugins.NotifyForm)

    # Test Valid Attachment
    path = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    attach = AppriseAttachment(path)
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Test invalid attachment
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=path) is False

    mock_post.return_value = None
    mock_post.side_effect = OSError()
    # We can't send the message if we can't read the attachment
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    # Get a appropriate "builtin" module name for pythons 2/3.
    if sys.version_info.major >= 3:
        builtin_open_function = 'builtins.open'

    else:
        builtin_open_function = '__builtin__.open'

    # Test Valid Attachment (load 3)
    path = (
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
    )
    attach = AppriseAttachment(path)

    # Return our good configuration
    mock_post.side_effect = None
    mock_post.return_value = okay_response
    with mock.patch(builtin_open_function, side_effect=OSError()):
        # We can't send the message we can't open the attachment for reading
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

    # Fail on the 2nd attempt (but not the first)
    with mock.patch(builtin_open_function,
                    side_effect=[None, OSError(), None]):
        # We can't send the message we can't open the attachment for reading
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

    # Test file exception handling when performing post
    mock_post.return_value = None
    mock_post.side_effect = OSError()
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False
