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

from apprise.config.ConfigMemory import ConfigMemory

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_config_memory():
    """
    API: ConfigMemory() object

    """

    assert ConfigMemory.parse_url('garbage://') is None

    # Initialize our object
    cm = ConfigMemory(content="json://localhost", format='text')

    # one entry added
    assert len(cm) == 1

    # Test general functions
    assert isinstance(cm.url(), str) is True
    assert isinstance(cm.read(), str) is True

    # Test situation where an auto-detect is required:
    cm = ConfigMemory(content="json://localhost")

    # one entry added
    assert len(cm) == 1

    # Test general functions
    assert isinstance(cm.url(), str) is True
    assert isinstance(cm.read(), str) is True

    # Test situation where we can not detect the data
    assert len(ConfigMemory(content="garbage")) == 0
