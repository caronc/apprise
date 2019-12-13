# -*- coding: utf-8 -*-
#
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

import six
import mock
import requests
from apprise import plugins

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


@mock.patch('requests.post')
def test_nextcloud_empty_body(mock_post):
    """
    API: NotifyNextcloud() empty body

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # A response
    robj = mock.Mock()
    robj.content = ''
    robj.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = robj

    # Variation Initializations
    obj = plugins.NotifyNextcloud(
        host="localhost", user="admin", password="pass", targets="user")
    assert isinstance(obj, plugins.NotifyNextcloud) is True
    assert isinstance(obj.url(), six.string_types) is True

    # An empty body
    assert obj.send(body="") is True
    assert 'data' in mock_post.call_args_list[0][1]
    assert 'shortMessage' in mock_post.call_args_list[0][1]['data']
    # The longMessage argument is not set
    assert 'longMessage' not in mock_post.call_args_list[0][1]['data']
