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

import pytest

from apprise.attachment.base import AttachBase

logging.disable(logging.CRITICAL)


def test_mimetype_initialization():
    """
    API: AttachBase() mimetype initialization

    """
    with (
        mock.patch("mimetypes.init") as mock_init,
        mock.patch("mimetypes.inited", True),
    ):
        AttachBase()
        assert mock_init.call_count == 0

    with (
        mock.patch("mimetypes.init") as mock_init,
        mock.patch("mimetypes.inited", False),
    ):
        AttachBase()
        assert mock_init.call_count == 1


def test_attach_base():
    """
    API: AttachBase()

    """
    # an invalid mime-type
    with pytest.raises(TypeError):
        AttachBase(**{"mimetype": "invalid"})

    # a valid mime-type does not cause an exception to throw
    AttachBase(**{"mimetype": "image/png"})

    # Create an object with no mimetype over-ride
    obj = AttachBase()

    # Get our url object
    str(obj)

    # We can not process name/path/mimetype at a Base level
    with pytest.raises(NotImplementedError):
        obj.download()

    # Unsupported URLs are not parsed
    assert AttachBase.parse_url(url="invalid://") is None

    # Valid URL & Valid Format
    results = AttachBase.parse_url(url="file://relative/path")
    assert isinstance(results, dict)
    # No mime is defined
    assert results.get("mimetype") is None

    # Valid URL & Valid Format with mime type set
    results = AttachBase.parse_url(url="file://relative/path?mime=image/jpeg")
    assert isinstance(results, dict)
    # mime defined
    assert results.get("mimetype") == "image/jpeg"
    # We can retrieve our url
    assert str(results)
