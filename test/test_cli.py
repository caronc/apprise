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
import mock
from os.path import dirname
from os.path import join
from apprise import cli
from apprise import NotifyBase
from click.testing import CliRunner
from apprise.plugins import SCHEMA_MAP

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
    SCHEMA_MAP['good'] = GoodNotification
    SCHEMA_MAP['bad'] = BadNotification

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
        '-b', 'has taga',
        '--config', str(t),
        '--tag', 'mytag',
    ])
    assert result.exit_code == 3

    # Same command as the one identified above except we set the --dry-run
    # flag. This causes our list of matched results to be printed only.
    # However, since we don't match anything; we still fail with a return code
    # of 2.
    result = runner.invoke(cli.main, [
        '-b', 'has taga',
        '--config', str(t),
        '--tag', 'mytag',
        '--dry-run'
    ])
    assert result.exit_code == 3

    # Here is a case where we get what was expected; we also attach a file
    result = runner.invoke(cli.main, [
        '-b', 'has taga',
        '--config', str(t),
        '--attach', join(dirname(__file__), 'var', 'apprise-test.gif'),
        '--tag', 'myTag',
    ])
    assert result.exit_code == 0

    # Testing with the --dry-run flag reveals the same positive results
    # because there was at least one match
    result = runner.invoke(cli.main, [
        '-b', 'has taga',
        '--config', str(t),
        '--tag', 'myTag',
        '--dry-run',
    ])
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
