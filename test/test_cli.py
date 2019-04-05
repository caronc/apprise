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
from apprise import cli
from apprise import NotifyBase
from click.testing import CliRunner
from apprise.plugins import SCHEMA_MAP

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_apprise_cli(tmpdir):
    """
    API: Apprise() CLI

    """

    class GoodNotification(NotifyBase):
        def __init__(self, *args, **kwargs):
            super(GoodNotification, self).__init__(*args, **kwargs)

        def notify(self, **kwargs):
            # Pretend everything is okay
            return True

        def url(self):
            # Support url()
            return ''

    class BadNotification(NotifyBase):
        def __init__(self, *args, **kwargs):
            super(BadNotification, self).__init__(*args, **kwargs)

        def notify(self, **kwargs):
            # Pretend everything is okay
            return False

        def url(self):
            # Support url()
            return ''

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

    result = runner.invoke(cli.main, [
        '-t', 'test title',
        'good://localhost',
    ], input='test stdin body\n')
    assert result.exit_code == 0

    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        'bad://localhost',
    ])
    assert result.exit_code == 1

    # Write a simple text based configuration file
    t = tmpdir.mkdir("apprise-obj").join("apprise")
    buf = """
    taga,tagb=good://localhost
    tagc=good://nuxref.com
    """
    t.write(buf)

    # This will read our configuration and send 2 notices to
    # each of the above defined good:// entries
    result = runner.invoke(cli.main, [
        '-b', 'test config',
        '--config', str(t),
    ])
    assert result.exit_code == 0

    # This will send out 1 notification because our tag matches
    # one of the entries above
    # translation: has taga
    result = runner.invoke(cli.main, [
        '-b', 'has taga',
        '--config', str(t),
        '--tag', 'taga',
    ])
    assert result.exit_code == 0

    # This will send out 0 notification because our tag requests that we meet
    # at least 2 tags associated with the same notification service (which
    # isn't the case above)
    # translation: has taga AND tagd
    result = runner.invoke(cli.main, [
        '-b', 'has taga AND tagd',
        '--config', str(t),
        '--tag', 'taga,tagd',
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
