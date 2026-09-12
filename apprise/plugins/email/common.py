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


import dataclasses

from ...exception import ApprisePluginException
from .smtp import SMTP_DEFAULT_PORTS, SMTPSecureMode


class AppriseEmailException(ApprisePluginException):
    """Raised when an email cannot be prepared."""

    def __init__(self, message, error_code=601):
        super().__init__(message, error_code=error_code)


class WebBaseLogin:
    """Identify the login format expected by an email provider."""

    # User Login must be Email Based
    EMAIL = "Email"

    # Login must use a user ID
    USERID = "UserID"


# Keep the established email name as an alias for the shared SMTP modes.
SecureMailMode = SMTPSecureMode

# Preserve the existing mode-to-default-port format for email callers.
SECURE_MODES = {
    mode: {"default_port": port} for mode, port in SMTP_DEFAULT_PORTS.items()
}


@dataclasses.dataclass
class EmailMessage:
    """Prepared email payload and recipients."""

    recipient: str
    to_addrs: list[str]
    body: str
