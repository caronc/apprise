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
import pytest
import requests
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# a test UUID we can use
UUID4 = '8b799edf-6f98-4d3a-9be7-2862fb4e5752'

# Our Testing URLs
apprise_url_tests = (
    ('lametric://', {
        # No APIKey or App ID specified
        'instance': TypeError,
    }),
    ('lametric://:@/', {
        # No APIKey or App ID specified
        'instance': TypeError,
    }),
    ('lametric://{}/'.format(
        'com.lametric.941c51dff3135bd87aa72db9d855dd50'), {
            # No APIKey specified
            'instance': TypeError,
    }),
    ('lametric://root:{}@192.168.0.5:8080/'.format(UUID4), {
        # Everything is okay; this would be picked up in Device Mode
        # We're using a default port and enforcing a special user
        'instance': plugins.NotifyLametric,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametric://root:8...2@192.168.0.5/',
    }),
    ('lametric://{}@192.168.0.4:8000/'.format(UUID4), {
        # Everything is okay; this would be picked up in Device Mode
        # Port is enforced
        'instance': plugins.NotifyLametric,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametric://8...2@192.168.0.4:8000/',
    }),
    ('lametric://{}@192.168.0.5/'.format(UUID4), {
        # Everything is okay; this would be picked up in Device Mode
        'instance': plugins.NotifyLametric,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametric://8...2@192.168.0.5/',
    }),
    ('lametrics://{}@192.168.0.6/?mode=device'.format(UUID4), {
        # Everything is okay; Device mode forced
        'instance': plugins.NotifyLametric,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametrics://8...2@192.168.0.6/',
    }),
    # Support Native URL (with Access Token Argument)
    ('https://developer.lametric.com/api/v1/dev/widget/update/'
        'com.lametric.ABCD123/1?token={}=='.format('D' * 88), {
            # Everything is okay; Device mode forced
            'instance': plugins.NotifyLametric,

            # Our expected url(privacy=True) startswith() response:
            'privacy_url': 'lametric://D...=@A...3/1/',
        }),

    ('lametric://192.168.2.8/?mode=device&apikey=abc123', {
        # Everything is okay; Device mode forced
        'instance': plugins.NotifyLametric,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametric://a...3@192.168.2.8/',
    }),
    ('lametrics://{}==@com.lametric.941c51dff3135bd87aa72db9d855dd50/'
        '?mode=cloud&app_ver=2'.format('A' * 88), {
            # Everything is okay; Cloud mode forced
            # We gracefully strip off the com.lametric. part as well
            # We also set an application version of 2
            'instance': plugins.NotifyLametric,

            # Our expected url(privacy=True) startswith() response:
            'privacy_url': 'lametric://A...=@9...0/',
        }),
    ('lametrics://{}==@com.lametric.941c51dff3135bd87aa72db9d855dd50/'
        '?app_ver=invalid'.format('A' * 88), {
            # We set invalid app version
            'instance': TypeError,
        }),
    # our lametric object initialized via argument
    ('lametric://?app=com.lametric.941c51dff3135bd87aa72db9d855dd50&token={}=='
        '&mode=cloud'.format('B' * 88), {
            # Everything is okay; Cloud mode forced
            'instance': plugins.NotifyLametric,

            # Our expected url(privacy=True) startswith() response:
            'privacy_url': 'lametric://B...=@9...0/',
        }),
    ('lametrics://{}==@abcd/?mode=cloud&sound=knock&icon_type=info'
     '&priority=critical&cycles=10'.format('C' * 88), {
         # Cloud mode forced, sound, icon_type, and priority not supported
         # with cloud mode so warnings are created
         'instance': plugins.NotifyLametric,

         # Our expected url(privacy=True) startswith() response:
         'privacy_url': 'lametric://C...=@a...d/',
     }),
    ('lametrics://{}@192.168.0.7/?mode=invalid'.format(UUID4), {
        # Invalid Mode
        'instance': TypeError,
    }),
    ('lametrics://{}@192.168.0.6/?sound=alarm1'.format(UUID4), {
        # Device mode with sound set to alarm1
        'instance': plugins.NotifyLametric,
    }),
    ('lametrics://{}@192.168.0.7/?sound=bike'.format(UUID4), {
        # Device mode with sound set to bicycle using alias
        'instance': plugins.NotifyLametric,
        # Bike is an alias,
        'url_matches': r'sound=bicycle',
    }),
    ('lametrics://{}@192.168.0.8/?sound=invalid!'.format(UUID4), {
        # Invalid sounds just produce warnings... object still loads
        'instance': plugins.NotifyLametric,
    }),
    ('lametrics://{}@192.168.0.9/?icon_type=alert'.format(UUID4), {
        # Icon Type Changed
        'instance': plugins.NotifyLametric,
        # icon=alert exists somewhere on our generated URL
        'url_matches': r'icon_type=alert',
    }),
    ('lametrics://{}@192.168.0.10/?icon_type=invalid'.format(UUID4), {
        # Invalid icon types just produce warnings... object still loads
        'instance': plugins.NotifyLametric,
    }),
    ('lametric://{}@192.168.1.1/?priority=warning'.format(UUID4), {
        # Priority changed
        'instance': plugins.NotifyLametric,
    }),
    ('lametrics://{}@192.168.1.2/?priority=invalid'.format(UUID4), {
        # Invalid priority just produce warnings... object still loads
        'instance': plugins.NotifyLametric,
    }),
    ('lametric://{}@192.168.1.2/?icon=230'.format(UUID4), {
        # Our custom icon by it's ID
        'instance': plugins.NotifyLametric,
    }),
    ('lametrics://{}@192.168.1.2/?icon=#230'.format(UUID4), {
        # Our custom icon by it's ID; the hashtag at the front is ignored
        'instance': plugins.NotifyLametric,
    }),
    ('lametric://{}@192.168.1.2/?icon=Heart'.format(UUID4), {
        # Our custom icon; the hashtag at the front is ignored
        'instance': plugins.NotifyLametric,
    }),
    ('lametric://{}@192.168.1.2/?icon=#'.format(UUID4), {
        # a hashtag and nothing else
        'instance': plugins.NotifyLametric,
    }),
    ('lametric://{}@192.168.1.2/?icon=#%20%20%20'.format(UUID4), {
        # a hashtag and some spaces
        'instance': plugins.NotifyLametric,
    }),
    ('lametric://{}@192.168.1.3/?cycles=2'.format(UUID4), {
        # Cycles changed
        'instance': plugins.NotifyLametric,
    }),
    ('lametric://{}@192.168.1.4/?cycles=-1'.format(UUID4), {
        # Cycles changed (out of range)
        'instance': plugins.NotifyLametric,
    }),
    ('lametrics://{}@192.168.1.5/?cycles=invalid'.format(UUID4), {
        # Invalid priority just produce warnings... object still loads
        'instance': plugins.NotifyLametric,
    }),
    ('lametric://{}@example.com/'.format(UUID4), {
        'instance': plugins.NotifyLametric,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametric://8...2@example.com/',
    }),
    ('lametrics://{}@example.ca/'.format(UUID4), {
        'instance': plugins.NotifyLametric,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametrics://8...2@example.ca/',
    }),
    ('lametrics://{}@example.net/'.format(UUID4), {
        'instance': plugins.NotifyLametric,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_lametric_urls():
    """
    NotifyLametric() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_lametric_edge_cases():
    """
    NotifyLametric() Edge Cases

    """
    # Initializes the plugin with an invalid API Key
    with pytest.raises(TypeError):
        plugins.NotifyLametric(apikey=None, mode="device")

    # Initializes the plugin with an invalid Client Secret
    with pytest.raises(TypeError):
        plugins.NotifyLametric(client_id='valid', secret=None, mode="cloud")
