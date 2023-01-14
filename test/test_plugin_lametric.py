# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.
import pytest
import requests
from apprise.plugins.NotifyLametric import NotifyLametric
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
        'instance': NotifyLametric,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametric://root:8...2@192.168.0.5/',
    }),
    ('lametric://{}@192.168.0.4:8000/'.format(UUID4), {
        # Everything is okay; this would be picked up in Device Mode
        # Port is enforced
        'instance': NotifyLametric,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametric://8...2@192.168.0.4:8000/',
    }),
    ('lametric://{}@192.168.0.5/'.format(UUID4), {
        # Everything is okay; this would be picked up in Device Mode
        'instance': NotifyLametric,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametric://8...2@192.168.0.5/',
    }),
    ('lametrics://{}@192.168.0.6/?mode=device'.format(UUID4), {
        # Everything is okay; Device mode forced
        'instance': NotifyLametric,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametrics://8...2@192.168.0.6/',
    }),
    # Support Native URL (with Access Token Argument)
    ('https://developer.lametric.com/api/v1/dev/widget/update/'
        'com.lametric.ABCD123/1?token={}=='.format('D' * 88), {
            # Everything is okay; Device mode forced
            'instance': NotifyLametric,

            # Our expected url(privacy=True) startswith() response:
            'privacy_url': 'lametric://D...=@A...3/1/',
        }),

    ('lametric://192.168.2.8/?mode=device&apikey=abc123', {
        # Everything is okay; Device mode forced
        'instance': NotifyLametric,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametric://a...3@192.168.2.8/',
    }),
    ('lametrics://{}==@com.lametric.941c51dff3135bd87aa72db9d855dd50/'
        '?mode=cloud&app_ver=2'.format('A' * 88), {
            # Everything is okay; Cloud mode forced
            # We gracefully strip off the com.lametric. part as well
            # We also set an application version of 2
            'instance': NotifyLametric,

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
            'instance': NotifyLametric,

            # Our expected url(privacy=True) startswith() response:
            'privacy_url': 'lametric://B...=@9...0/',
        }),
    ('lametrics://{}==@abcd/?mode=cloud&sound=knock&icon_type=info'
     '&priority=critical&cycles=10'.format('C' * 88), {
         # Cloud mode forced, sound, icon_type, and priority not supported
         # with cloud mode so warnings are created
         'instance': NotifyLametric,

         # Our expected url(privacy=True) startswith() response:
         'privacy_url': 'lametric://C...=@a...d/',
     }),
    ('lametrics://{}@192.168.0.7/?mode=invalid'.format(UUID4), {
        # Invalid Mode
        'instance': TypeError,
    }),
    ('lametrics://{}@192.168.0.6/?sound=alarm1'.format(UUID4), {
        # Device mode with sound set to alarm1
        'instance': NotifyLametric,
    }),
    ('lametrics://{}@192.168.0.7/?sound=bike'.format(UUID4), {
        # Device mode with sound set to bicycle using alias
        'instance': NotifyLametric,
        # Bike is an alias,
        'url_matches': r'sound=bicycle',
    }),
    ('lametrics://{}@192.168.0.8/?sound=invalid!'.format(UUID4), {
        # Invalid sounds just produce warnings... object still loads
        'instance': NotifyLametric,
    }),
    ('lametrics://{}@192.168.0.9/?icon_type=alert'.format(UUID4), {
        # Icon Type Changed
        'instance': NotifyLametric,
        # icon=alert exists somewhere on our generated URL
        'url_matches': r'icon_type=alert',
    }),
    ('lametrics://{}@192.168.0.10/?icon_type=invalid'.format(UUID4), {
        # Invalid icon types just produce warnings... object still loads
        'instance': NotifyLametric,
    }),
    ('lametric://{}@192.168.1.1/?priority=warning'.format(UUID4), {
        # Priority changed
        'instance': NotifyLametric,
    }),
    ('lametrics://{}@192.168.1.2/?priority=invalid'.format(UUID4), {
        # Invalid priority just produce warnings... object still loads
        'instance': NotifyLametric,
    }),
    ('lametric://{}@192.168.1.2/?icon=230'.format(UUID4), {
        # Our custom icon by it's ID
        'instance': NotifyLametric,
    }),
    ('lametrics://{}@192.168.1.2/?icon=#230'.format(UUID4), {
        # Our custom icon by it's ID; the hashtag at the front is ignored
        'instance': NotifyLametric,
    }),
    ('lametric://{}@192.168.1.2/?icon=Heart'.format(UUID4), {
        # Our custom icon; the hashtag at the front is ignored
        'instance': NotifyLametric,
    }),
    ('lametric://{}@192.168.1.2/?icon=#'.format(UUID4), {
        # a hashtag and nothing else
        'instance': NotifyLametric,
    }),
    ('lametric://{}@192.168.1.2/?icon=#%20%20%20'.format(UUID4), {
        # a hashtag and some spaces
        'instance': NotifyLametric,
    }),
    ('lametric://{}@192.168.1.3/?cycles=2'.format(UUID4), {
        # Cycles changed
        'instance': NotifyLametric,
    }),
    ('lametric://{}@192.168.1.4/?cycles=-1'.format(UUID4), {
        # Cycles changed (out of range)
        'instance': NotifyLametric,
    }),
    ('lametrics://{}@192.168.1.5/?cycles=invalid'.format(UUID4), {
        # Invalid priority just produce warnings... object still loads
        'instance': NotifyLametric,
    }),
    ('lametric://{}@example.com/'.format(UUID4), {
        'instance': NotifyLametric,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametric://8...2@example.com/',
    }),
    ('lametrics://{}@example.ca/'.format(UUID4), {
        'instance': NotifyLametric,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lametrics://8...2@example.ca/',
    }),
    ('lametrics://{}@example.net/'.format(UUID4), {
        'instance': NotifyLametric,
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
        NotifyLametric(apikey=None, mode="device")

    # Initializes the plugin with an invalid Client Secret
    with pytest.raises(TypeError):
        NotifyLametric(client_id='valid', secret=None, mode="cloud")
