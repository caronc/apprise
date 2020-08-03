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

import os
import sys
import mock
import six
import pytest
import apprise

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

try:
    # Python v3.4+
    from importlib import reload
except ImportError:
    try:
        # Python v3.0-v3.3
        from imp import reload
    except ImportError:
        # Python v2.7
        pass


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
    # no problem; these tests will be skipped at this point
    TEST_GROWL_EXCEPTIONS = tuple()


@pytest.mark.skipif('gntp' not in sys.modules, reason="requires gntp")
def test_growl_plugin_import_error(tmpdir):
    """
    API: NotifyGrowl Plugin() Import Error

    """
    # This is a really confusing test case; it can probably be done better,
    # but this was all I could come up with.  Effectively Apprise is will
    # still work flawlessly without the gntp dependancy.  Since
    # gntp is actually required to be installed to run these unit tests
    # we need to do some hacky tricks into fooling our test cases that the
    # package isn't available.

    # So we create a temporary directory called gntp (simulating the
    # library itself) and writing an __init__.py in it that does nothing
    # but throw an ImportError exception (simulating that the library
    # isn't found).
    suite = tmpdir.mkdir("gntp")
    suite.join("__init__.py").write('')
    module_name = 'gntp'
    suite.join("{}.py".format(module_name)).write('raise ImportError()')

    # The second part of the test is to update our PYTHON_PATH to look
    # into this new directory first (before looking where the actual
    # valid paths are).  This will allow us to override 'JUST' the sleekxmpp
    # path.

    # Update our path to point to our new test suite
    sys.path.insert(0, str(suite))

    # We need to remove the gntp modules that have already been loaded
    # in memory otherwise they'll just be used instead. Python is smart and
    # won't go try and reload everything again if it doesn't have to.
    for name in list(sys.modules.keys()):
        if name.startswith('{}.'.format(module_name)):
            del sys.modules[name]
    del sys.modules[module_name]

    # The following libraries need to be reloaded to prevent
    #  TypeError: super(type, obj): obj must be an instance or subtype of type
    #  This is better explained in this StackOverflow post:
    #     https://stackoverflow.com/questions/31363311/\
    #       any-way-to-manually-fix-operation-of-\
    #          super-after-ipython-reload-avoiding-ty
    #
    reload(sys.modules['apprise.plugins.NotifyGrowl'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])

    # This tests that Apprise still works without gntp.
    obj = apprise.Apprise.instantiate('growl://growl.server')

    # Growl objects can still be instantiated however
    assert obj is not None

    # Notifications won't work because gntp did not load
    assert obj.notify(
        title='test', body='body',
        notify_type=apprise.NotifyType.INFO) is False

    # Tidy-up / restore things to how they were
    # Remove our garbage library
    os.unlink(str(suite.join("{}.py".format(module_name))))

    # Remove our custom entry into the path
    sys.path.remove(str(suite))

    # Reload the libraries we care about
    reload(sys.modules['apprise.plugins.NotifyGrowl'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])


@pytest.mark.skipif('gntp' not in sys.modules, reason="requires gntp")
@mock.patch('gntp.notifier.GrowlNotifier')
def test_growl_exception_handling(mock_gntp):
    """
    API: NotifyGrowl Exception Handling
    """

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
    'gntp' not in sys.modules, reason="requires gntp")
@mock.patch('gntp.notifier.GrowlNotifier')
def test_growl_plugin(mock_gntp):
    """
    API: NotifyGrowl Plugin()

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
                assert isinstance(obj.url(), six.string_types) is True

                # Test our privacy=True flag
                assert isinstance(
                    obj.url(privacy=True), six.string_types) is True

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
