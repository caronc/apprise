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

import sys
from unittest import mock

import pytest
import apprise
from apprise.plugins.NotifyGrowl import GrowlPriority

try:
    from gntp import errors

    TEST_GROWL_EXCEPTIONS = (
        errors.NetworkError(
            0, 'gntp.ParseError() not handled'),
        errors.AuthError(
            0, 'gntp.AuthError() not handled'),
        errors.ParseError(
            0, 'gntp.ParseError() not handled'),
        errors.UnsupportedError(
            0, 'gntp.UnsupportedError() not handled'),
    )

except ImportError:
    # no problem; gntp isn't available to us
    pass

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


@pytest.mark.skipif(
    'gntp' in sys.modules,
    reason="Requires that gntp NOT be installed")
def test_plugin_growl_gntp_import_error():
    """
    NotifyGrowl() Import Error

    """
    # If the object is disabled, then it can't be instantiated
    obj = apprise.Apprise.instantiate('growl://growl.server')
    assert obj is None


@pytest.mark.skipif(
    'gntp' not in sys.modules, reason="Requires gntp")
@mock.patch('gntp.notifier.GrowlNotifier')
def test_plugin_growl_exception_handling(mock_gntp):
    """
    NotifyGrowl() Exception Handling
    """
    TEST_GROWL_EXCEPTIONS = (
        errors.NetworkError(
            0, 'gntp.ParseError() not handled'),
        errors.AuthError(
            0, 'gntp.AuthError() not handled'),
        errors.ParseError(
            0, 'gntp.ParseError() not handled'),
        errors.UnsupportedError(
            0, 'gntp.UnsupportedError() not handled'),
    )

    mock_notifier = mock.Mock()
    mock_gntp.return_value = mock_notifier
    mock_notifier.notify.return_value = True

    # First we test the growl.register() function
    for exception in TEST_GROWL_EXCEPTIONS:
        mock_notifier.register.side_effect = exception

        # instantiate our object
        obj = apprise.Apprise.instantiate(
            'growl://growl.server.hostname', suppress_exceptions=False)

        # Verify Growl object was instantiated
        assert obj is not None

        # We will fail to send the notification because our registration
        # would have failed
        assert obj.notify(
            title='test', body='body',
            notify_type=apprise.NotifyType.INFO) is False

    # Now we test the growl.notify() function
    mock_notifier.register.side_effect = None
    for exception in TEST_GROWL_EXCEPTIONS:
        mock_notifier.notify.side_effect = exception

        # instantiate our object
        obj = apprise.Apprise.instantiate(
            'growl://growl.server.hostname', suppress_exceptions=False)

        # Verify Growl object was instantiated
        assert obj is not None

        # We will fail to send the notification because of the underlining
        # notify() call throws an exception
        assert obj.notify(
            title='test', body='body',
            notify_type=apprise.NotifyType.INFO) is False


@pytest.mark.skipif(
    'gntp' not in sys.modules, reason="Requires gntp")
@mock.patch('gntp.notifier.GrowlNotifier')
def test_plugin_growl_general(mock_gntp):
    """
    NotifyGrowl() General Checks

    """

    urls = (
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
            'instance': apprise.plugins.NotifyGrowl,
        }),
        ('growl://ignored:pass@growl.server', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
        ('growl://growl.server', {
            'instance': apprise.plugins.NotifyGrowl,
            # don't include an image by default
            'include_image': False,
        }),
        ('growl://growl.server?version=1', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
        # Test sticky flag
        ('growl://growl.server?sticky=yes', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
        ('growl://growl.server?sticky=no', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
        # Force a failure
        ('growl://growl.server?version=1', {
            'instance': apprise.plugins.NotifyGrowl,
            'growl_response': None,
        }),
        ('growl://growl.server?version=2', {
            # don't include an image by default
            'include_image': False,
            'instance': apprise.plugins.NotifyGrowl,
        }),
        ('growl://growl.server?version=2', {
            # don't include an image by default
            'include_image': False,
            'instance': apprise.plugins.NotifyGrowl,
            'growl_response': None,
        }),

        # Priorities
        ('growl://pass@growl.server?priority=low', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
        ('growl://pass@growl.server?priority=moderate', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
        ('growl://pass@growl.server?priority=normal', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
        ('growl://pass@growl.server?priority=high', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
        ('growl://pass@growl.server?priority=emergency', {
            'instance': apprise.plugins.NotifyGrowl,
        }),

        # Invalid Priorities
        ('growl://pass@growl.server?priority=invalid', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
        ('growl://pass@growl.server?priority=', {
            'instance': apprise.plugins.NotifyGrowl,
        }),

        # invalid version
        ('growl://growl.server?version=', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
        ('growl://growl.server?version=crap', {
            'instance': apprise.plugins.NotifyGrowl,
        }),

        # Ports
        ('growl://growl.changeport:2000', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
        ('growl://growl.garbageport:garbage', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
        ('growl://growl.colon:', {
            'instance': apprise.plugins.NotifyGrowl,
        }),
    )

    # iterate over our dictionary and test it out
    for (url, meta) in urls:

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

        mock_notifier = mock.Mock()
        mock_gntp.return_value = mock_notifier
        mock_notifier.notify.side_effect = None

        # Store our response
        mock_notifier.notify.return_value = growl_response

        try:
            obj = apprise.Apprise.instantiate(url, suppress_exceptions=False)

            assert exception is None

            if obj is None:
                # We're done
                continue

            if instance is None:
                # Expected None but didn't get it
                assert False

            assert isinstance(obj, instance) is True

            if isinstance(obj, apprise.plugins.NotifyBase):
                # We loaded okay; now lets make sure we can reverse this url
                assert isinstance(obj.url(), str) is True

                # Test our privacy=True flag
                assert isinstance(
                    obj.url(privacy=True), str) is True

                # Instantiate the exact same object again using the URL from
                # the one that was already created properly
                obj_cmp = apprise.Apprise.instantiate(obj.url())

                # Our object should be the same instance as what we had
                # originally expected above.
                if not isinstance(obj_cmp, apprise.plugins.NotifyBase):
                    # Assert messages are hard to trace back with the way
                    # these tests work. Just printing before throwing our
                    # assertion failure makes things easier to debug later on
                    print('TEST FAIL: {} regenerated as {}'.format(
                        url, obj.url()))
                    assert False

            if self:
                # Iterate over our expected entries inside of our object
                for key, val in self.items():
                    # Test that our object has the desired key
                    assert hasattr(key, obj)
                    assert getattr(key, obj) == val

            try:
                # check that we're as expected
                assert obj.notify(
                    title='test', body='body',
                    notify_type=apprise.NotifyType.INFO) == response

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
            assert exception is not None
            assert isinstance(e, exception)


@pytest.mark.skipif(
    'gntp' not in sys.modules, reason="Requires gntp")
@mock.patch('gntp.notifier.GrowlNotifier')
def test_plugin_growl_config_files(mock_gntp):
    """
    NotifyGrowl() Config File Cases
    """
    content = """
    urls:
      - growl://pass@growl.server:
          - priority: -2
            tag: growl_int low
          - priority: "-2"
            tag: growl_str_int low
          - priority: low
            tag: growl_str low

          # This will take on moderate (default) priority
          - priority: invalid
            tag: growl_invalid

      - growl://pass@growl.server:
          - priority: 2
            tag: growl_int emerg
          - priority: "2"
            tag: growl_str_int emerg
          - priority: emergency
            tag: growl_str emerg
    """

    # Disable Throttling to speed testing
    apprise.plugins.NotifyGrowl.request_rate_per_sec = 0

    mock_notifier = mock.Mock()
    mock_gntp.return_value = mock_notifier
    mock_notifier.notify.return_value = True

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 7 servers from that
    # 3x low
    # 3x emerg
    # 1x invalid (so takes on normal priority)
    assert len(ac.servers()) == 7
    assert len(aobj) == 7
    assert len([x for x in aobj.find(tag='low')]) == 3
    for s in aobj.find(tag='low'):
        assert s.priority == GrowlPriority.LOW

    assert len([x for x in aobj.find(tag='emerg')]) == 3
    for s in aobj.find(tag='emerg'):
        assert s.priority == GrowlPriority.EMERGENCY

    assert len([x for x in aobj.find(tag='growl_str')]) == 2
    assert len([x for x in aobj.find(tag='growl_str_int')]) == 2
    assert len([x for x in aobj.find(tag='growl_int')]) == 2

    assert len([x for x in aobj.find(tag='growl_invalid')]) == 1
    assert next(aobj.find(tag='growl_invalid')).priority == \
        GrowlPriority.NORMAL
