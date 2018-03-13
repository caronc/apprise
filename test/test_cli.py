# -*- coding: utf-8 -*-
#
# Apprise CLI Unit Tests
#
# Copyright (C) 2017-2018 Chris Caron <lead2gold@gmail.com>
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

from __future__ import print_function
from __future__ import unicode_literals
from apprise import cli
from apprise import NotifyBase
from click.testing import CliRunner
from apprise.Apprise import SCHEMA_MAP


def test_apprise_cli():
    """
    API: Apprise() CLI

    """

    class GoodNotification(NotifyBase):
        def __init__(self, **kwargs):
            super(GoodNotification, self).__init__()

        def notify(self, **kwargs):
            # Pretend everything is okay
            return True

    class BadNotification(NotifyBase):
        def __init__(self, **kwargs):
            super(BadNotification, self).__init__()

        def notify(self, **kwargs):
            # Pretend everything is okay
            return False

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

    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        'good://localhost',
    ])
    assert result.exit_code == 0

    result = runner.invoke(cli.main, [
            '-t', 'test title',
            'good://localhost',
        ],
        input='test stdin body\n',
    )
    assert result.exit_code == 0

    result = runner.invoke(cli.main, [
        '-t', 'test title',
        '-b', 'test body',
        'bad://localhost',
    ])
    assert result.exit_code == 1
