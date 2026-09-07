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

import errno
import logging

import pytest

from apprise.exception import (
    AppriseDiskIOError,
    AppriseException,
    AppriseFileNotFound,
    AppriseImproperlyConfigured,
    AppriseInvalidData,
    ApprisePluginException,
)

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)


def test_appriseexception_base_behavior():
    """AppriseException stores the message and defaults error_code to 0."""
    exc = AppriseException("something went wrong")
    assert str(exc) == "something went wrong"
    assert exc.error_code == 0

    exc = AppriseException("with a code", error_code=42)
    assert exc.error_code == 42


def test_appriseplugin_exception_defaults():
    """ApprisePluginException defaults its error_code to 600."""
    exc = ApprisePluginException("plugin failure")
    assert isinstance(exc, AppriseException)
    assert exc.error_code == 600

    exc = ApprisePluginException("plugin failure", error_code=503)
    assert exc.error_code == 503


def test_appriseimproperlyconfigured_is_apprise_exception():
    """AppriseImproperlyConfigured is a first-class AppriseException."""
    exc = AppriseImproperlyConfigured("bad config")
    assert isinstance(exc, AppriseException)
    assert exc.error_code == errno.EINVAL


def test_appriseimproperlyconfigured_builtin_compatibility():
    """The new exception remains compatible with historical built-ins."""
    exc = AppriseImproperlyConfigured("bad config")
    assert isinstance(exc, TypeError)
    assert isinstance(exc, ValueError)
    assert isinstance(exc, AttributeError)

    for builtin in (TypeError, ValueError, AttributeError):
        with pytest.raises(builtin):
            raise AppriseImproperlyConfigured("bad config")

    with pytest.raises(AppriseException):
        raise AppriseImproperlyConfigured("bad config")


def test_appriseinvaliddata_defaults():
    """AppriseInvalidData defaults its error_code to EINVAL."""
    exc = AppriseInvalidData("bad data")
    assert isinstance(exc, AppriseException)
    assert exc.error_code == errno.EINVAL


def test_apprisediskioerror_is_oserror():
    """AppriseDiskIOError supplies standard and Apprise error details."""
    exc = AppriseDiskIOError("disk failure")
    assert isinstance(exc, AppriseException)
    assert isinstance(exc, OSError)
    assert exc.error_code == errno.EIO
    assert exc.errno == errno.EIO
    assert exc.strerror == "disk failure"
    assert str(exc) == "disk failure"

    with pytest.raises(OSError):
        raise AppriseDiskIOError("disk failure")

    custom = AppriseDiskIOError("disk full", error_code=errno.ENOSPC)
    assert custom.error_code == errno.ENOSPC
    assert custom.errno == errno.ENOSPC
    assert custom.strerror == "disk full"


def test_apprisefilenotfound_is_filenotfounderror():
    """AppriseFileNotFound remains catchable as FileNotFoundError/OSError."""
    exc = AppriseFileNotFound("missing attachment")
    assert isinstance(exc, AppriseDiskIOError)
    assert isinstance(exc, FileNotFoundError)
    assert isinstance(exc, OSError)
    assert exc.error_code == errno.ENOENT
    assert exc.errno == errno.ENOENT
    assert exc.strerror == "missing attachment"
    assert str(exc) == "missing attachment"
