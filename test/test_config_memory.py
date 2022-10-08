# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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
    cm = ConfigMemory(content="syslog://", format='text')

    # one entry added
    assert len(cm) == 1

    # Test general functions
    assert isinstance(cm.url(), str) is True
    assert isinstance(cm.read(), str) is True

    # Test situation where an auto-detect is required:
    cm = ConfigMemory(content="syslog://")

    # one entry added
    assert len(cm) == 1

    # Test general functions
    assert isinstance(cm.url(), str) is True
    assert isinstance(cm.read(), str) is True

    # Test situation where we can not detect the data
    assert len(ConfigMemory(content="garbage")) == 0
