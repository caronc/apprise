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

from apprise.plugins.NotifyStreamlabs import NotifyStreamlabs
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('strmlabs://', {
        # No Access Token specified
        'instance': TypeError,
    }),
    ('strmlabs://a_bd_/', {
        # invalid Access Token
        'instance': TypeError,
    }),
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso', {
        # access token
        'instance': NotifyStreamlabs,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'strmlabs://I...o',
    }),
    # Test incorrect currency
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?currency=ABCD', {
        'instance': TypeError,
    }),
    # Test complete params - donations
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/'
     '?name=tt&identifier=pyt&amount=20&currency=USD&call=donations',
     {'instance': NotifyStreamlabs, }),
    # Test complete params - donations
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/'
     '?image_href=https://example.org/rms.jpg'
     '&sound_href=https://example.org/rms.mp3',
     {'instance': NotifyStreamlabs, }),
    # Test complete params - alerts
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/'
     '?duration=1000&image_href=&'
     'sound_href=&alert_type=donation&special_text_color=crimson',
     {'instance': NotifyStreamlabs, }),
    # Test incorrect call
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/'
     '?name=tt&identifier=pyt&amount=20&currency=USD&call=rms',
     {'instance': TypeError, }),
    # Test incorrect alert_type
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/'
     '?name=tt&identifier=pyt&amount=20&currency=USD&alert_type=rms',
     {'instance': TypeError, }),
    # Test incorrect name
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?name=t', {
        'instance': TypeError,
    }),
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=donations', {
        'instance': NotifyStreamlabs,
        # A failure has status set to zero
        # Test without an 'error' flag
        'requests_response_text': {
            'status': 0,
        },

        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=alerts', {
        'instance': NotifyStreamlabs,
        # A failure has status set to zero
        # Test without an 'error' flag
        'requests_response_text': {
            'status': 0,
        },

        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=alerts', {
        'instance': NotifyStreamlabs,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=donations', {
        'instance': NotifyStreamlabs,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_streamlabs_urls():
    """
    NotifyStreamlabs() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
