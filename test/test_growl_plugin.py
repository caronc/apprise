# -*- coding: utf-8 -*-
#
# NotifyGrowl - Unit Tests
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
import re


TEST_URLS = (
    ##################################
    # NotifyGrowl
    ##################################
    ('growl://', {
        'instance': None,
    }),
    ('growl://:@/', {
        'instance': None
    }),

    ('growl://pass@growl.server', {
        'instance': plugins.NotifyGrowl,
    }),
    ('growl://ignored:pass@growl.server', {
        'instance': plugins.NotifyGrowl,
    }),
    ('growl://growl.server', {
        'instance': plugins.NotifyGrowl,
        # don't include an image by default
        'include_image': False,
    }),
    ('growl://growl.server?version=1', {
        'instance': plugins.NotifyGrowl,
    }),
    # Force a failure
    ('growl://growl.server?version=1', {
        'instance': plugins.NotifyGrowl,
        'growl_response': None,
    }),
    ('growl://growl.server?version=2', {
        # don't include an image by default
        'include_image': False,
        'instance': plugins.NotifyGrowl,
    }),
    ('growl://growl.server?version=2', {
        # don't include an image by default
        'include_image': False,
        'instance': plugins.NotifyGrowl,
        'growl_response': None,
    }),

    # Priorities
    ('growl://pass@growl.server?priority=low', {
        'instance': plugins.NotifyGrowl,
    }),
    ('growl://pass@growl.server?priority=moderate', {
        'instance': plugins.NotifyGrowl,
    }),
    ('growl://pass@growl.server?priority=normal', {
        'instance': plugins.NotifyGrowl,
    }),
    ('growl://pass@growl.server?priority=high', {
        'instance': plugins.NotifyGrowl,
    }),
    ('growl://pass@growl.server?priority=emergency', {
        'instance': plugins.NotifyGrowl,
    }),

    # Invalid Priorities
    ('growl://pass@growl.server?priority=invalid', {
        'instance': plugins.NotifyGrowl,
    }),
    ('growl://pass@growl.server?priority=', {
        'instance': plugins.NotifyGrowl,
    }),

    # invalid version
    ('growl://growl.server?version=', {
        'instance': plugins.NotifyGrowl,
    }),
    ('growl://growl.server?version=crap', {
        'instance': plugins.NotifyGrowl,
    }),

    # Ports
    ('growl://growl.changeport:2000', {
        'instance': plugins.NotifyGrowl,
    }),
    ('growl://growl.garbageport:garbage', {
        'instance': plugins.NotifyGrowl,
    }),
    ('growl://growl.colon:', {
        'instance': plugins.NotifyGrowl,
    }),
    # Exceptions
    ('growl://growl.exceptions01', {
        'instance': plugins.NotifyGrowl,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_growl_notify_exceptions': True,
    }),
    ('growl://growl.exceptions02', {
        'instance': plugins.NotifyGrowl,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_growl_register_exceptions': True,
    }),
)


@mock.patch('apprise.plugins.gntp.notifier.GrowlNotifier')
def test_growl_plugin(mock_gntp):
    """
    API: NotifyGrowl Plugin()

    """

    # iterate over our dictionary and test it out
    for (url, meta) in TEST_URLS:

        # Our expected instance
        instance = meta.get('instance', None)

        # Our expected exception
        exception = meta.get('exception', None)

        # Our expected server objects
        self = meta.get('self', None)

        # Our expected Query response (True, False, or exception type)
        response = meta.get('response', True)

        # Allow us to force the server response code to be something other then
        # the defaults
        growl_response = meta.get(
            'growl_response', True if response else False)

        test_growl_notify_exceptions = meta.get(
            'test_growl_notify_exceptions', False)

        test_growl_register_exceptions = meta.get(
            'test_growl_register_exceptions', False)

        mock_notifier = mock.Mock()
        mock_gntp.return_value = mock_notifier

        test_growl_exceptions = (
            plugins.gntp.errors.NetworkError(
                0, 'gntp.ParseError() not handled'),
            plugins.gntp.errors.AuthError(
                0, 'gntp.AuthError() not handled'),
            plugins.gntp.errors.UnsupportedError(
                'gntp.UnsupportedError() not handled'),
        )

        if test_growl_notify_exceptions is True:
            # Store oure exceptions
            test_growl_notify_exceptions = test_growl_exceptions

        elif test_growl_register_exceptions is True:
            # Store oure exceptions
            test_growl_register_exceptions = test_growl_exceptions

            for exception in test_growl_register_exceptions:
                mock_notifier.register.side_effect = exception
                try:
                    obj = Apprise.instantiate(url, suppress_exceptions=False)

                except TypeError:
                    # This is the response we expect
                    assert True

                except Exception as e:
                    # We can't handle this exception type
                    print('%s / %s' % (url, str(e)))
                    assert False

            # We're done this part of the test
            continue

        else:
            # Store our response
            mock_notifier.notify.return_value = growl_response

        try:
            obj = Apprise.instantiate(url, suppress_exceptions=False)

            assert(exception is None)

            if obj is None:
                # We're done
                continue

            if instance is None:
                # Expected None but didn't get it
                print('%s instantiated %s' % (url, str(obj)))
                assert(False)

            assert(isinstance(obj, instance))

            if self:
                # Iterate over our expected entries inside of our object
                for key, val in self.items():
                    # Test that our object has the desired key
                    assert(hasattr(key, obj))
                    assert(getattr(key, obj) == val)

            try:
                if test_growl_notify_exceptions is False:
                    # check that we're as expected
                    assert obj.notify(
                        title='test', body='body',
                        notify_type=NotifyType.INFO) == response

                else:
                    for exception in test_growl_notify_exceptions:
                        mock_notifier.notify.side_effect = exception
                        try:
                            assert obj.notify(
                                title='test', body='body',
                                notify_type=NotifyType.INFO) is False

                        except AssertionError:
                            # Don't mess with these entries
                            raise

                        except Exception as e:
                            # We can't handle this exception type
                            print('%s / %s' % (url, str(e)))
                            assert False

            except AssertionError:
                # Don't mess with these entries
                raise

            except Exception as e:
                # Check that we were expecting this exception to happen
                assert isinstance(e, response)

        except AssertionError:
            # Don't mess with these entries
            print('%s AssertionError' % url)
            raise

        except Exception as e:
            # Handle our exception
            print('%s / %s' % (url, str(e)))
            assert(exception is not None)
            assert(isinstance(e, exception))
