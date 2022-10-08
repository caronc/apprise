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
