# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from apprise import AppriseAsset
from apprise.config.file import ConfigFile
from apprise.plugins import NotifyBase

logging.disable(logging.CRITICAL)


def test_config_file(tmpdir):
    """
    API: ConfigFile() object

    """

    assert ConfigFile.parse_url("garbage://") is None

    # Test cases where our URL is invalid
    t = tmpdir.mkdir("testing").join("apprise")
    t.write("gnome://")

    assert ConfigFile.parse_url("file://?") is None

    # Create an Apprise asset we can reference
    asset = AppriseAsset()

    # Initialize our object
    cf = ConfigFile(path=str(t), format="text", asset=asset)

    # one entry added
    assert len(cf) == 1

    assert isinstance(cf.url(), str) is True

    # Verify that we're using the same asset
    assert cf[0].asset is asset

    # Testing of pop
    cf = ConfigFile(path=str(t), format="text")

    ref = cf[0]
    assert isinstance(ref, NotifyBase) is True

    ref_popped = cf.pop(0)
    assert isinstance(ref_popped, NotifyBase) is True

    assert ref == ref_popped

    assert len(cf) == 0

    # reference to calls on initial reference
    cf = ConfigFile(path=str(t), format="text")
    assert isinstance(cf.pop(0), NotifyBase) is True

    cf = ConfigFile(path=str(t), format="text")
    assert isinstance(cf[0], NotifyBase) is True
    # Second reference actually uses cache
    assert isinstance(cf[0], NotifyBase) is True

    cf = ConfigFile(path=str(t), format="text")
    # Itereator creation (nothing needed to assert here)
    iter(cf)
    # Second reference actually uses cache
    iter(cf)

    # Cache Handling; cache each request for 30 seconds
    results = ConfigFile.parse_url(f"file://{t!s}?cache=30")
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
    cf = ConfigFile(path=str(t), format="text")

    # Internal Exception would have been thrown and this would fail
    with mock.patch("builtins.open", side_effect=OSError):
        assert cf.read() is None

    # handle case where the file is to large for what was expected:
    max_buffer_size = cf.max_buffer_size
    cf.max_buffer_size = 1
    assert cf.read() is None

    # Restore default value
    cf.max_buffer_size = max_buffer_size
