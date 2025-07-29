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
import errno


class AppriseException(Exception):
    """Base Apprise Exception Class."""

    def __init__(self, message, error_code=0):
        super().__init__(message)
        self.error_code = error_code


class ApprisePluginException(AppriseException):
    """Class object for handling exceptions raised from within a plugin."""

    def __init__(self, message, error_code=600):
        super().__init__(message, error_code=error_code)


class AppriseDiskIOError(AppriseException):
    """Thrown when an disk i/o error occurs."""

    def __init__(self, message, error_code=errno.EIO):
        super().__init__(message, error_code=error_code)


class AppriseInvalidData(AppriseException):
    """Thrown when bad data was passed into an internal function."""

    def __init__(self, message, error_code=errno.EINVAL):
        super().__init__(message, error_code=error_code)


class AppriseFileNotFound(AppriseDiskIOError, FileNotFoundError):
    """Thrown when a persistent write occured in MEMORY mode."""

    def __init__(self, message):
        super().__init__(message, error_code=errno.ENOENT)
