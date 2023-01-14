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
import requests
from unittest import mock

import apprise
from apprise.plugins.NotifyDapnet import DapnetPriority, NotifyDapnet
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('dapnet://', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('dapnet://:@/', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('dapnet://user:pass', {
        # No call-sign specified
        'instance': TypeError,
    }),
    ('dapnet://user@host', {
        # No password specified
        'instance': TypeError,
    }),
    ('dapnet://user:pass@{}'.format('DF1ABC'), {
        # valid call sign
        'instance': NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}/{}'.format('DF1ABC', 'DF1DEF'), {
        # valid call signs
        'instance': NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@DF1ABC-1/DF1ABC/DF1ABC-15', {
        # valid call signs; but a few are duplicates;
        # at the end there will only be 1 entry
        'instance': NotifyDapnet,
        'requests_response_code': requests.codes.created,
        # Our expected url(privacy=True) startswith() response:
        # Note that only 1 entry is saved (as other 2 are duplicates)
        'privacy_url': 'dapnet://user:****@D...C?',
    }),
    ('dapnet://user:pass@?to={},{}'.format('DF1ABC', 'DF1DEF'), {
        # support the to= argument
        'instance': NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}?priority=normal'.format('DF1ABC'), {
        # valid call sign with priority
        'instance': NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}?priority=em&batch=false'.format(
        '/'.join(['DF1ABC', '0A1DEF'])), {
            # valid call sign with priority (emergency) + no batch
            # transmissions
            'instance': NotifyDapnet,
            'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}?priority=invalid'.format('DF1ABC'), {
        # invalid priority
        'instance': NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}?txgroups=dl-all,all'.format('DF1ABC'), {
        # valid call sign with two transmitter groups
        'instance': NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}?txgroups=invalid'.format('DF1ABC'), {
        # valid call sign with invalid transmitter group
        'instance': NotifyDapnet,
        'requests_response_code': requests.codes.created,
    }),
    ('dapnet://user:pass@{}/{}'.format('abcdefghi', 'a'), {
        # invalid call signs
        'instance': NotifyDapnet,
        'notify_response': False,
    }),
    # Edge cases
    ('dapnet://user:pass@{}'.format('DF1ABC'), {
        'instance': NotifyDapnet,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('dapnet://user:pass@{}'.format('DF1ABC'), {
        'instance': NotifyDapnet,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_dapnet_urls():
    """
    NotifyDapnet() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_dapnet_config_files(mock_post):
    """
    NotifyDapnet() Config File Cases
    """
    content = """
    urls:
      - dapnet://user:pass@DF1ABC:
          - priority: 0
            tag: dapnet_int normal
          - priority: "0"
            tag: dapnet_str_int normal
          - priority: normal
            tag: dapnet_str normal

          # This will take on normal (default) priority
          - priority: invalid
            tag: dapnet_invalid

      - dapnet://user1:pass2@DF1ABC:
          - priority: 1
            tag: dapnet_int emerg
          - priority: "1"
            tag: dapnet_str_int emerg
          - priority: emergency
            tag: dapnet_str emerg
    """

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.created

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 7 servers from that
    # 4x normal (invalid + 3 exclusivly specified to be so)
    # 3x emerg
    assert len(ac.servers()) == 7
    assert len(aobj) == 7
    assert len([x for x in aobj.find(tag='normal')]) == 3
    for s in aobj.find(tag='normal'):
        assert s.priority == DapnetPriority.NORMAL

    assert len([x for x in aobj.find(tag='emerg')]) == 3
    for s in aobj.find(tag='emerg'):
        assert s.priority == DapnetPriority.EMERGENCY

    assert len([x for x in aobj.find(tag='dapnet_str')]) == 2
    assert len([x for x in aobj.find(tag='dapnet_str_int')]) == 2
    assert len([x for x in aobj.find(tag='dapnet_int')]) == 2

    assert len([x for x in aobj.find(tag='dapnet_invalid')]) == 1
    assert next(aobj.find(tag='dapnet_invalid')).priority == \
        DapnetPriority.NORMAL

    # Notifications work
    assert aobj.notify(title="title", body="body") is True
