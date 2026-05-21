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
import os
import sys
from unittest import mock

import pytest

from apprise.utils import pgp as pgp_module
from apprise.utils.pgp import ApprisePGPController, _ensure_imghdr_shim

logging.disable(logging.CRITICAL)

# Path to the pre-generated private key fixture used by signing tests
_VAR_DIR = os.path.join(os.path.dirname(__file__), "var", "pgp")
_VALID_PRV_ASC = os.path.join(_VAR_DIR, "valid-prv.asc")


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

    # Second call must use the parsed-key cache -- wkd.fetch must NOT be
    # called again (the cache check now happens before wkd.fetch())
    mock_wkd.fetch.reset_mock()
    result2 = ctrl._fetch_wkd_key("user@example.com")
    assert result2 is not None
    mock_wkd.fetch.assert_not_called()


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_fetch_wkd_key_expired_cache_refetches(tmpdir):
    """_fetch_wkd_key() drops an expired parsed-key cache entry and
    re-fetches from WKD rather than returning the stale key."""
    from datetime import datetime, timedelta, timezone
    import hashlib

    import pgpy

    # Generate a key to serve as the fresh WKD result
    key = pgpy.PGPKey.new(
        pgpy.constants.PubKeyAlgorithm.RSAEncryptOrSign, 2048
    )
    uid = pgpy.PGPUID.new("Fresh", email="user@example.com")
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

    # Seed the parsed-key cache with an already-expired entry
    cache_key = hashlib.sha1(b"wkd:user@example.com").hexdigest()
    # Use the private name-mangled attribute
    ctrl._ApprisePGPController__key_lookup[cache_key] = {
        "public_key": None,
        "expires": datetime.now(timezone.utc) - timedelta(seconds=1),
    }

    # The expired entry is discarded; WKD is fetched and result returned
    result = ctrl._fetch_wkd_key("user@example.com")
    assert result is not None
    mock_wkd.fetch.assert_called_once_with("user@example.com")


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_fetch_wkd_key_prefers_recipient_over_sender(tmpdir):
    """_fetch_wkd_key() tries recipient emails before self.email so that
    the recipient's public key (not the sender's) is used for encryption."""
    import pgpy

    # Generate a key to represent the recipient's WKD result
    key = pgpy.PGPKey.new(
        pgpy.constants.PubKeyAlgorithm.RSAEncryptOrSign, 2048
    )
    uid = pgpy.PGPUID.new("Recipient", email="recipient@example.com")
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

    # WKD returns a key only for the recipient address
    def fake_fetch(email):
        if email == "recipient@example.com":
            return pub_bytes
        return None

    mock_wkd = mock.Mock(side_effect=fake_fetch)
    mock_wkd.fetch.side_effect = fake_fetch
    ctrl = ApprisePGPController(
        path=str(tmpdir),
        email="sender@example.com",
        wkd=mock_wkd,
    )

    # The recipient's email is passed as a positional argument
    result = ctrl._fetch_wkd_key("recipient@example.com")
    assert result is not None
    # sender@example.com must NOT have been tried before the recipient hit
    calls = [call.args[0] for call in mock_wkd.fetch.call_args_list]
    assert calls[0] == "recipient@example.com"
    assert "sender@example.com" not in calls


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


# ---------------------------------------------------------------------------
# private_keyfile() -- path resolution
# ---------------------------------------------------------------------------


def test_private_keyfile_no_path():
    """private_keyfile() returns None when neither path nor prv_keyfile set."""
    ctrl = ApprisePGPController(path=None)
    assert ctrl.private_keyfile() is None


def test_private_keyfile_explicit_valid(tmpdir):
    """private_keyfile() returns a path for a valid explicit prv_keyfile."""
    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=_VALID_PRV_ASC)
    result = ctrl.private_keyfile()
    # Should be an existing file path
    assert result and os.path.isfile(result)


def test_private_keyfile_explicit_invalid(tmpdir):
    """private_keyfile() returns False when an explicit file is unreachable."""
    ctrl = ApprisePGPController(
        path=str(tmpdir),
        prv_keyfile="/nonexistent/path/key.asc",
    )
    # The attachment itself is invalid, so the property returns False
    result = ctrl.private_keyfile()
    assert result is False


def test_private_keyfile_auto_discover_by_email(tmpdir):
    """private_keyfile() finds an auto-generated key named by email prefix."""
    # Place a fake private key named after the email prefix
    key_path = str(tmpdir.join("user-prv.asc"))
    with open(key_path, "w") as f:
        f.write("dummy")

    ctrl = ApprisePGPController(path=str(tmpdir), email="user@example.com")
    result = ctrl.private_keyfile()
    assert result == key_path


def test_private_keyfile_fallback_generic_name(tmpdir):
    """private_keyfile() falls back to pgp-prv.asc when no email-named key."""
    key_path = str(tmpdir.join("pgp-prv.asc"))
    with open(key_path, "w") as f:
        f.write("dummy")

    ctrl = ApprisePGPController(path=str(tmpdir))
    result = ctrl.private_keyfile()
    assert result == key_path


def test_private_keyfile_not_found(tmpdir):
    """private_keyfile() returns None when no private key exists on disk."""
    ctrl = ApprisePGPController(path=str(tmpdir))
    assert ctrl.private_keyfile() is None


def test_prv_keyfile_property_none_when_not_set(tmpdir):
    """prv_keyfile property returns None when no explicit key was provided."""
    ctrl = ApprisePGPController(path=str(tmpdir))
    assert ctrl.prv_keyfile is None


def test_prv_keyfile_property_path_when_valid(tmpdir):
    """prv_keyfile property returns the resolved path for a valid key."""
    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=_VALID_PRV_ASC)
    # Property accesses the attachment; it may return None before loading
    # because the attachment is resolved lazily -- just confirm it is not False
    assert ctrl.prv_keyfile is not False


def test_prv_keyfile_property_false_when_invalid(tmpdir):
    """prv_keyfile property returns False for an unreachable explicit file."""
    ctrl = ApprisePGPController(
        path=str(tmpdir),
        prv_keyfile="/no/such/file.asc",
    )
    assert ctrl.prv_keyfile is False


# ---------------------------------------------------------------------------
# private_key() -- loading the private PGP key object
# ---------------------------------------------------------------------------


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_private_key_loads_valid_fixture(tmpdir):
    """private_key() returns a PGPKey object from a valid private key file."""
    import pgpy

    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=_VALID_PRV_ASC)
    key = ctrl.private_key()
    assert key is not None
    assert isinstance(key, pgpy.PGPKey)


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_private_key_cached_on_second_call(tmpdir):
    """private_key() returns the same object on repeated calls (cached)."""
    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=_VALID_PRV_ASC)
    first = ctrl.private_key()
    second = ctrl.private_key()
    assert first is not None
    assert first is second


def test_private_key_returns_none_when_not_found(tmpdir):
    """private_key() returns None when no private key file exists."""
    ctrl = ApprisePGPController(path=str(tmpdir))
    assert ctrl.private_key() is None


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_private_key_expired_cache_reloads(tmpdir):
    """private_key() drops an expired cache entry and reloads from disk."""
    from datetime import datetime, timedelta, timezone
    import hashlib

    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=_VALID_PRV_ASC)

    # Load the key once to prime the cache
    first = ctrl.private_key()
    assert first is not None

    # Artificially expire the cached entry by back-dating its expiry time
    cache_key = hashlib.sha1(
        ("prv:" + os.path.abspath(_VALID_PRV_ASC)).encode("utf-8")
    ).hexdigest()
    ctrl._ApprisePGPController__key_lookup[cache_key]["expires"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    )

    # Second call must detect the expiry and re-load from disk
    second = ctrl.private_key()
    assert second is not None


def test_private_key_returns_none_when_pgpy_missing(tmpdir):
    """private_key() returns None gracefully when PGPy is not installed."""
    import contextlib

    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=_VALID_PRV_ASC)
    with contextlib.ExitStack() as stack:
        # Force PGP_SUPPORT=True so the key-loading branch is reached
        stack.enter_context(mock.patch.object(pgp_module, "PGP_SUPPORT", True))
        # Supply any readable content for the open() call
        stack.enter_context(
            mock.patch("builtins.open", mock.mock_open(read_data="data"))
        )
        if "pgpy" in sys.modules:
            # When pgpy IS installed, simulate its absence by making
            # from_blob raise NameError (same as if the name were undefined)
            stack.enter_context(
                mock.patch("pgpy.PGPKey.from_blob", side_effect=NameError)
            )
        # Without pgpy installed the NameError arises naturally at the
        # 'pgpy.PGPKey.from_blob(...)' call in private_key(); either way
        # private_key() must swallow the error and return None
        result = ctrl.private_key()
    assert result is None


def test_private_key_returns_none_when_keyfile_inaccessible(tmpdir):
    """private_key() returns None when private_keyfile() returns False."""
    # Provide an invalid path so the attachment reports the file as unreachable
    ctrl = ApprisePGPController(
        path=str(tmpdir), prv_keyfile="/no/such/file.asc"
    )
    # private_keyfile() will return False; private_key() must not raise
    result = ctrl.private_key()
    assert result is None


def test_private_key_returns_none_on_io_error(tmpdir):
    """private_key() returns None when the file cannot be read."""
    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=_VALID_PRV_ASC)
    with mock.patch("builtins.open", side_effect=OSError("disk error")):
        result = ctrl.private_key()
    assert result is None


def test_private_key_returns_none_on_malformed_key(tmpdir):
    """private_key() returns None when the file contains non-PGP data."""
    bad_key = str(tmpdir.join("bad-prv.asc"))
    with open(bad_key, "w") as f:
        f.write("this is not a pgp key")

    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=bad_key)
    result = ctrl.private_key()
    assert result is None


def test_private_key_returns_none_when_file_disappears(tmpdir):
    """private_key() handles a key file that vanishes between stat and open."""
    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=_VALID_PRV_ASC)
    with mock.patch("builtins.open", side_effect=FileNotFoundError("gone")):
        result = ctrl.private_key()
    assert result is None


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_private_key_rejects_passphrase_protected(tmpdir):
    """private_key() returns None for a passphrase-protected key."""
    import pgpy

    # Generate a fresh key and protect it with a passphrase
    key = pgpy.PGPKey.new(
        pgpy.constants.PubKeyAlgorithm.RSAEncryptOrSign, 2048
    )
    uid = pgpy.PGPUID.new("Locked", email="locked@example.com")
    key.add_uid(
        uid,
        usage={pgpy.constants.KeyFlags.Sign},
        hashes=[pgpy.constants.HashAlgorithm.SHA256],
        ciphers=[pgpy.constants.SymmetricKeyAlgorithm.AES256],
        compression=[pgpy.constants.CompressionAlgorithm.ZLIB],
    )
    key.protect(
        "s3cr3t",
        pgpy.constants.SymmetricKeyAlgorithm.AES256,
        pgpy.constants.HashAlgorithm.SHA256,
    )

    locked_path = str(tmpdir.join("locked-prv.asc"))
    with open(locked_path, "w") as f:
        f.write(str(key))

    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=locked_path)
    result = ctrl.private_key()
    assert result is None


# ---------------------------------------------------------------------------
# sign() -- creating detached PGP signatures
# ---------------------------------------------------------------------------


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_sign_returns_signature_and_micalg(tmpdir):
    """sign() returns a (sig_str, micalg) tuple for valid message + key."""
    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=_VALID_PRV_ASC)
    result = ctrl.sign("Hello, World!")
    assert result is not None
    sig_str, micalg = result
    # The signature must be a non-empty armored block
    assert "BEGIN PGP SIGNATURE" in sig_str
    # The micalg must start with 'pgp-'
    assert micalg.startswith("pgp-")


def test_sign_returns_none_when_no_private_key(tmpdir):
    """sign() returns None when no private key is available."""
    ctrl = ApprisePGPController(path=str(tmpdir))
    assert ctrl.sign("test message") is None


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_sign_returns_none_on_pgp_error(tmpdir):
    """sign() returns None when pgpy raises PGPError during signing."""
    import pgpy

    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=_VALID_PRV_ASC)
    with mock.patch.object(
        ctrl.private_key().__class__,
        "sign",
        side_effect=pgpy.errors.PGPError("fail"),
    ):
        result = ctrl.sign("test")
    assert result is None


def test_sign_returns_none_when_pgpy_missing(tmpdir):
    """sign() returns None gracefully when PGPy is not installed."""
    ctrl = ApprisePGPController(path=str(tmpdir), prv_keyfile=_VALID_PRV_ASC)
    # Patch private_key() to return a mock that raises NameError on sign()
    mock_key = mock.Mock()
    mock_key.sign.side_effect = NameError("pgpy not installed")
    with mock.patch.object(ctrl, "private_key", return_value=mock_key):
        result = ctrl.sign("test")
    assert result is None
