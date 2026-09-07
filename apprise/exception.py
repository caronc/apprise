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


class AppriseException(Exception):
    """Base class for exceptions raised by Apprise."""

    def __init__(self, message, error_code=0):
        super().__init__(message)
        self.error_code = error_code


class ApprisePluginException(AppriseException):
    """Raised when a notification plugin cannot complete an operation."""

    def __init__(self, message, error_code=600):
        super().__init__(message, error_code=error_code)


class AppriseImproperlyConfigured(
    AppriseException, TypeError, ValueError, AttributeError
):
    """Raised when Apprise receives missing, invalid, or conflicting settings.

    It remains compatible with code that catches the built-in exceptions
    historically raised for these errors: ``TypeError``, ``ValueError``, and
    ``AttributeError``.
    """

    def __init__(self, message, error_code=errno.EINVAL):
        super().__init__(message, error_code=error_code)


class AppriseDiskIOError(AppriseException, OSError):
    """Raised when a disk I/O operation fails."""

    def __init__(self, message, error_code=errno.EIO):
        super().__init__(message, error_code=error_code)
        # Expose the standard I/O error code and message for compatibility
        # with code that catches the built-in OSError.
        self.errno = error_code
        self.strerror = message

    def __str__(self):
        """Return the original message while exposing standard I/O details."""
        return str(self.args[0])


class AppriseInvalidData(AppriseException):
    """Raised when Apprise cannot safely use supplied or stored data."""

    def __init__(self, message, error_code=errno.EINVAL):
        super().__init__(message, error_code=error_code)


class AppriseFileNotFound(AppriseDiskIOError, FileNotFoundError):
    """Raised when an attachment or stored file cannot be found."""

    def __init__(self, message):
        super().__init__(message, error_code=errno.ENOENT)
