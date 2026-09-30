# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
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

"""Tests for Python 3.9 Compatibility."""

from __future__ import annotations

from unittest import mock

import pytest

from apprise.plugins.irc import protocol


def test_compat_dataclass_keeps_slots():
    """dataclass_compat() passes slots= through on Python 3.10+."""
    # protocol.dataclass is a compat wrapper around
    # apprise.compat.py39._dataclass.
    with (
        mock.patch("apprise.compat.py39._HAS_SLOTS", True),
        mock.patch("apprise.compat.py39._dataclass") as m,
    ):
        sentinel = object()
        m.return_value = sentinel

        assert protocol.dataclass(frozen=True, slots=True) is sentinel
        m.assert_called_once_with(frozen=True, slots=True)


def test_compat_dataclass_drops_slots():
    """dataclass_compat() drops slots= on Python 3.9."""
    with (
        mock.patch("apprise.compat.py39._HAS_SLOTS", False),
        mock.patch("apprise.compat.py39._dataclass") as m,
    ):
        sentinel = object()
        m.return_value = sentinel

        assert protocol.dataclass(frozen=True, slots=True) is sentinel
        m.assert_called_once_with(frozen=True)


def test_compat_dataclass_errors_not_hidden():
    """dataclass_compat() never retries or hides a TypeError."""
    with (
        mock.patch("apprise.compat.py39._HAS_SLOTS", True),
        mock.patch("apprise.compat.py39._dataclass") as m,
    ):
        m.side_effect = TypeError("boom")

        with pytest.raises(TypeError):
            protocol.dataclass(frozen=True, slots=True)

        # The call was made once, with slots still requested
        m.assert_called_once_with(frozen=True, slots=True)
