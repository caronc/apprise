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
from apprise.plugins.NotifyPagerDuty import NotifyPagerDuty
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('pagerduty://', {
        # No Access Token or Integration/Routing Key specified
        'instance': TypeError,
    }),
    ('pagerduty://%20@%20/', {
        # invalid Access Token and Integration/Routing Key
        'instance': TypeError,
    }),
    ('pagerduty://%20/', {
        # invalid Access Token; no Integration/Routing Key
        'instance': TypeError,
    }),
    ('pagerduty://%20@abcd/', {
        # Invalid Integration/Routing Key (but valid Access Token)
        'instance': TypeError,
    }),
    ('pagerduty://myroutekey@myapikey/%20', {
        # bad source
        'instance': TypeError,
    }),
    ('pagerduty://myroutekey@myapikey/mysource/%20', {
        # bad component
        'instance': TypeError,
    }),
    ('pagerduty://myroutekey@myapikey?region=invalid', {
        # invalid region
        'instance': TypeError,
    }),
    ('pagerduty://myroutekey@myapikey?severity=invalid', {
        # invalid severity
        'instance': TypeError,
    }),
    ('pagerduty://myroutekey@myapikey', {
        # minimum requirements met
        'instance': NotifyPagerDuty,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pagerduty://****@****/A...e/N...n?',
    }),
    ('pagerduty://myroutekey@myapikey?image=no', {
        # minimum requirements met and disable images
        'instance': NotifyPagerDuty,
    }),
    ('pagerduty://myroutekey@myapikey?region=eu', {
        # european region
        'instance': NotifyPagerDuty,
    }),
    ('pagerduty://myroutekey@myapikey?severity=critical', {
        # Severity over-ride
        'instance': NotifyPagerDuty,
    }),
    ('pagerduty://myroutekey@myapikey?severity=err', {
        # Severity over-ride (short-form)
        'instance': NotifyPagerDuty,
    }),
    # Custom values
    ('pagerduty://myroutekey@myapikey?+key=value&+key2=value2', {
        # minimum requirements and support custom key/value pairs
        'instance': NotifyPagerDuty,
    }),
    ('pagerduty://myroutekey@myapikey/mysource/mycomponent', {
        # a valid url
        'instance': NotifyPagerDuty,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pagerduty://****@****/m...e/m...t?',
    }),
    ('pagerduty://routekey@apikey/ms/mc?group=mygroup&class=myclass', {
        # class/group testing
        'instance': NotifyPagerDuty,
    }),
    ('pagerduty://?integrationkey=r&apikey=a&source=s&component=c'
        '&group=g&class=c&image=no&click=http://localhost', {
            # all parameters
            'instance': NotifyPagerDuty}),
    ('pagerduty://somerkey@someapikey/bizzare/code', {
        'instance': NotifyPagerDuty,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('pagerduty://myroutekey@myapikey/mysource/mycomponent', {
        'instance': NotifyPagerDuty,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_pagerduty_urls():
    """
    NotifyPagerDuty() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
