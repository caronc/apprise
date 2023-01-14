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

from unittest import mock

import requests
import apprise
from apprise.plugins.NotifyOpsgenie import NotifyOpsgenie, OpsgeniePriority
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# a test UUID we can use
UUID4 = '8b799edf-6f98-4d3a-9be7-2862fb4e5752'

# Our Testing URLs
apprise_url_tests = (
    ('opsgenie://', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('opsgenie://:@/', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('opsgenie://%20%20/', {
        # invalid apikey specified
        'instance': TypeError,
    }),
    ('opsgenie://apikey/user/?region=xx', {
        # invalid region id
        'instance': TypeError,
    }),
    ('opsgenie://apikey/', {
        # No targets specified; this is allowed
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://apikey/user', {
        # Valid user
        'instance': NotifyOpsgenie,
        'privacy_url': 'opsgenie://a...y/%40user',
    }),
    ('opsgenie://apikey/@user?region=eu', {
        # European Region
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://apikey/@user?entity=A%20Entity', {
        # Assign an entity
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://apikey/@user?alias=An%20Alias', {
        # Assign an alias
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://apikey/@user?priority=p3', {
        # Assign our priority
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://apikey/?tags=comma,separated', {
        # Test our our 'tags' (tag is reserved in Apprise) but not 'tags'
        # Also test the fact we do not need to define a target
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://apikey/@user?priority=invalid', {
        # Invalid priority (loads using default)
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://apikey/user@email.com/#team/*sche/^esc/%20/a', {
        # Valid user (email), valid schedule, Escalated ID,
        # an invalid entry (%20), and too short of an entry (a)
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://apikey/{}/@{}/#{}/*{}/^{}/'.format(
        UUID4, UUID4, UUID4, UUID4, UUID4), {
        # similar to the above, except we use the UUID's
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://apikey?to=#team,user&+key=value&+type=override', {
        # Test to= and details (key/value pair) also override 'type'
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://apikey/#team/@user/?batch=yes', {
        # Test batch=
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://apikey/#team/@user/?batch=no', {
        # Test batch=
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://?apikey=abc&to=user', {
        # Test Kwargs
        'instance': NotifyOpsgenie,
    }),
    ('opsgenie://apikey/#team/user/', {
        'instance': NotifyOpsgenie,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('opsgenie://apikey/#topic1/device/', {
        'instance': NotifyOpsgenie,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_opsgenie_urls():
    """
    NotifyOpsgenie() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_opsgenie_config_files(mock_post):
    """
    NotifyOpsgenie() Config File Cases
    """
    content = """
    urls:
      - opsgenie://apikey/user:
          - priority: 1
            tag: opsgenie_int low
          - priority: "1"
            tag: opsgenie_str_int low
          - priority: "p1"
            tag: opsgenie_pstr_int low
          - priority: low
            tag: opsgenie_str low

          # This will take on moderate (default) priority
          - priority: invalid
            tag: opsgenie_invalid

      - opsgenie://apikey2/user2:
          - priority: 5
            tag: opsgenie_int emerg
          - priority: "5"
            tag: opsgenie_str_int emerg
          - priority: "p5"
            tag: opsgenie_pstr_int emerg
          - priority: emergency
            tag: opsgenie_str emerg
    """

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 9 servers from that
    # 4x low
    # 4x emerg
    # 1x invalid (so takes on normal priority)
    assert len(ac.servers()) == 9
    assert len(aobj) == 9
    assert len([x for x in aobj.find(tag='low')]) == 4
    for s in aobj.find(tag='low'):
        assert s.priority == OpsgeniePriority.LOW

    assert len([x for x in aobj.find(tag='emerg')]) == 4
    for s in aobj.find(tag='emerg'):
        assert s.priority == OpsgeniePriority.EMERGENCY

    assert len([x for x in aobj.find(tag='opsgenie_str')]) == 2
    assert len([x for x in aobj.find(tag='opsgenie_str_int')]) == 2
    assert len([x for x in aobj.find(tag='opsgenie_pstr_int')]) == 2
    assert len([x for x in aobj.find(tag='opsgenie_int')]) == 2

    assert len([x for x in aobj.find(tag='opsgenie_invalid')]) == 1
    assert next(aobj.find(tag='opsgenie_invalid')).priority == \
        OpsgeniePriority.NORMAL
