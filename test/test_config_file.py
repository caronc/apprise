# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.

from unittest import mock

from apprise.config.ConfigFile import ConfigFile
from apprise.plugins.NotifyBase import NotifyBase
from apprise.AppriseAsset import AppriseAsset

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_config_file(tmpdir):
    """
    API: ConfigFile() object

    """

    assert ConfigFile.parse_url('garbage://') is None

    # Test cases where our URL is invalid
    t = tmpdir.mkdir("testing").join("apprise")
    t.write("gnome://")

    assert ConfigFile.parse_url('file://?') is None

    # Create an Apprise asset we can reference
    asset = AppriseAsset()

    # Initialize our object
    cf = ConfigFile(path=str(t), format='text', asset=asset)

    # one entry added
    assert len(cf) == 1

    assert isinstance(cf.url(), str) is True

    # Verify that we're using the same asset
    assert cf[0].asset is asset

    # Testing of pop
    cf = ConfigFile(path=str(t), format='text')

    ref = cf[0]
    assert isinstance(ref, NotifyBase) is True

    ref_popped = cf.pop(0)
    assert isinstance(ref_popped, NotifyBase) is True

    assert ref == ref_popped

    assert len(cf) == 0

    # reference to calls on initial reference
    cf = ConfigFile(path=str(t), format='text')
    assert isinstance(cf.pop(0), NotifyBase) is True

    cf = ConfigFile(path=str(t), format='text')
    assert isinstance(cf[0], NotifyBase) is True
    # Second reference actually uses cache
    assert isinstance(cf[0], NotifyBase) is True

    cf = ConfigFile(path=str(t), format='text')
    # Itereator creation (nothing needed to assert here)
    iter(cf)
    # Second reference actually uses cache
    iter(cf)

    # Cache Handling; cache each request for 30 seconds
    results = ConfigFile.parse_url(
        'file://{}?cache=30'.format(str(t)))
    assert isinstance(results, dict)
    cf = ConfigFile(**results)
    assert isinstance(cf.url(), str) is True
    assert isinstance(cf.read(), str) is True


def test_config_file_exceptions(tmpdir):
    """
    API: ConfigFile() i/o exception handling

    """

    # Test cases where our URL is invalid
    t = tmpdir.mkdir("testing").join("apprise")
    t.write("gnome://")

    # Initialize our object
    cf = ConfigFile(path=str(t), format='text')

    # Internal Exception would have been thrown and this would fail
    with mock.patch('builtins.open', side_effect=OSError):
        assert cf.read() is None

    # handle case where the file is to large for what was expected:
    max_buffer_size = cf.max_buffer_size
    cf.max_buffer_size = 1
    assert cf.read() is None

    # Restore default value
    cf.max_buffer_size = max_buffer_size
