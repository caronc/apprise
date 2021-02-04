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
import mock
import requests
from json import dumps
from apprise.plugins.NotifyFCM.oauth import GoogleOAuth

# Test files for KeyFile Directory
PRIVATE_KEYFILE_DIR = os.path.join(os.path.dirname(__file__), 'var', 'fcm')


@mock.patch('requests.post')
def test_fcm_keyfile_parse(mock_post):
    """
    API: NotifyFCM() KeyFile Tests
    """

    # Prepare a good response
    response = mock.Mock()
    response.content = dumps({
        "access_token": "ya29.c.abcd",
        "expires_in": 3599,
        "token_type": "Bearer",
    })
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    path = os.path.join(PRIVATE_KEYFILE_DIR, 'service_account.json')
    oauth = GoogleOAuth()
    assert oauth.load(path) is True
    assert oauth.access_token is not None

    # Test our call count
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'https://accounts.google.com/o/oauth2/token'

    mock_post.reset_mock()
    # a second call uses cache since our token hasn't expired yet
    assert oauth.access_token is not None
    assert mock_post.call_count == 0
