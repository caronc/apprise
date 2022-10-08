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
from __future__ import print_function
import re
from unittest import mock

import requests
import json
from inspect import cleandoc
from os.path import dirname
from os.path import join
from apprise import cli
from apprise import NotifyBase
from apprise.common import NOTIFY_CUSTOM_MODULE_MAP
from apprise.utils import PATHS_PREVIOUSLY_SCANNED
from click.testing import CliRunner
from apprise.common import NOTIFY_SCHEMA_MAP
from apprise.utils import environ
from apprise.plugins import __load_matrix
from apprise.plugins import __reset_matrix

from importlib import reload


# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_apprise_cli_nux_env(tmpdir):
    """
    CLI: Nux Environment

    """

    class GoodNotification(NotifyBase):
        def __init__(self, *args, **kwargs):
            super(GoodNotification, self).__init__(*args, **kwargs)

        def notify(self, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, *args, **kwargs):
            # Support url()
            return 'good://'

    class BadNotification(NotifyBase):
        def __init__(self, *args, **kwargs):
            super(BadNotification, self).__init__(*args, **kwargs)

        def notify(self, **kwargs):
            # Force a notification failure
            return False

        def url(self, *args, **kwargs):
            # Support url()
            return 'bad://'

    # Set up our notification types
    NOTIFY_SCHEMA_MAP['good'] = GoodNotification
    NOTIFY_SCHEMA_MAP['bad'] = BadNotification

    runner = CliRunner()
    result = runner.invoke(cli.main)
    # no servers specified; we return 1 (non-zero)
    assert result.exit_code == 1

    result = runner.invoke(cli.main, ['-v'])
    assert result.exit_code == 1

    result = runner.invoke(cli.main, ['-vv'])
    assert result.exit_code == 1

    result = runner.invoke(cli.main, ['-vvv'])
    assert result.exit_code == 1

    result = runner.invoke(cli.main, ['-vvvv'])
    assert result.exit_code == 1

    # Display version information and exit
    result = runner.invoke(cli.main, ['-V'])
    assert result.exit_code == 0

    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        'good://localhost',
    ])
    assert result.exit_code == 0

    with mock.patch('requests.post') as mock_post:
        # Prepare Mock
        mock_post.return_value = requests.Request()
        mock_post.return_value.status_code = requests.codes.ok

        result = runner.invoke(cli.main, [
            '-t', 'test title',
            '-b', 'test body\\nsNewLine',
            # Test using interpret escapes
            '-e',
            # Use our JSON query
            'json://localhost',
        ])
        assert result.exit_code == 0

        # Test our call count
        assert mock_post.call_count == 1

        # Our string is now escaped correctly
        json.loads(mock_post.call_args_list[0][1]['data'])\
            .get('message', '') == 'test body\nsNewLine'

        # Reset
        mock_post.reset_mock()

        result = runner.invoke(cli.main, [
            '-t', 'test title',
            '-b', 'test body\\nsNewLine',
            # No -e switch at all (so we don't escape the above)
            # Use our JSON query
            'json://localhost',
        ])
        assert result.exit_code == 0

        # Test our call count
        assert mock_post.call_count == 1

        # Our string is now escaped correctly
        json.loads(mock_post.call_args_list[0][1]['data'])\
            .get('message', '') == 'test body\\nsNewLine'

    # Run in synchronous mode
    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        'good://localhost',
        '--disable-async',
    ])
    assert result.exit_code == 0

    # Test Debug Mode (--debug)
    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        'good://localhost',
        '--debug',
    ])
    assert result.exit_code == 0

    # Test Debug Mode (-D)
    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        'good://localhost',
        '-D',
    ])
    assert result.exit_code == 0

    result = runner.invoke(cli.main, [
        '-t', 'test title',
        'good://localhost',
    ], input='test stdin body\n')
    assert result.exit_code == 0

    # Run in synchronous mode
    result = runner.invoke(cli.main, [
        '-t', 'test title',
        'good://localhost',
        '--disable-async',
    ], input='test stdin body\n')
    assert result.exit_code == 0

    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        'bad://localhost',
    ])
    assert result.exit_code == 1

    # Run in synchronous mode
    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        'bad://localhost',
        '-Da',
    ])
    assert result.exit_code == 1

    # Testing with the --dry-run flag reveals a successful response since we
    # don't actually execute the bad:// notification; we only display it
    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        'bad://localhost',
        '--dry-run',
    ])
    assert result.exit_code == 0

    # Write a simple text based configuration file
    t = tmpdir.mkdir("apprise-obj").join("apprise")
    buf = """
    # Include ourselves
    include {}

    taga,tagb=good://localhost
    tagc=good://nuxref.com
    """.format(str(t))
    t.write(buf)

    # This will read our configuration and not send any notices at all
    # because we assigned tags to all of our urls and didn't identify
    # a specific match below.

    # 'include' reference in configuration file would have included the file a
    # second time (since recursion default is 1).
    result = runner.invoke(cli.main, [
        '-b', 'test config',
        '--config', str(t),
    ])
    # Even when recursion take place, tags are all honored
    # so 2 is returned because nothing was notified
    assert result.exit_code == 3

    # This will send out 1 notification because our tag matches
    # one of the entries above
    # translation: has taga
    result = runner.invoke(cli.main, [
        '-b', 'has taga',
        '--config', str(t),
        '--tag', 'taga',
    ])
    assert result.exit_code == 0

    # Test recursion
    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        '--config', str(t),
        '--tag', 'tagc',
        # Invalid entry specified for recursion
        '-R', 'invalid',
    ])
    assert result.exit_code == 2

    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        '--config', str(t),
        '--tag', 'tagc',
        # missing entry specified for recursion
        '--recursive-depth',
    ])
    assert result.exit_code == 2

    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        '--config', str(t),
        '--tag', 'tagc',
        # Disable recursion (thus inclusion will be ignored)
        '-R', '0',
    ])
    assert result.exit_code == 0

    # Test recursion
    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        '--config', str(t),
        '--tag', 'tagc',
        # Recurse up to 5 times
        '--recursion-depth', '5',
    ])
    assert result.exit_code == 0

    # This will send out 2 notifications because by specifying 2 tag
    # entries, we 'or' them together:
    # translation: has taga or tagb or tagd
    result = runner.invoke(cli.main, [
        '-b', 'has taga OR tagc OR tagd',
        '--config', str(t),
        '--tag', 'taga',
        '--tag', 'tagc',
        '--tag', 'tagd',
    ])
    assert result.exit_code == 0

    # Write a simple text based configuration file
    t = tmpdir.mkdir("apprise-obj2").join("apprise-test2")
    buf = """
    good://localhost/1
    good://localhost/2
    good://localhost/3
    good://localhost/4
    good://localhost/5
    myTag=good://localhost/6
    """
    t.write(buf)

    # This will read our configuration and send a notification to
    # the first 5 entries in the list, but not the one that has
    # the tag associated with it
    result = runner.invoke(cli.main, [
        '-b', 'test config',
        '--config', str(t),
    ])
    assert result.exit_code == 0

    # Test our notification type switch (it defaults to info) so we want to
    # try it as a different value. Should return without a problem
    result = runner.invoke(cli.main, [
        '-b', '# test config',
        '--config', str(t),
        '-n', 'success',
    ])
    assert result.exit_code == 0

    # Test our notification type switch when set to something unsupported
    result = runner.invoke(cli.main, [
        '-b', 'test config',
        '--config', str(t),
        '--notification-type', 'invalid',
    ])
    # An error code of 2 is returned if invalid input is specified on the
    # command line
    assert result.exit_code == 2

    # The notification type switch is case-insensitive
    result = runner.invoke(cli.main, [
        '-b', 'test config',
        '--config', str(t),
        '--notification-type', 'WARNING',
    ])
    assert result.exit_code == 0

    # Test our formatting switch (it defaults to text) so we want to try it as
    # a different value. Should return without a problem
    result = runner.invoke(cli.main, [
        '-b', '# test config',
        '--config', str(t),
        '-i', 'markdown',
    ])
    assert result.exit_code == 0

    # Test our formatting switch when set to something unsupported
    result = runner.invoke(cli.main, [
        '-b', 'test config',
        '--config', str(t),
        '--input-format', 'invalid',
    ])
    # An error code of 2 is returned if invalid input is specified on the
    # command line
    assert result.exit_code == 2

    # The formatting switch is not case sensitive
    result = runner.invoke(cli.main, [
        '-b', '# test config',
        '--config', str(t),
        '--input-format', 'HTML',
    ])
    assert result.exit_code == 0

    # As a way of ensuring we match the first 5 entries, we can run a
    # --dry-run against the same result set above and verify the output
    result = runner.invoke(cli.main, [
        '-b', 'test config',
        '--config', str(t),
        '--dry-run',
    ])
    assert result.exit_code == 0
    lines = re.split(r'[\r\n]', result.output.strip())
    # 5 lines of all good:// entries matched
    assert len(lines) == 5
    # Verify we match against the remaining good:// entries
    for i in range(0, 5):
        assert lines[i].endswith('good://')

    # This will fail because nothing matches mytag. It's case sensitive
    # and we would only actually match against myTag
    result = runner.invoke(cli.main, [
        '-b', 'has mytag',
        '--config', str(t),
        '--tag', 'mytag',
    ])
    assert result.exit_code == 3

    # Same command as the one identified above except we set the --dry-run
    # flag. This causes our list of matched results to be printed only.
    # However, since we don't match anything; we still fail with a return code
    # of 2.
    result = runner.invoke(cli.main, [
        '-b', 'has mytag',
        '--config', str(t),
        '--tag', 'mytag',
        '--dry-run'
    ])
    assert result.exit_code == 3

    # Here is a case where we get what was expected; we also attach a file
    result = runner.invoke(cli.main, [
        '-b', 'has myTag',
        '--config', str(t),
        '--attach', join(dirname(__file__), 'var', 'apprise-test.gif'),
        '--tag', 'myTag',
    ])
    assert result.exit_code == 0

    # Testing with the --dry-run flag reveals the same positive results
    # because there was at least one match
    result = runner.invoke(cli.main, [
        '-b', 'has myTag',
        '--config', str(t),
        '--tag', 'myTag',
        '--dry-run',
    ])
    assert result.exit_code == 0

    #
    # Test environment variables
    #
    # Write a simple text based configuration file
    t2 = tmpdir.mkdir("apprise-obj-env").join("apprise")
    buf = """
    # A general one
    good://localhost

    # A failure (if we use the fail tag)
    fail=bad://localhost

    # A normal one tied to myTag
    myTag=good://nuxref.com
    """
    t2.write(buf)

    with environ(APPRISE_URLS="good://localhost"):
        # This will load okay because we defined the environment
        # variable with a valid URL
        result = runner.invoke(cli.main, [
            '-b', 'test environment',
            # Test that we ignore our tag
            '--tag', 'mytag',
        ])
        assert result.exit_code == 0

        # Same action but without --tag
        result = runner.invoke(cli.main, [
            '-b', 'test environment',
        ])
        assert result.exit_code == 0

    with mock.patch('apprise.cli.DEFAULT_CONFIG_PATHS', []):
        with environ(APPRISE_URLS="      "):
            # An empty string is not valid and therefore not loaded so the
            # below fails. We override the DEFAULT_CONFIG_PATHS because we
            # don't want to detect ones loaded on the machine running the unit
            # tests
            result = runner.invoke(cli.main, [
                '-b', 'test environment',
            ])
            assert result.exit_code == 1

    with environ(APPRISE_URLS="bad://localhost"):
        result = runner.invoke(cli.main, [
            '-b', 'test environment',
        ])
        assert result.exit_code == 1

        # If we specify an inline URL, it will over-ride the environment
        # variable
        result = runner.invoke(cli.main, [
            '-t', 'test title',
            '-b', 'test body',
            'good://localhost',
        ])
        assert result.exit_code == 0

        # A Config file also over-rides the environment variable if
        # specified on the command line:
        result = runner.invoke(cli.main, [
            '-b', 'has myTag',
            '--config', str(t2),
            '--tag', 'myTag',
        ])
        assert result.exit_code == 0

    with environ(APPRISE_CONFIG=str(t2)):
        # Our configuration file will load from our environmment variable
        result = runner.invoke(cli.main, [
            '-b', 'has myTag',
            '--tag', 'myTag',
        ])
        assert result.exit_code == 0

    with mock.patch('apprise.cli.DEFAULT_CONFIG_PATHS', []):
        with environ(APPRISE_CONFIG="      "):
            # We will fail to send the notification as no path was
            # specified.
            # We override the DEFAULT_CONFIG_PATHS because we don't
            # want to detect ones loaded on the machine running the unit tests
            result = runner.invoke(cli.main, [
                '-b', 'my message',
            ])
            assert result.exit_code == 1

    with environ(APPRISE_CONFIG="garbage/file/path.yaml"):
        # We will fail to send the notification as the path
        # specified is not loadable
        result = runner.invoke(cli.main, [
            '-b', 'my message',
        ])
        assert result.exit_code == 1

        # We can force an over-ride by specifying a config file on the
        # command line options:
        result = runner.invoke(cli.main, [
            '-b', 'has myTag',
            '--config', str(t2),
            '--tag', 'myTag',
        ])
        assert result.exit_code == 0

    # Just a general test; if both the --config and urls are specified
    # then the the urls trumps all
    result = runner.invoke(cli.main, [
        '-b', 'has myTag',
        '--config', str(t2),
        'good://localhost',
        '--tag', 'fail',
    ])
    # Tags are ignored, URL specified, so it trump config
    assert result.exit_code == 0

    # we just repeat the test as a proof that it only executes
    # the urls despite the fact the --config was specified
    result = runner.invoke(cli.main, [
        '-b', 'reads the url entry only',
        '--config', str(t2),
        'good://localhost',
        '--tag', 'fail',
    ])
    # Tags are ignored, URL specified, so it trump config
    assert result.exit_code == 0

    # once agian, but we call bad://
    result = runner.invoke(cli.main, [
        '-b', 'reads the url entry only',
        '--config', str(t2),
        'bad://localhost',
        '--tag', 'myTag',
    ])
    assert result.exit_code == 1

    # Test Escaping:
    result = runner.invoke(cli.main, [
        '-e',
        '-t', 'test\ntitle',
        '-b', 'test\nbody',
        'good://localhost',
    ])
    assert result.exit_code == 0

    # Test Escaping (without title)
    result = runner.invoke(cli.main, [
        '--interpret-escapes',
        '-b', 'test\nbody',
        'good://localhost',
    ])
    assert result.exit_code == 0


def test_apprise_cli_details(tmpdir):
    """
    CLI: --details (-l)

    """

    runner = CliRunner()

    #
    # Testing the printout of our details
    #   --details or -l
    #
    result = runner.invoke(cli.main, [
        '--details',
    ])
    assert result.exit_code == 0

    result = runner.invoke(cli.main, [
        '-l',
    ])
    assert result.exit_code == 0

    # Reset our matrix
    __reset_matrix()

    # This is a made up class that is just used to verify
    class TestReq01Notification(NotifyBase):
        """
        This class is used to test various requirement configurations
        """

        # Set some requirements
        requirements = {
            'packages_required': [
                'cryptography <= 3.4',
                'ultrasync',
            ],
            'packages_recommended': 'django',
        }

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    NOTIFY_SCHEMA_MAP['req01'] = TestReq01Notification

    # This is a made up class that is just used to verify
    class TestReq02Notification(NotifyBase):
        """
        This class is used to test various requirement configurations
        """

        # Just not enabled at all
        enabled = False

        # Set some requirements
        requirements = {
            # None and/or [] is implied, but jsut to show that the code won't
            # crash if explicitly set this way:
            'packages_required': None,

            'packages_recommended': [
                'cryptography <= 3.4',
            ]
        }

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    NOTIFY_SCHEMA_MAP['req02'] = TestReq02Notification

    # This is a made up class that is just used to verify
    class TestReq03Notification(NotifyBase):
        """
        This class is used to test various requirement configurations
        """

        # Set some requirements (but additionally include a details over-ride)
        requirements = {
            # We can over-ride the default details assigned to our plugin if
            # specified
            'details': _('some specified requirement details'),

            # We can set a string value as well (it does not have to be a list)
            'packages_recommended': 'cryptography <= 3.4'
        }

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    NOTIFY_SCHEMA_MAP['req03'] = TestReq03Notification

    # This is a made up class that is just used to verify
    class TestReq04Notification(NotifyBase):
        """
        This class is used to test a case where our requirements is fixed
        to a None
        """

        # This is the same as saying there are no requirements
        requirements = None

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    NOTIFY_SCHEMA_MAP['req04'] = TestReq04Notification

    # This is a made up class that is just used to verify
    class TestReq05Notification(NotifyBase):
        """
        This class is used to test a case where only packages_recommended
        is identified
        """

        requirements = {
            'packages_recommended': 'cryptography <= 3.4'
        }

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    NOTIFY_SCHEMA_MAP['req05'] = TestReq04Notification

    class TestDisabled01Notification(NotifyBase):
        """
        This class is used to test a pre-disabled state
        """

        # Just flat out disable our service
        enabled = False

        # we'll use this as a key to make our service easier to find
        # in the next part of the testing
        service_name = 'na01'

        def url(self, **kwargs):
            # Support URL
            return ''

        def notify(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    NOTIFY_SCHEMA_MAP['na01'] = TestDisabled01Notification

    class TestDisabled02Notification(NotifyBase):
        """
        This class is used to test a post-disabled state
        """

        # we'll use this as a key to make our service easier to find
        # in the next part of the testing
        service_name = 'na02'

        def __init__(self, *args, **kwargs):
            super(TestDisabled02Notification, self).__init__(**kwargs)

            # enable state changes **AFTER** we initialize
            self.enabled = False

        def url(self, **kwargs):
            # Support URL
            return ''

        def notify(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    NOTIFY_SCHEMA_MAP['na02'] = TestDisabled02Notification

    # We'll add a good notification to our list
    class TesEnabled01Notification(NotifyBase):
        """
        This class is just a simple enabled one
        """

        # we'll use this as a key to make our service easier to find
        # in the next part of the testing
        service_name = 'good'

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    NOTIFY_SCHEMA_MAP['good'] = TesEnabled01Notification

    # Verify that we can pass through all of our different details
    result = runner.invoke(cli.main, [
        '--details',
    ])
    assert result.exit_code == 0

    result = runner.invoke(cli.main, [
        '-l',
    ])
    assert result.exit_code == 0

    # Reset our matrix
    __reset_matrix()
    __load_matrix()


@mock.patch('requests.post')
def test_apprise_cli_plugin_loading(mock_post, tmpdir):
    """
    CLI: --plugin-path (-P)

    """
    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    runner = CliRunner()

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    PATHS_PREVIOUSLY_SCANNED.clear()
    NOTIFY_CUSTOM_MODULE_MAP.clear()

    # Test a path that has no files to load in it
    result = runner.invoke(cli.main, [
        '--plugin-path', join(str(tmpdir), 'invalid_path'),
        '-b', 'test\nbody',
        'json://localhost',
    ])
    # The path is silently loaded but fails... it's okay because the
    # notification we're choosing to notify does exist
    assert result.exit_code == 0

    # Directories that don't exist passed in by the CLI aren't even scanned
    assert len(PATHS_PREVIOUSLY_SCANNED) == 0
    assert len(NOTIFY_CUSTOM_MODULE_MAP) == 0

    # Test our current existing path that has no entries in it
    result = runner.invoke(cli.main, [
        '--plugin-path', str(tmpdir.mkdir('empty')),
        '-b', 'test\nbody',
        'json://localhost',
    ])
    # The path is silently loaded but fails... it's okay because the
    # notification we're choosing to notify does exist
    assert result.exit_code == 0
    assert len(PATHS_PREVIOUSLY_SCANNED) == 1
    assert join(str(tmpdir), 'empty') in PATHS_PREVIOUSLY_SCANNED

    # However there was nothing to load
    assert len(NOTIFY_CUSTOM_MODULE_MAP) == 0

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    PATHS_PREVIOUSLY_SCANNED.clear()
    NOTIFY_CUSTOM_MODULE_MAP.clear()

    # Prepare ourselves a file to work with
    notify_hook_a_base = tmpdir.mkdir('random')
    notify_hook_a = notify_hook_a_base.join('myhook01.py')
    notify_hook_a.write(cleandoc("""
    raise ImportError
    """))

    result = runner.invoke(cli.main, [
        '--plugin-path', str(notify_hook_a),
        '-b', 'test\nbody',
        # A custom hook:
        'clihook://',
    ])
    # It doesn't exist so it will fail
    # meanwhile we would have failed to load the myhook path
    assert result.exit_code == 1

    # The path is silently loaded but fails... it's okay because the
    # notification we're choosing to notify does exist
    assert len(PATHS_PREVIOUSLY_SCANNED) == 1
    assert str(notify_hook_a) in PATHS_PREVIOUSLY_SCANNED
    # However there was nothing to load
    assert len(NOTIFY_CUSTOM_MODULE_MAP) == 0

    # Prepare ourselves a file to work with
    notify_hook_aa = notify_hook_a_base.join('myhook02.py')
    notify_hook_aa.write(cleandoc("""
    garbage entry
    """))

    result = runner.invoke(cli.main, [
        '--plugin-path', str(notify_hook_aa),
        '-b', 'test\nbody',
        # A custom hook:
        'clihook://',
    ])
    # It doesn't exist so it will fail
    # meanwhile we would have failed to load the myhook path
    assert result.exit_code == 1

    # The path is silently loaded but fails...
    # as a result the path stacks with the last
    assert len(PATHS_PREVIOUSLY_SCANNED) == 2
    assert str(notify_hook_a) in PATHS_PREVIOUSLY_SCANNED
    assert str(notify_hook_aa) in PATHS_PREVIOUSLY_SCANNED
    # However there was nothing to load
    assert len(NOTIFY_CUSTOM_MODULE_MAP) == 0

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    PATHS_PREVIOUSLY_SCANNED.clear()
    NOTIFY_CUSTOM_MODULE_MAP.clear()

    # Prepare ourselves a file to work with
    notify_hook_b = tmpdir.mkdir('goodmodule').join('__init__.py')
    notify_hook_b.write(cleandoc("""
    from apprise.decorators import notify

    # We want to trigger on anyone who configures a call to clihook://
    @notify(on="clihook")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        # A simple test - print to screen
        print("{}: {} - {}".format(notify_type, title, body))

        # No return (so a return of None) get's translated to True
    """))

    result = runner.invoke(cli.main, [
        '--plugin-path', str(tmpdir),
        '-b', 'test body',
        # A custom hook:
        'clihook://',
    ])

    # We can detect the goodmodule (which has an __init__.py in it)
    # so we'll load okay
    assert result.exit_code == 0

    # Let's see how things got loaded:
    assert len(PATHS_PREVIOUSLY_SCANNED) == 2
    assert str(tmpdir) in PATHS_PREVIOUSLY_SCANNED
    # absolute path to detected module is also added
    assert join(str(tmpdir), 'goodmodule', '__init__.py') \
        in PATHS_PREVIOUSLY_SCANNED

    # We also loaded our clihook properly
    assert len(NOTIFY_CUSTOM_MODULE_MAP) == 1

    # We can find our new hook loaded in our NOTIFY_SCHEMA_MAP now...
    assert 'clihook' in NOTIFY_SCHEMA_MAP

    # Capture our key for reference
    key = [k for k in NOTIFY_CUSTOM_MODULE_MAP.keys()][0]

    assert len(NOTIFY_CUSTOM_MODULE_MAP[key]['notify']) == 1
    assert 'clihook' in NOTIFY_CUSTOM_MODULE_MAP[key]['notify']

    # Our function name
    assert NOTIFY_CUSTOM_MODULE_MAP[key]['notify']['clihook']['fn_name'] \
        == 'mywrapper'
    # What we parsed from the `on` keyword in the @notify decorator
    assert NOTIFY_CUSTOM_MODULE_MAP[key]['notify']['clihook']['url'] \
        == 'clihook://'
    # our default name Assignment.  This can be-overridden on the @notify
    # decorator by just adding a name= to the parameter list
    assert NOTIFY_CUSTOM_MODULE_MAP[key]['notify']['clihook']['name'] \
        == 'Custom - clihook'

    # Our Base Notification object when initialized:
    assert isinstance(
        NOTIFY_CUSTOM_MODULE_MAP[key]['notify']['clihook']['plugin'](),
        NotifyBase)

    # This is how it ties together in the backend
    assert NOTIFY_CUSTOM_MODULE_MAP[key]['notify']['clihook']['plugin'] == \
        NOTIFY_SCHEMA_MAP['clihook']

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    PATHS_PREVIOUSLY_SCANNED.clear()
    NOTIFY_CUSTOM_MODULE_MAP.clear()
    del NOTIFY_SCHEMA_MAP['clihook']

    result = runner.invoke(cli.main, [
        '--plugin-path', str(notify_hook_b),
        '-b', 'test body',
        # A custom hook:
        'clihook://',
    ])

    # Absolute path to __init__.py is okay
    assert result.exit_code == 0

    # we can verify that it prepares our message
    assert result.stdout.strip() == 'info:  - test body'

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    PATHS_PREVIOUSLY_SCANNED.clear()
    NOTIFY_CUSTOM_MODULE_MAP.clear()
    del NOTIFY_SCHEMA_MAP['clihook']

    result = runner.invoke(cli.main, [
        '--plugin-path', dirname(str(notify_hook_b)),
        '-b', 'test body',
        # A custom hook:
        'clihook://',
    ])

    # Now we succeed to load our module when pointed to it only because
    # an __init__.py is found on the inside of it
    assert result.exit_code == 0

    # we can verify that it prepares our message
    assert result.stdout.strip() == 'info:  - test body'

    # Test double paths that are the same; this ensures we only
    # load the plugin once
    result = runner.invoke(cli.main, [
        '--plugin-path', dirname(str(notify_hook_b)),
        '--plugin-path', str(notify_hook_b),
        '--details',
    ])

    # Now we succeed to load our module when pointed to it only because
    # an __init__.py is found on the inside of it
    assert result.exit_code == 0

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    PATHS_PREVIOUSLY_SCANNED.clear()
    NOTIFY_CUSTOM_MODULE_MAP.clear()
    del NOTIFY_SCHEMA_MAP['clihook']

    # Prepare ourselves a file to work with
    notify_hook_b = tmpdir.mkdir('complex').join('complex.py')
    notify_hook_b.write(cleandoc("""
    from apprise.decorators import notify

    # We can't over-ride an element that already exists
    # in this case json://
    @notify(on="json")
    def mywrapper_01(body, title, notify_type, *args, **kwargs):
        # Return True (same as None)
        return True

    @notify(on="willfail", name="always failing...")
    def mywrapper_02(body, title, notify_type, *args, **kwargs):
        # Simply fail
        return False

    @notify(on="clihook1", name="the original clihook entry")
    def mywrapper_03(body, title, notify_type, *args, **kwargs):
        # Return True
        return True

    # This is a duplicate o the entry above, so it can not be
    # loaded...
    @notify(on="clihook1", name="a duplicate of the clihook entry")
    def mywrapper_04(body, title, notify_type, *args, **kwargs):
        # Return True
        return True

    # This is where things get realy cool... we can not only
    # define the schema we want to over-ride, but we can define
    # some default values to pass into our wrapper function to
    # act as a base before whatever was actually passed in is
    # applied ontop.... think of it like templating information
    @notify(on="clihook2://localhost")
    def mywrapper_05(body, title, notify_type, *args, **kwargs):
        # Return True
        return True


    # This can't load because of the defined schema/on definition
    @notify(on="", name="an invalid schema was specified")
    def mywrapper_06(body, title, notify_type, *args, **kwargs):
        return True
    """))

    result = runner.invoke(cli.main, [
        '--plugin-path', join(str(tmpdir), 'complex'),
        '-b', 'test body',
        # A custom hook that does not exist
        'clihook://',
    ])

    # Since clihook:// isn't in our complex listing, this will fail
    assert result.exit_code == 1

    # Let's see how things got loaded
    assert len(PATHS_PREVIOUSLY_SCANNED) == 2
    # Our path we specified on the CLI...
    assert join(str(tmpdir), 'complex') in PATHS_PREVIOUSLY_SCANNED

    # absolute path to detected module is also added
    assert join(str(tmpdir), 'complex', 'complex.py') \
        in PATHS_PREVIOUSLY_SCANNED

    # We loaded our one module successfuly
    assert len(NOTIFY_CUSTOM_MODULE_MAP) == 1

    # We can find our new hook loaded in our SCHEMA_MAP now...
    assert 'willfail' in NOTIFY_SCHEMA_MAP
    assert 'clihook1' in NOTIFY_SCHEMA_MAP
    assert 'clihook2' in NOTIFY_SCHEMA_MAP

    # Capture our key for reference
    key = [k for k in NOTIFY_CUSTOM_MODULE_MAP.keys()][0]

    assert len(NOTIFY_CUSTOM_MODULE_MAP[key]['notify']) == 3
    assert 'willfail' in NOTIFY_CUSTOM_MODULE_MAP[key]['notify']
    assert 'clihook1' in NOTIFY_CUSTOM_MODULE_MAP[key]['notify']
    # We only load 1 instance of the clihook2, the second will fail
    assert 'clihook2' in NOTIFY_CUSTOM_MODULE_MAP[key]['notify']
    # We can never load previously created notifications
    assert 'json' not in NOTIFY_CUSTOM_MODULE_MAP[key]['notify']

    result = runner.invoke(cli.main, [
        '--plugin-path', join(str(tmpdir), 'complex'),
        '-b', 'test body',
        # A custom notification set up for failure
        'willfail://',
    ])
    # Note that the failure of the decorator carries all the way back
    # to the CLI
    assert result.exit_code == 1

    result = runner.invoke(cli.main, [
        '--plugin-path', join(str(tmpdir), 'complex'),
        '-b', 'test body',
        # our clihook that returns true
        'clihook1://',
        # our other loaded clihook
        'clihook2://',
    ])
    # Note that the failure of the decorator carries all the way back
    # to the CLI
    assert result.exit_code == 0

    result = runner.invoke(cli.main, [
        '--plugin-path', join(str(tmpdir), 'complex'),
        # Print our custom details to the screen
        '--details',
    ])
    assert 'willfail' in result.stdout
    assert 'always failing...' in result.stdout

    assert 'clihook1' in result.stdout
    assert 'the original clihook entry' in result.stdout
    assert 'a duplicate of the clihook entry' not in result.stdout

    assert 'clihook2' in result.stdout
    assert 'Custom - clihook2' in result.stdout

    # Note that the failure of the decorator carries all the way back
    # to the CLI
    assert result.exit_code == 0


@mock.patch('platform.system')
def test_apprise_cli_windows_env(mock_system):
    """
    CLI: Windows Environment

    """
    # Force a windows environment
    mock_system.return_value = 'Windows'

    # Reload our module
    reload(cli)
