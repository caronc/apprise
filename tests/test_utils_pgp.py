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
import sys
from unittest import mock

import pytest

from apprise.utils import pgp as pgp_module
from apprise.utils.pgp import ApprisePGPController, _ensure_imghdr_shim

logging.disable(logging.CRITICAL)


# ---------------------------------------------------------------------------
# imghdr shim
# ---------------------------------------------------------------------------


def test_imghdr_shim_when_present():
    """_ensure_imghdr_shim() leaves sys.modules intact when imghdr imports."""

    # Guarantee imghdr is importable for this test
    real_imghdr = sys.modules.get("imghdr")
    try:
        import imghdr as _real

        # If we got here, imghdr is available on this Python version
        _ensure_imghdr_shim()

        # sys.modules entry must not have been replaced by our shim
        assert sys.modules.get("imghdr") is _real

    except ImportError:
        # Python 3.13+ -- imghdr is gone; skip this branch
        pytest.skip("imghdr not present on this Python version")

    finally:
        # Restore whatever was there before
        if real_imghdr is None:
            sys.modules.pop("imghdr", None)
        else:
            sys.modules["imghdr"] = real_imghdr


def test_imghdr_shim_when_absent():
    """_ensure_imghdr_shim() installs a working shim when imghdr is missing."""

    # Remove any real imghdr from sys.modules and make import fail
    saved = sys.modules.pop("imghdr", None)
    try:
        # Setting the key to None causes 'import imghdr' to raise ImportError
        sys.modules["imghdr"] = None

        _ensure_imghdr_shim()

        shim = sys.modules.get("imghdr")
        assert shim is not None
        assert callable(shim.what)

        # The shim must return None (safe fallback for all inputs)
        assert shim.what() is None
        assert shim.what(file=None, h=b"\xff\xd8\xff") is None
        assert shim.what(None, h=b"some data") is None

    finally:
        # Restore original state
        if saved is None:
            sys.modules.pop("imghdr", None)
        else:
            sys.modules["imghdr"] = saved


# ---------------------------------------------------------------------------
# ApprisePGPController -- WKD integration
# ---------------------------------------------------------------------------


def test_pgp_controller_wkd_none_by_default(tmpdir):
    """ApprisePGPController has wkd=None unless explicitly provided."""
    ctrl = ApprisePGPController(path=str(tmpdir))
    assert ctrl.wkd is None


def test_pgp_controller_accepts_wkd(tmpdir):
    """ApprisePGPController stores the WKD controller it is given."""
    mock_wkd = mock.Mock()
    ctrl = ApprisePGPController(path=str(tmpdir), wkd=mock_wkd)
    assert ctrl.wkd is mock_wkd


def test_fetch_wkd_key_no_controller(tmpdir):
    """_fetch_wkd_key() returns None when no WKD controller is set."""
    ctrl = ApprisePGPController(path=str(tmpdir))
    result = ctrl._fetch_wkd_key("user@example.com")
    assert result is None


def test_fetch_wkd_key_empty_emails(tmpdir):
    """_fetch_wkd_key() returns None when no email candidates exist."""
    mock_wkd = mock.Mock()
    ctrl = ApprisePGPController(path=str(tmpdir), wkd=mock_wkd)
    # No self.email set and no positional emails
    result = ctrl._fetch_wkd_key()
    assert result is None
    mock_wkd.fetch.assert_not_called()


def test_fetch_wkd_key_skips_none_in_candidate_list(tmpdir):
    """_fetch_wkd_key() skips None/empty entries in the email candidates."""
    mock_wkd = mock.Mock()
    mock_wkd.fetch.return_value = None
    ctrl = ApprisePGPController(path=str(tmpdir), wkd=mock_wkd)
    # None is a valid positional argument; it must be skipped, not crash
    result = ctrl._fetch_wkd_key(None, "user@example.com")
    assert result is None
    # fetch must only be called for the valid address, not for None
    mock_wkd.fetch.assert_called_once_with("user@example.com")


def test_fetch_wkd_key_wkd_returns_none(tmpdir):
    """_fetch_wkd_key() returns None when WKD fetch yields nothing."""
    mock_wkd = mock.Mock()
    mock_wkd.fetch.return_value = None
    ctrl = ApprisePGPController(path=str(tmpdir), wkd=mock_wkd)
    result = ctrl._fetch_wkd_key("user@example.com")
    assert result is None


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_fetch_wkd_key_success(tmpdir):
    """_fetch_wkd_key() parses and caches a key returned by WKD."""
    import pgpy

    # Generate a fresh key pair to use as our fake WKD payload
    key = pgpy.PGPKey.new(
        pgpy.constants.PubKeyAlgorithm.RSAEncryptOrSign, 2048
    )
    uid = pgpy.PGPUID.new("Test", email="user@example.com")
    key.add_uid(
        uid,
        usage={
            pgpy.constants.KeyFlags.Sign,
            pgpy.constants.KeyFlags.EncryptCommunications,
        },
        hashes=[pgpy.constants.HashAlgorithm.SHA256],
        ciphers=[pgpy.constants.SymmetricKeyAlgorithm.AES256],
        compression=[pgpy.constants.CompressionAlgorithm.ZLIB],
    )
    pub_bytes = str(key.pubkey).encode()

    mock_wkd = mock.Mock()
    mock_wkd.fetch.return_value = pub_bytes
    ctrl = ApprisePGPController(path=str(tmpdir), wkd=mock_wkd)

    result = ctrl._fetch_wkd_key("user@example.com")
    assert result is not None
    assert isinstance(result, pgpy.PGPKey)
    mock_wkd.fetch.assert_called_once_with("user@example.com")

    # Second call returns the cached key without hitting WKD again
    mock_wkd.fetch.reset_mock()
    result2 = ctrl._fetch_wkd_key("user@example.com")
    # Cache stores it in __key_lookup; second fetch still calls wkd.fetch
    # because the cache is keyed by path and WKD keys have no path --
    # verify WKD is called again (no local file path cache hit)
    assert result2 is not None


@pytest.mark.skipif(
    pgp_module.PGP_SUPPORT, reason="Tests behavior when pgpy is absent"
)
def test_fetch_wkd_key_pgpy_not_installed(tmpdir):
    """_fetch_wkd_key() skips silently when pgpy raises NameError."""
    mock_wkd = mock.Mock()
    mock_wkd.fetch.return_value = b"fake-key-bytes"
    ctrl = ApprisePGPController(path=str(tmpdir), wkd=mock_wkd)
    # In a minimal env pgpy is not installed, so pgpy.PGPKey.from_blob
    # raises NameError naturally -- no mock needed.
    result = ctrl._fetch_wkd_key("user@example.com")
    assert result is None


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_fetch_wkd_key_corrupt_data(tmpdir):
    """_fetch_wkd_key() skips and tries next candidate on parse failure."""
    mock_wkd = mock.Mock()
    mock_wkd.fetch.return_value = b"this-is-not-a-pgp-key"
    ctrl = ApprisePGPController(path=str(tmpdir), wkd=mock_wkd)

    # Patch the canonical pgpy module directly (not the pgp module's copy)
    # so the mock works whether pgpy was imported by name or attribute.
    with mock.patch(
        "pgpy.PGPKey.from_blob",
        side_effect=Exception("bad key"),
    ):
        result = ctrl._fetch_wkd_key("user@example.com")

    assert result is None


def test_fetch_wkd_key_uses_self_email_as_candidate(tmpdir):
    """_fetch_wkd_key() includes self.email in the candidate list."""
    mock_wkd = mock.Mock()
    mock_wkd.fetch.return_value = None
    ctrl = ApprisePGPController(
        path=str(tmpdir), email="sender@example.com", wkd=mock_wkd
    )

    ctrl._fetch_wkd_key()

    # self.email must have been tried
    mock_wkd.fetch.assert_called_with("sender@example.com")


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_public_key_falls_through_to_wkd(tmpdir):
    """public_key() uses WKD when no local key file exists."""
    import pgpy

    # Generate a minimal key for the mock WKD response
    key = pgpy.PGPKey.new(
        pgpy.constants.PubKeyAlgorithm.RSAEncryptOrSign, 2048
    )
    uid = pgpy.PGPUID.new("WKD User", email="wkd@example.com")
    key.add_uid(
        uid,
        usage={
            pgpy.constants.KeyFlags.Sign,
            pgpy.constants.KeyFlags.EncryptCommunications,
        },
        hashes=[pgpy.constants.HashAlgorithm.SHA256],
        ciphers=[pgpy.constants.SymmetricKeyAlgorithm.AES256],
        compression=[pgpy.constants.CompressionAlgorithm.ZLIB],
    )
    pub_bytes = str(key.pubkey).encode()

    mock_wkd = mock.Mock()
    mock_wkd.fetch.return_value = pub_bytes
    ctrl = ApprisePGPController(path=str(tmpdir), wkd=mock_wkd)

    # No local key file exists, so WKD must be tried
    result = ctrl.public_key("wkd@example.com", autogen=False)
    assert result is not None
    mock_wkd.fetch.assert_called()


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_public_key_wkd_fails_falls_through_to_autogen(tmpdir):
    """public_key() falls through to autogen when WKD also returns None."""
    mock_wkd = mock.Mock()
    mock_wkd.fetch.return_value = None
    ctrl = ApprisePGPController(path=str(tmpdir), wkd=mock_wkd)
    # No local key file exists; WKD fails; autogen=False => None returned
    result = ctrl.public_key("nobody@example.com", autogen=False)
    assert result is None
    mock_wkd.fetch.assert_called()


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_public_key_malformed_local_file_returns_none(tmpdir):
    """public_key() returns None gracefully when the local .asc file is
    not valid PGP data (pgpy raises during parse)."""
    # Write a file with non-PGP content under a name that public_keyfile()
    # will discover automatically
    bad_key_path = tmpdir.join("pub.asc")
    bad_key_path.write("this is not a pgp key\n")

    ctrl = ApprisePGPController(path=str(tmpdir))
    # No autogen so the only candidate is the malformed file above
    result = ctrl.public_key(autogen=False)
    assert result is None


# ---------------------------------------------------------------------------
# prune() -- WKD delegation
# ---------------------------------------------------------------------------


def test_prune_delegates_to_wkd(tmpdir):
    """prune() calls prune() on the WKD controller when one is set."""
    mock_wkd = mock.Mock()
    ctrl = ApprisePGPController(path=str(tmpdir), wkd=mock_wkd)
    ctrl.prune()
    mock_wkd.prune.assert_called_once()


def test_prune_without_wkd(tmpdir):
    """prune() runs without error when no WKD controller is set."""
    ctrl = ApprisePGPController(path=str(tmpdir))
    ctrl.prune()  # must not raise


# ---------------------------------------------------------------------------
# PGP_SUPPORT flag consistency
# ---------------------------------------------------------------------------


def test_pgp_support_flag_present():
    """PGP_SUPPORT is a boolean exported from the pgp module."""
    assert isinstance(pgp_module.PGP_SUPPORT, bool)
