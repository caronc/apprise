# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('bark://', {
        # No no host
        'instance': None,
    }),
    ('bark://:@/', {
        # just invalid all around
        'instance': None,
    }),
    ('bark://localhost', {
        # No Device Key specified
        'instance': plugins.NotifyBark,
        # Expected notify() response False (because we won't be able
        # to actually notify anything if no device_key was specified
        'notify_response': False,

    }),
    ('bark://192.168.0.6:8081/device_key', {
        # Everything is okay
        'instance': plugins.NotifyBark,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'bark://192.168.0.6:8081/',
    }),
    ('bark://user@192.168.0.6:8081/device_key', {
        # Everything is okay (test with user)
        'instance': plugins.NotifyBark,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'bark://user@192.168.0.6:8081/',
    }),
    ('bark://192.168.0.6:8081/device_key/?sound=invalid', {
        # bad sound, but we go ahead anyway
        'instance': plugins.NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?sound=alarm', {
        # alarm.caf sound loaded
        'instance': plugins.NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?sound=NOiR.cAf', {
        # noir.caf sound loaded
        'instance': plugins.NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?badge=100', {
        # set badge
        'instance': plugins.NotifyBark,
    }),
    ('barks://192.168.0.6:8081/device_key/?badge=invalid', {
        # set invalid badge
        'instance': plugins.NotifyBark,
    }),
    ('barks://192.168.0.6:8081/device_key/?badge=-12', {
        # set invalid badge
        'instance': plugins.NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?category=apprise', {
        # set category
        'instance': plugins.NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?image=no', {
        # do not display image
        'instance': plugins.NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?group=apprise', {
        # set group
        'instance': plugins.NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?level=invalid', {
        # bad level, but we go ahead anyway
        'instance': plugins.NotifyBark,
    }),
    ('bark://192.168.0.6:8081/?to=device_key', {
        # test use of to= argument
        'instance': plugins.NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?click=http://localhost', {
        # Our click link
        'instance': plugins.NotifyBark,
    }),
    ('bark://192.168.0.6:8081/device_key/?level=active', {
        # active level
        'instance': plugins.NotifyBark,
    }),
    ('bark://user:pass@192.168.0.5:8086/device_key/device_key2/', {
        # Everything is okay
        'instance': plugins.NotifyBark,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'bark://user:****@192.168.0.5:8086/',
    }),
    ('barks://192.168.0.7/device_key/', {
        'instance': plugins.NotifyBark,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'barks://192.168.0.7/device_key',
    }),
    ('bark://192.168.0.7/device_key', {
        'instance': plugins.NotifyBark,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_bark_urls():
    """
    NotifyBark() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
