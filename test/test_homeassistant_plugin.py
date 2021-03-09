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

import six
import mock
import requests
from apprise import plugins
from apprise import Apprise

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


@mock.patch('requests.post')
def test_homeassistant_plugin(mock_post):
    """
    API: NotifyHomeAssistant() Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    response = mock.Mock()
    response.content = ''
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Variation Initializations
    obj = Apprise.instantiate('hassio://localhost/accesstoken')
    assert isinstance(obj, plugins.NotifyHomeAssistant) is True
    assert isinstance(obj.url(), six.string_types) is True

    # Send Notification
    assert obj.send(body="test") is True

    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'http://localhost:8123/api/services/persistent_notification/create'
