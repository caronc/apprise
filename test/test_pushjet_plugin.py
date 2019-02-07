# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
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
from apprise import NotifyType
from apprise import Apprise
import mock

TEST_URLS = (
    ##################################
    # NotifyPushjet
    ##################################
    ('pjet://', {
        'instance': None,
    }),
    ('pjets://', {
        'instance': None,
    }),
    #  You must specify a username
    ('pjet://%s' % ('a' * 32), {
        'instance': None,
    }),
    # Specify your own server
    ('pjet://%s@localhost' % ('a' * 32), {
        'instance': plugins.NotifyPushjet,
    }),
    # Specify your own server with port
    ('pjets://%s@localhost:8080' % ('a' * 32), {
        'instance': plugins.NotifyPushjet,
    }),
    ('pjet://:@/', {
        'instance': None,
    }),
    ('pjet://%s@localhost:8081' % ('a' * 32), {
        'instance': plugins.NotifyPushjet,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_notify_exceptions': True,
    }),
)


@mock.patch('apprise.plugins.pushjet.pushjet.Service.send')
@mock.patch('apprise.plugins.pushjet.pushjet.Service.refresh')
def test_plugin(mock_refresh, mock_send):
    """
    API: NotifyPushjet Plugin() (pt1)

    """

    # iterate over our dictionary and test it out
    for (url, meta) in TEST_URLS:

        # Our expected instance
        instance = meta.get('instance', None)

        # Our expected server objects
        self = meta.get('self', None)

        # Our expected Query response (True, False, or exception type)
        response = meta.get('response', True)

        # Allow us to force the server response code to be something other then
        # the defaults
        response = meta.get(
            'response', True if response else False)

        test_notify_exceptions = meta.get(
            'test_notify_exceptions', False)

        test_exceptions = (
            plugins.pushjet.errors.AccessError(
                0, 'pushjet.AccessError() not handled'),
            plugins.pushjet.errors.NonexistentError(
                0, 'pushjet.NonexistentError() not handled'),
            plugins.pushjet.errors.SubscriptionError(
                0, 'gntp.SubscriptionError() not handled'),
            plugins.pushjet.errors.RequestError(
                'pushjet.RequestError() not handled'),
        )

        try:
            obj = Apprise.instantiate(url, suppress_exceptions=False)

            if instance is None:
                # Check that we got what we came for
                assert obj is instance
                continue

            assert(isinstance(obj, instance))

            if self:
                # Iterate over our expected entries inside of our object
                for key, val in self.items():
                    # Test that our object has the desired key
                    assert(hasattr(key, obj))
                    assert(getattr(key, obj) == val)

            try:
                if test_notify_exceptions is False:
                    # Store our response
                    mock_send.return_value = response
                    mock_send.side_effect = None

                    # check that we're as expected
                    assert obj.notify(
                        title='test', body='body',
                        notify_type=NotifyType.INFO) == response

                else:
                    for exception in test_exceptions:
                        mock_send.side_effect = exception
                        mock_send.return_value = None
                        try:
                            assert obj.notify(
                                title='test', body='body',
                                notify_type=NotifyType.INFO) is False

                        except AssertionError:
                            # Don't mess with these entries
                            raise

                        except Exception as e:
                            # We can't handle this exception type
                            assert False

            except AssertionError:
                # Don't mess with these entries
                raise

            except Exception as e:
                # Check that we were expecting this exception to happen
                assert isinstance(e, response)

        except AssertionError:
            # Don't mess with these entries
            raise

        except Exception as e:
            # Handle our exception
            assert(instance is not None)
            assert(isinstance(e, instance))
