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

# Disable logging for a cleaner testing output
import logging
import smtplib
from unittest import mock

import pytest

from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.email.smtp import (
    SMTP_DEFAULT_PORTS,
    SMTP_SECURE_MODES,
    AppriseSMTPController,
    SMTPSecureMode,
)

logging.disable(logging.CRITICAL)


def test_smtp_secure_mode_constants():
    """SMTPSecureMode / SMTP_SECURE_MODES / SMTP_DEFAULT_PORTS basics."""

    assert SMTPSecureMode.INSECURE == "insecure"
    assert SMTPSecureMode.SSL == "ssl"
    assert SMTPSecureMode.STARTTLS == "starttls"

    assert set(SMTP_SECURE_MODES) == {
        SMTPSecureMode.STARTTLS,
        SMTPSecureMode.SSL,
        SMTPSecureMode.INSECURE,
    }

    assert SMTP_DEFAULT_PORTS[SMTPSecureMode.STARTTLS] == 587
    assert SMTP_DEFAULT_PORTS[SMTPSecureMode.SSL] == 465
    assert SMTP_DEFAULT_PORTS[SMTPSecureMode.INSECURE] == 25


@mock.patch("smtplib.SMTP")
def test_smtp_controller_starttls_flow(mock_smtp):
    """AppriseSMTPController applies STARTTLS and login in starttls mode."""

    mock_socket = mock.Mock()
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp.return_value = mock_socket

    with AppriseSMTPController(
        host="smtp.example.com",
        port=587,
        secure_mode=SMTPSecureMode.STARTTLS,
        user="user",
        password="pass",
    ) as smtp:
        assert isinstance(smtp, AppriseSMTPController)
        assert smtp.sendmail("from@example.com", ["to@example.com"], "body")

    mock_smtp.assert_called_once_with(
        "smtp.example.com", 587, None, timeout=15
    )
    assert mock_socket.starttls.called
    mock_socket.login.assert_called_once_with("user", "pass")
    mock_socket.sendmail.assert_called_once_with(
        "from@example.com", ["to@example.com"], "body"
    )
    assert mock_socket.quit.called


@mock.patch("smtplib.SMTP_SSL")
def test_smtp_controller_ssl_flow(mock_smtp_ssl):
    """SSL mode uses SMTP_SSL without STARTTLS."""

    mock_socket = mock.Mock()
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp_ssl.return_value = mock_socket

    with AppriseSMTPController(
        host="smtp.example.com",
        port=465,
        secure_mode=SMTPSecureMode.SSL,
    ) as smtp:
        assert smtp.sendmail("from@example.com", ["to@example.com"], "body")

    assert mock_smtp_ssl.called
    assert not mock_socket.starttls.called
    # No credentials supplied; login must not be attempted
    assert not mock_socket.login.called
    assert mock_socket.quit.called


@mock.patch("smtplib.SMTP")
def test_smtp_controller_insecure_flow(mock_smtp):
    """Insecure mode uses plain SMTP."""

    mock_socket = mock.Mock()
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp.return_value = mock_socket

    with AppriseSMTPController(
        host="smtp.example.com",
        port=25,
        secure_mode=SMTPSecureMode.INSECURE,
    ) as smtp:
        assert smtp.sendmail("from@example.com", ["to@example.com"], "body")

    assert not mock_socket.starttls.called
    assert not mock_socket.login.called


@mock.patch("smtplib.SMTP")
def test_smtp_controller_skips_partial_login(mock_smtp):
    """Login requires both a username and password."""

    mock_socket = mock.Mock()
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp.return_value = mock_socket

    with AppriseSMTPController(
        host="smtp.example.com",
        port=25,
        secure_mode=SMTPSecureMode.INSECURE,
        user="user",
        password=None,
    ):
        pass

    assert not mock_socket.login.called


@mock.patch("smtplib.SMTP")
def test_smtp_controller_connect_failure(mock_smtp):
    """A connection failure escapes without attempting to quit."""

    mock_smtp.side_effect = OSError("connection refused")

    with (
        pytest.raises(OSError),
        AppriseSMTPController(
            host="smtp.example.com",
            port=25,
            secure_mode=SMTPSecureMode.INSECURE,
        ),
    ):
        raise AssertionError("should never enter the with block")


@mock.patch("smtplib.SMTP")
def test_smtp_controller_starttls_cleanup(mock_smtp):
    """A STARTTLS failure closes the partial connection."""

    mock_socket = mock.Mock()
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_socket.starttls.side_effect = smtplib.SMTPException("tls failed")
    mock_smtp.return_value = mock_socket

    with (
        pytest.raises(smtplib.SMTPException),
        AppriseSMTPController(
            host="smtp.example.com",
            port=587,
            secure_mode=SMTPSecureMode.STARTTLS,
        ),
    ):
        raise AssertionError("should never enter the with block")

    assert mock_socket.quit.called


@mock.patch("smtplib.SMTP")
def test_smtp_controller_login_cleanup(mock_smtp):
    """A login failure closes the established connection."""

    mock_socket = mock.Mock()
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_socket.login.side_effect = smtplib.SMTPAuthenticationError(
        535, "bad credentials"
    )
    mock_smtp.return_value = mock_socket

    with (
        pytest.raises(smtplib.SMTPAuthenticationError),
        AppriseSMTPController(
            host="smtp.example.com",
            port=587,
            secure_mode=SMTPSecureMode.STARTTLS,
            user="user",
            password="pass",
        ),
    ):
        raise AssertionError("should never enter the with block")

    assert mock_socket.starttls.called
    assert mock_socket.quit.called


@mock.patch("smtplib.SMTP")
def test_smtp_controller_sendmail_exceptions(mock_smtp):
    """Delivery errors return false instead of escaping."""

    mock_socket = mock.Mock()
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp.return_value = mock_socket

    for exception in (
        OSError("boom"),
        smtplib.SMTPHeloError(0, "boom"),
        smtplib.SMTPException(0, "boom"),
        smtplib.SMTPRecipientsRefused("boom"),
        smtplib.SMTPSenderRefused(0, "boom", "addr@example.com"),
        smtplib.SMTPDataError(0, "boom"),
        smtplib.SMTPServerDisconnected("boom"),
        RuntimeError("boom"),
    ):
        mock_socket.sendmail.side_effect = exception
        with AppriseSMTPController(
            host="smtp.example.com",
            port=25,
            secure_mode=SMTPSecureMode.INSECURE,
        ) as smtp:
            assert (
                smtp.sendmail("from@example.com", ["to@example.com"], "body")
                is False
            )


@mock.patch("smtplib.SMTP")
def test_smtp_controller_sendmail_partial_rejection(mock_smtp):
    """A partial recipient rejection makes the delivery fail."""

    mock_socket = mock.Mock()
    mock_socket.sendmail.return_value = {
        "bad@example.com": (550, b"Mailbox unavailable")
    }
    mock_smtp.return_value = mock_socket

    with AppriseSMTPController(
        host="smtp.example.com",
        port=25,
        secure_mode=SMTPSecureMode.INSECURE,
    ) as smtp:
        assert (
            smtp.sendmail(
                "from@example.com",
                ["good@example.com", "bad@example.com"],
                "body",
            )
            is False
        )


@mock.patch("smtplib.SMTP")
def test_smtp_controller_quit_failure_suppressed(mock_smtp):
    """__exit__ suppresses errors raised while closing the connection."""

    mock_socket = mock.Mock()
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_socket.quit.side_effect = smtplib.SMTPServerDisconnected("bye")
    mock_smtp.return_value = mock_socket

    # Must not raise despite quit() failing
    with AppriseSMTPController(
        host="smtp.example.com",
        port=25,
        secure_mode=SMTPSecureMode.INSECURE,
    ):
        pass

    assert mock_socket.quit.called


@mock.patch("smtplib.SMTP")
def test_smtp_controller_quits_on_caller_error(mock_smtp):
    """Caller errors still close the connection and propagate."""

    mock_socket = mock.Mock()
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp.return_value = mock_socket

    with (
        pytest.raises(ValueError),
        AppriseSMTPController(
            host="smtp.example.com",
            port=25,
            secure_mode=SMTPSecureMode.INSECURE,
        ),
    ):
        raise ValueError("caller-side failure")

    assert mock_socket.quit.called


@mock.patch("smtplib.SMTP_SSL")
def test_smtp_controller_disables_verification(mock_smtp_ssl):
    """The verification option controls certificate and hostname checks."""

    mock_socket = mock.Mock()
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp_ssl.return_value = mock_socket

    with AppriseSMTPController(
        host="smtp.example.com",
        port=465,
        secure_mode=SMTPSecureMode.SSL,
        verify_certificate=False,
    ):
        pass

    context = mock_smtp_ssl.call_args.kwargs["context"]
    assert context.check_hostname is False

    import ssl

    assert context.verify_mode == ssl.CERT_NONE


@mock.patch("smtplib.SMTP")
def test_smtp_controller_connect_timeout(mock_smtp):
    """The configured connection timeout reaches smtplib."""

    mock_socket = mock.Mock()
    # An empty refusal map means SMTP accepted every recipient.
    mock_socket.sendmail.return_value = {}
    mock_smtp.return_value = mock_socket

    with AppriseSMTPController(
        host="smtp.example.com",
        port=25,
        secure_mode=SMTPSecureMode.INSECURE,
        socket_connect_timeout=42,
    ):
        pass

    mock_smtp.assert_called_once_with("smtp.example.com", 25, None, timeout=42)


def test_smtp_controller_exit_before_enter():
    """Exiting before entering is harmless."""

    smtp = AppriseSMTPController(
        host="smtp.example.com",
        port=25,
        secure_mode=SMTPSecureMode.INSECURE,
    )
    smtp.__exit__(None, None, None)


def test_smtp_controller_invalid_secure_mode_rejected():
    """Unknown security modes cannot fall back to plain SMTP."""

    with (
        pytest.raises(AppriseImproperlyConfigured),
        AppriseSMTPController(
            host="smtp.example.com",
            port=25,
            secure_mode="bogus",
        ),
    ):
        raise AssertionError("should never enter the with block")
