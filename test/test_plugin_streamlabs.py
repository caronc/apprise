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
from apprise import plugins
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
        'instance': plugins.NotifyStreamlabs,

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
     {'instance': plugins.NotifyStreamlabs, }),
    # Test complete params - donations
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/'
     '?image_href=https://example.org/rms.jpg'
     '&sound_href=https://example.org/rms.mp3',
     {'instance': plugins.NotifyStreamlabs, }),
    # Test complete params - alerts
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/'
     '?duration=1000&image_href=&'
     'sound_href=&alert_type=donation&special_text_color=crimson',
     {'instance': plugins.NotifyStreamlabs, }),
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
        'instance': plugins.NotifyStreamlabs,
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
        'instance': plugins.NotifyStreamlabs,
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
        'instance': plugins.NotifyStreamlabs,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
    ('strmlabs://IcIcArukDQtuC1is1X1UdKZjTg118Lag2vScOmso/?call=donations', {
        'instance': plugins.NotifyStreamlabs,
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
