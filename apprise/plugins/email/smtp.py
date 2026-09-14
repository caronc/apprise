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

# Shared SMTP connection handling for Email and its subclasses.

import contextlib
import smtplib
import ssl
from typing import Optional

from ...exception import AppriseImproperlyConfigured
from ...logger import logger


class SMTPSecureMode:
    """SMTP transport security mode."""

    # No transport security at all
    INSECURE = "insecure"

    # Implicit TLS from the first byte of the connection
    SSL = "ssl"

    # Plaintext connection upgraded to TLS via STARTTLS
    STARTTLS = "starttls"


# Every valid secure mode
SMTP_SECURE_MODES = (
    SMTPSecureMode.STARTTLS,
    SMTPSecureMode.SSL,
    SMTPSecureMode.INSECURE,
)

# Default SMTP submission port per security mode
SMTP_DEFAULT_PORTS = {
    SMTPSecureMode.STARTTLS: 587,
    SMTPSecureMode.SSL: 465,
    SMTPSecureMode.INSECURE: 25,
}

# The exceptions every SMTP operation in this module guards against
SMTP_EXCEPTIONS = (OSError, smtplib.SMTPException, RuntimeError)


class AppriseSMTPController:
    """Manage one authenticated SMTP connection within a context manager.

    ``sendmail()`` returns false for delivery errors. Connection and login
    errors leave the context so the plugin can report the whole send as failed.

        with AppriseSMTPController(
            host=host, port=port, secure_mode=secure_mode,
            user=user, password=password,
        ) as smtp:
            for target in targets:
                message = build_message(target)
                if not smtp.sendmail(from_addr, [target], message):
                    has_error = True
    """

    def __init__(
        self,
        host: str,
        port: int,
        secure_mode: str,
        user: Optional[str] = None,
        password: Optional[str] = None,
        verify_certificate: bool = True,
        socket_connect_timeout: int = 15,
    ) -> None:
        self.host = host
        self.port = port
        self.secure_mode = secure_mode
        self.user = user
        self.password = password
        self.verify_certificate = verify_certificate
        self.socket_connect_timeout = socket_connect_timeout

        # Bind our socket variable to the current namespace
        self._socket = None

    def __enter__(self) -> "AppriseSMTPController":
        """Connects, secures, and authenticates the SMTP session."""

        if self.secure_mode not in SMTP_SECURE_MODES:
            # Reject unknown modes rather than silently using plain SMTP.
            raise AppriseImproperlyConfigured(
                f"Invalid SMTP secure mode: {self.secure_mode!r}"
            )

        # Configure certificate and hostname checks for encrypted connections.
        context = ssl.create_default_context()
        if not self.verify_certificate:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        try:
            logger.debug("Connecting to remote SMTP server...")
            socket_func = smtplib.SMTP
            socket_args = {}
            if self.secure_mode == SMTPSecureMode.SSL:
                logger.debug("Securing connection with SSL...")
                socket_func = smtplib.SMTP_SSL
                socket_args["context"] = context

            self._socket = socket_func(
                self.host,
                self.port,
                None,
                timeout=self.socket_connect_timeout,
                **socket_args,
            )

            if self.secure_mode == SMTPSecureMode.STARTTLS:
                # Handle Secure Connections
                logger.debug("Securing connection with STARTTLS...")
                self._socket.starttls(context=context)

            logger.trace("Login ID: %s", self.user)
            if self.user and self.password:
                # Apply Login credentials
                logger.debug("Applying user credentials...")
                self._socket.login(self.user, self.password)

        except SMTP_EXCEPTIONS:
            # Close a connection that failed during STARTTLS or login.
            if self._socket is not None:
                with contextlib.suppress(*SMTP_EXCEPTIONS):
                    self._socket.quit()
                self._socket = None
            raise

        return self

    def sendmail(self, from_addr: str, to_addrs: list, message: str) -> bool:
        """Send one prepared message and return whether it succeeded."""

        try:
            # A non-empty result lists recipients SMTP refused.
            refused = self._socket.sendmail(from_addr, to_addrs, message)

        except SMTP_EXCEPTIONS as e:
            logger.debug("Socket Exception: %s", str(e))
            return False

        if refused:
            for addr, (code, resp) in refused.items():
                logger.warning(
                    "SMTP recipient %s was refused: %s %s", addr, code, resp
                )
            return False

        return True

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Gracefully terminates the connection with the server."""

        if self._socket is not None:
            with contextlib.suppress(*SMTP_EXCEPTIONS):
                # The socket may already be invalid after a TLS failure.
                self._socket.quit()
