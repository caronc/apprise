# -*- coding: utf-8 -*-
#
# NotifyPushjet - Unit Tests
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

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
    # Default query (uses pushjet server)
    ('pjet://%s' % ('a' * 32), {
        'instance': plugins.NotifyPushjet,
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
