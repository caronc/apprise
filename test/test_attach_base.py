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

import pytest
from unittest import mock
from apprise.attachment.AttachBase import AttachBase

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_mimetype_initialization():
    """
    API: AttachBase() mimetype initialization

    """
    with mock.patch('mimetypes.init') as mock_init:
        with mock.patch('mimetypes.inited', True):
            AttachBase()
            assert mock_init.call_count == 0

    with mock.patch('mimetypes.init') as mock_init:
        with mock.patch('mimetypes.inited', False):
            AttachBase()
            assert mock_init.call_count == 1


def test_attach_base():
    """
    API: AttachBase()

    """
    # an invalid mime-type
    with pytest.raises(TypeError):
        AttachBase(**{'mimetype': 'invalid'})

    # a valid mime-type does not cause an exception to throw
    AttachBase(**{'mimetype': 'image/png'})

    # Create an object with no mimetype over-ride
    obj = AttachBase()

    # Get our string object
    with pytest.raises(NotImplementedError):
        str(obj)

    # We can not process name/path/mimetype at a Base level
    with pytest.raises(NotImplementedError):
        obj.download()

    with pytest.raises(NotImplementedError):
        obj.name

    with pytest.raises(NotImplementedError):
        obj.path

    with pytest.raises(NotImplementedError):
        obj.mimetype

    # Unsupported URLs are not parsed
    assert AttachBase.parse_url(url='invalid://') is None

    # Valid URL & Valid Format
    results = AttachBase.parse_url(url='file://relative/path')
    assert isinstance(results, dict)
    # No mime is defined
    assert results.get('mimetype') is None

    # Valid URL & Valid Format with mime type set
    results = AttachBase.parse_url(url='file://relative/path?mime=image/jpeg')
    assert isinstance(results, dict)
    # mime defined
    assert results.get('mimetype') == 'image/jpeg'
    # We can retrieve our url
    assert str(results)
