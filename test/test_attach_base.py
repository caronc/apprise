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
