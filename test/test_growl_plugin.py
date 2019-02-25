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

import mock
import six
from apprise import plugins
from apprise import NotifyType
from apprise import Apprise

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


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

                except Exception:
                    # We can't handle this exception type
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
                assert(False)

            assert(isinstance(obj, instance) is True)

            if isinstance(obj, plugins.NotifyBase.NotifyBase):
                # We loaded okay; now lets make sure we can reverse this url
                assert(isinstance(obj.url(), six.string_types) is True)

                # Instantiate the exact same object again using the URL from
                # the one that was already created properly
                obj_cmp = Apprise.instantiate(obj.url())

                # Our object should be the same instance as what we had
                # originally expected above.
                if not isinstance(obj_cmp, plugins.NotifyBase.NotifyBase):
                    # Assert messages are hard to trace back with the way
                    # these tests work. Just printing before throwing our
                    # assertion failure makes things easier to debug later on
                    print('TEST FAIL: {} regenerated as {}'.format(
                        url, obj.url()))
                    assert(False)

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
