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
import base64
import logging
import os
import shutil
import sys
from unittest import mock

import pytest

from apprise import AppriseAsset
from apprise.utils import pgp as pgp_module
from apprise.utils.pgp import ApprisePGPController, _ensure_imghdr_shim

logging.disable(logging.CRITICAL)

# Path to the pre-generated key fixtures used by signing/autocrypt tests
_VAR_DIR = os.path.join(os.path.dirname(__file__), "var", "pgp")
_VALID_PRV_ASC = os.path.join(_VAR_DIR, "valid-prv.asc")
_VALID_PUB_ASC = os.path.join(_VAR_DIR, "valid-pub.asc")


# imghdr shim


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
        # Python 3.13 and newer removed imghdr.
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


# ApprisePGPController WKD integration


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

    # The second call must use the parsed-key cache.
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
    # raises NameError naturally, so no mock is needed.
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


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
@pytest.mark.parametrize("use_keyfile", (False, True))
def test_keygen_checks_eligibility_before_rsa(tmpdir, use_keyfile):
    """Disabled key generation does not perform expensive RSA work."""

    ctrl = ApprisePGPController(
        path=str(tmpdir) if use_keyfile else None,
        pub_keyfile=_VALID_PUB_ASC if use_keyfile else None,
        email="test@example.com",
    )

    with mock.patch.object(pgp_module.pgpy.PGPKey, "new") as mock_new:
        assert ctrl.keygen() is False
        mock_new.assert_not_called()


# autocrypt_header()


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_no_sender_key(tmpdir):
    """Autocrypt is omitted when no sender key is available."""

    asset = AppriseAsset(pgp_autogen=False)
    ctrl = ApprisePGPController(
        path=str(tmpdir), email="test@example.com", asset=asset
    )
    assert ctrl.autocrypt_header() is None


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
@pytest.mark.parametrize("missing_email", (None, ""))
def test_autocrypt_header_none_without_email(tmpdir, missing_email):
    """Autocrypt requires an address even when a sender key exists."""

    ctrl = ApprisePGPController(
        path=str(tmpdir),
        prv_keyfile=_VALID_PRV_ASC,
        email=missing_email,
    )
    # Only the address is missing.
    assert ctrl.private_key() is not None
    assert ctrl.autocrypt_header() is None


def _fingerprint_of(path):
    """Loads a key fixture from disk and returns its fingerprint string."""
    import pgpy

    with open(path) as key_file:
        key, _ = pgpy.PGPKey.from_blob(key_file.read())
    return str(key.fingerprint)


def _keydata_fingerprint(header):
    """Decodes an Autocrypt header's keydata= and returns its fingerprint."""
    import pgpy

    keydata = header.split("keydata=", 1)[1]
    key, _ = pgpy.PGPKey.from_blob(base64.b64decode(keydata))
    return str(key.fingerprint)


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_valid_key(tmpdir):
    """Autocrypt advertises the public half of a generated sender key."""

    ctrl = ApprisePGPController(path=str(tmpdir), email="test@example.com")
    assert ctrl.keygen() is True

    header = ctrl.autocrypt_header()
    assert header is not None
    assert header.startswith(
        "addr=test@example.com; prefer-encrypt=mutual; keydata="
    )

    # Compare fingerprints so an unrelated but valid key cannot pass.
    assert _keydata_fingerprint(header) == str(ctrl.private_key().fingerprint)


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_ignores_recipient_pgppub(tmpdir):
    """Autocrypt uses our signing key instead of recipient pgppub=."""

    # Generate the sender key before configuring a recipient override.
    keygen_ctrl = ApprisePGPController(
        path=str(tmpdir), email="test@example.com"
    )
    assert keygen_ctrl.keygen() is True
    own_fingerprint = str(keygen_ctrl.private_key().fingerprint)

    # The fixture represents an unrelated recipient's key
    assert own_fingerprint != _fingerprint_of(_VALID_PUB_ASC)

    # The sender key remains discoverable beside the recipient override.
    ctrl = ApprisePGPController(
        path=str(tmpdir),
        pub_keyfile=_VALID_PUB_ASC,
        email="test@example.com",
    )
    header = ctrl.autocrypt_header()
    assert header is not None
    assert _keydata_fingerprint(header) == own_fingerprint


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_ignores_recipient_only_key(tmpdir):
    """Autocrypt omits a recipient pgppub= when no sender key exists."""

    asset = AppriseAsset(pgp_autogen=False)
    ctrl = ApprisePGPController(
        path=str(tmpdir),
        pub_keyfile=_VALID_PUB_ASC,
        email="test@example.com",
        asset=asset,
    )
    assert ctrl.autocrypt_header() is None


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
@pytest.mark.parametrize(
    "filename",
    (
        # Sender-specific names still require a matching private key.
        "sender@example.com-pub.asc",
        "sender-pub.asc",
        "pgp-public.asc",
        "pgp-pub.asc",
        "public.asc",
        "pub.asc",
    ),
)
def test_autocrypt_header_ignores_public_only_local_files(tmpdir, filename):
    """Autocrypt ignores local public keys without a matching private key."""

    shutil.copy(_VALID_PUB_ASC, str(tmpdir.join(filename)))

    asset = AppriseAsset(pgp_autogen=False)
    ctrl = ApprisePGPController(
        path=str(tmpdir), email="sender@example.com", asset=asset
    )
    assert ctrl.autocrypt_header() is None


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_autogen_generates_own_key(tmpdir):
    """Autocrypt may generate and advertise a sender-owned key pair."""

    asset = AppriseAsset(pgp_autogen=True)
    ctrl = ApprisePGPController(
        path=str(tmpdir), email="sender@example.com", asset=asset
    )
    assert ctrl.private_key() is None

    header = ctrl.autocrypt_header()
    assert header is not None
    assert header.startswith("addr=sender@example.com;")

    # A private key must now exist, and it must be the one advertised
    private_key = ctrl.private_key()
    assert private_key is not None
    assert _keydata_fingerprint(header) == str(private_key.fingerprint)


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_respects_autogen_disabled(tmpdir):
    """Autocrypt respects disabled key generation."""

    asset = AppriseAsset(pgp_autogen=False)
    ctrl = ApprisePGPController(
        path=str(tmpdir), email="sender@example.com", asset=asset
    )
    assert ctrl.autocrypt_header() is None
    assert ctrl.private_key() is None


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_enforces_size_limit(tmpdir):
    """Autocrypt rejects headers over its 10 KiB limit."""

    ctrl = ApprisePGPController(path=str(tmpdir), email="test@example.com")
    assert ctrl.keygen() is True

    # Sanity: the real key comfortably fits within the real limit
    assert ctrl.autocrypt_header() is not None

    # Force the limit far below anything a real key could satisfy
    ctrl.max_autocrypt_header_size = 10
    assert ctrl.autocrypt_header() is None


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_rejects_key_without_encryption_subkey(tmpdir):
    """Autocrypt rejects a private key without an encryption subkey."""

    ctrl = ApprisePGPController(
        path=str(tmpdir),
        prv_keyfile=_VALID_PRV_ASC,
        email="test@example.com",
    )
    private_key = ctrl.private_key()
    assert private_key is not None
    assert not ApprisePGPController._has_encryption_subkey(private_key)

    assert ctrl.autocrypt_header() is None


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_accepts_key_with_encryption_subkey(tmpdir):
    """_has_encryption_subkey() recognizes a properly structured key."""

    ctrl = ApprisePGPController(path=str(tmpdir), email="test@example.com")
    assert ctrl.keygen() is True

    private_key = ctrl.private_key()
    assert ApprisePGPController._has_encryption_subkey(private_key)


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_rejects_key_with_extra_userid(tmpdir):
    """Autocrypt rejects an otherwise valid key with multiple UIDs."""

    import pgpy
    from pgpy.constants import (
        CompressionAlgorithm,
        HashAlgorithm,
        KeyFlags,
        PubKeyAlgorithm,
        SymmetricKeyAlgorithm,
    )

    primary = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    for name, email in (
        ("Test", "test@example.com"),
        ("Test (work)", "test@work.example.com"),
    ):
        primary.add_uid(
            pgpy.PGPUID.new(name, email=email),
            usage={KeyFlags.Sign, KeyFlags.Certify},
            hashes=[HashAlgorithm.SHA256],
            ciphers=[SymmetricKeyAlgorithm.AES256],
            compression=[CompressionAlgorithm.ZLIB],
        )
    subkey = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    primary.add_subkey(
        subkey,
        usage={KeyFlags.EncryptCommunications, KeyFlags.EncryptStorage},
    )

    prv_path = str(tmpdir.join("multi-uid-prv.asc"))
    with open(prv_path, "w") as f:
        f.write(str(primary))

    ctrl = ApprisePGPController(
        path=str(tmpdir), prv_keyfile=prv_path, email="test@example.com"
    )
    private_key = ctrl.private_key()
    assert private_key is not None
    assert not ApprisePGPController._has_encryption_subkey(private_key)
    assert ctrl.autocrypt_header() is None


def _mock_uid_with_one_selfsig():
    """A mock UID with exactly the one self-signature a compliant key
    is expected to have, so tests can focus on the subkey side."""
    uid = mock.Mock()
    selfsig = mock.Mock()
    uid.selfsig = selfsig
    uid._signatures = [selfsig]
    return uid


def test_has_encryption_subkey_skips_subkey_without_selfsig():
    """A lone subkey with no self-signature at all is not usable."""

    no_selfsig_subkey = mock.Mock()
    no_selfsig_subkey.revocation_signatures = []
    no_selfsig_subkey.self_signatures = iter(())

    key = mock.Mock()
    key.userattributes = []
    key.revocation_signatures = []
    key.userids = [_mock_uid_with_one_selfsig()]
    key.subkeys = {"a": no_selfsig_subkey}

    assert ApprisePGPController._has_encryption_subkey(key) is False


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_has_encryption_subkey_skips_subkey_with_wrong_flags():
    """A signed subkey without encryption usage is not usable."""

    wrong_flags_subkey = mock.Mock()
    wrong_flags_subkey.revocation_signatures = []
    wrong_flags_subkey.self_signatures = iter(
        [mock.Mock(key_flags={pgp_module.pgpy.constants.KeyFlags.Sign})]
    )

    key = mock.Mock()
    key.userattributes = []
    key.revocation_signatures = []
    key.userids = [_mock_uid_with_one_selfsig()]
    key.subkeys = {"a": wrong_flags_subkey}

    assert ApprisePGPController._has_encryption_subkey(key) is False


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_has_encryption_subkey_rejects_multiple_userids():
    """Autocrypt rejects keys with multiple identities."""

    good_subkey = mock.Mock()
    good_subkey.self_signatures = iter(
        [
            mock.Mock(
                key_flags={
                    pgp_module.pgpy.constants.KeyFlags.EncryptCommunications
                }
            )
        ]
    )

    key = mock.Mock()
    key.userattributes = []
    key.revocation_signatures = []
    key.userids = ["user@example.com", "user@work.example.com"]
    key.subkeys = {"a": good_subkey}

    assert ApprisePGPController._has_encryption_subkey(key) is False


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_has_encryption_subkey_rejects_multiple_subkeys():
    """Autocrypt Level 1 requires exactly one subkey."""

    def make_subkey():
        subkey = mock.Mock()
        subkey.self_signatures = iter(
            [
                mock.Mock(
                    key_flags={
                        pgp_module.pgpy.constants.KeyFlags.EncryptCommunications
                    }
                )
            ]
        )
        return subkey

    key = mock.Mock()
    key.userattributes = []
    key.revocation_signatures = []
    key.userids = ["user@example.com"]
    key.subkeys = {"a": make_subkey(), "b": make_subkey()}

    assert ApprisePGPController._has_encryption_subkey(key) is False


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_has_encryption_subkey_rejects_extra_uid_selfsig():
    """Autocrypt rejects a UID with an extra self-signature."""

    uid = mock.Mock()
    uid._signatures = [mock.Mock(), mock.Mock()]

    subkey = mock.Mock()
    subkey.self_signatures = iter(
        [
            mock.Mock(
                key_flags={
                    pgp_module.pgpy.constants.KeyFlags.EncryptCommunications
                }
            )
        ]
    )

    key = mock.Mock()
    key.userattributes = []
    key.revocation_signatures = []
    key.userids = [uid]
    key.subkeys = {"a": subkey}

    assert ApprisePGPController._has_encryption_subkey(key) is False


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_has_encryption_subkey_rejects_extra_subkey_binding_sig():
    """Autocrypt rejects a subkey with an extra binding signature."""

    uid = mock.Mock()
    uid._signatures = [mock.Mock()]

    subkey = mock.Mock()
    subkey.revocation_signatures = []
    subkey.self_signatures = iter(
        [
            mock.Mock(
                key_flags={
                    pgp_module.pgpy.constants.KeyFlags.EncryptCommunications
                }
            ),
            mock.Mock(
                key_flags={
                    pgp_module.pgpy.constants.KeyFlags.EncryptCommunications
                }
            ),
        ]
    )

    key = mock.Mock()
    key.userattributes = []
    key.revocation_signatures = []
    key.userids = [uid]
    key.subkeys = {"a": subkey}

    assert ApprisePGPController._has_encryption_subkey(key) is False


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_has_encryption_subkey_rejects_uid_without_selfsig():
    """Reject a UID whose only signature is from a third party."""

    uid = mock.Mock()
    uid.selfsig = None
    uid._signatures = [mock.Mock()]

    subkey = mock.Mock()
    subkey.self_signatures = iter(
        [
            mock.Mock(
                key_flags={
                    pgp_module.pgpy.constants.KeyFlags.EncryptCommunications
                }
            )
        ]
    )

    key = mock.Mock()
    key.userattributes = []
    key.revocation_signatures = []
    key.userids = [uid]
    key.subkeys = {"a": subkey}

    assert ApprisePGPController._has_encryption_subkey(key) is False


def test_has_encryption_subkey_rejects_missing_signature_list():
    """Reject the key if PGPy's private signature collection is absent."""

    uid = mock.Mock(spec=["selfsig"])
    uid.selfsig = mock.Mock()

    key = mock.Mock()
    key.userattributes = []
    key.revocation_signatures = []
    key.userids = [uid]
    key.subkeys = {"a": mock.Mock()}

    assert ApprisePGPController._has_encryption_subkey(key) is False


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_rejects_third_party_only_uid(tmpdir):
    """Reject a serialized key with only a third-party UID signature."""

    import pgpy
    from pgpy.constants import (
        CompressionAlgorithm,
        HashAlgorithm,
        KeyFlags,
        PubKeyAlgorithm,
        SymmetricKeyAlgorithm,
    )

    victim = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    uid = pgpy.PGPUID.new("Victim", email="victim@example.com")
    victim.add_uid(
        uid,
        usage={KeyFlags.Sign, KeyFlags.Certify},
        hashes=[HashAlgorithm.SHA256],
        ciphers=[SymmetricKeyAlgorithm.AES256],
        compression=[CompressionAlgorithm.ZLIB],
    )
    subkey = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    victim.add_subkey(
        subkey,
        usage={KeyFlags.EncryptCommunications, KeyFlags.EncryptStorage},
    )

    # A third party certifies the UID instead of the primary itself
    thirdparty = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    tp_uid = pgpy.PGPUID.new("ThirdParty", email="tp@example.com")
    thirdparty.add_uid(
        tp_uid,
        usage={KeyFlags.Sign, KeyFlags.Certify},
        hashes=[HashAlgorithm.SHA256],
        ciphers=[SymmetricKeyAlgorithm.AES256],
        compression=[CompressionAlgorithm.ZLIB],
    )
    cert_sig = thirdparty.certify(uid)

    # Replace the genuine self-signature with the third-party one, so
    # the UID's only signature is not from its own primary key
    uid._signatures.clear()
    uid._signatures.append(cert_sig)

    prv_path = str(tmpdir.join("thirdparty-only-prv.asc"))
    with open(prv_path, "w") as f:
        f.write(str(victim))

    ctrl = ApprisePGPController(
        path=str(tmpdir), prv_keyfile=prv_path, email="victim@example.com"
    )
    private_key = ctrl.private_key()
    assert private_key is not None
    assert private_key.userids[0].selfsig is None
    assert not ApprisePGPController._has_encryption_subkey(private_key)
    assert ctrl.autocrypt_header() is None


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_rejects_key_with_extra_uid_signature(tmpdir):
    """Autocrypt rejects an extra UID signature after serialization."""

    import pgpy
    from pgpy.constants import (
        CompressionAlgorithm,
        HashAlgorithm,
        KeyFlags,
        PubKeyAlgorithm,
        SymmetricKeyAlgorithm,
    )

    primary = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    uid = pgpy.PGPUID.new("Test", email="test@example.com")
    primary.add_uid(
        uid,
        usage={KeyFlags.Sign, KeyFlags.Certify},
        hashes=[HashAlgorithm.SHA256],
        ciphers=[SymmetricKeyAlgorithm.AES256],
        compression=[CompressionAlgorithm.ZLIB],
    )
    subkey = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    primary.add_subkey(
        subkey,
        usage={KeyFlags.EncryptCommunications, KeyFlags.EncryptStorage},
    )

    # Add another genuine self-certification to the same UID.
    extra_sig = primary.certify(uid, expires=None)
    uid._signatures.insert(0, extra_sig)

    prv_path = str(tmpdir.join("extra-sig-prv.asc"))
    with open(prv_path, "w") as f:
        f.write(str(primary))

    ctrl = ApprisePGPController(
        path=str(tmpdir), prv_keyfile=prv_path, email="test@example.com"
    )
    private_key = ctrl.private_key()
    assert private_key is not None
    assert len(private_key.userids[0]._signatures) == 2
    assert not ApprisePGPController._has_encryption_subkey(private_key)
    assert ctrl.autocrypt_header() is None


def test_has_encryption_subkey_rejects_user_attribute():
    """Reject user attributes because they add packets to the key."""

    key = mock.Mock()
    key.userattributes = [mock.Mock()]

    assert ApprisePGPController._has_encryption_subkey(key) is False


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_rejects_photo_attribute(tmpdir):
    """Reject a serialized key containing a photo attribute."""

    import pgpy
    from pgpy.constants import (
        CompressionAlgorithm,
        HashAlgorithm,
        KeyFlags,
        PubKeyAlgorithm,
        SymmetricKeyAlgorithm,
    )

    primary = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    uid = pgpy.PGPUID.new("Test", email="test@example.com")
    primary.add_uid(
        uid,
        usage={KeyFlags.Sign, KeyFlags.Certify},
        hashes=[HashAlgorithm.SHA256],
        ciphers=[SymmetricKeyAlgorithm.AES256],
        compression=[CompressionAlgorithm.ZLIB],
    )
    subkey = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    primary.add_subkey(
        subkey,
        usage={KeyFlags.EncryptCommunications, KeyFlags.EncryptStorage},
    )

    # A minimal (fake, but structurally-tagged) JPEG photo attribute
    photo_bytes = bytearray(b"\xff\xd8\xff\xe0" + b"\x00" * 100 + b"\xff\xd9")
    photo_uid = pgpy.PGPUID.new(photo_bytes)
    primary.add_uid(photo_uid)

    prv_path = str(tmpdir.join("photo-prv.asc"))
    with open(prv_path, "w") as f:
        f.write(str(primary))

    ctrl = ApprisePGPController(
        path=str(tmpdir), prv_keyfile=prv_path, email="test@example.com"
    )
    private_key = ctrl.private_key()
    assert private_key is not None
    assert len(private_key.userattributes) == 1
    assert not ApprisePGPController._has_encryption_subkey(private_key)
    assert ctrl.autocrypt_header() is None


def test_has_encryption_subkey_rejects_revoked_primary_key():
    """Reject a revoked primary key despite its valid UID and subkey."""

    key = mock.Mock()
    key.userattributes = []
    key.revocation_signatures = [mock.Mock()]

    assert ApprisePGPController._has_encryption_subkey(key) is False


def test_has_encryption_subkey_rejects_revoked_subkey():
    """Reject an encryption subkey carrying a revocation signature."""

    subkey = mock.Mock()
    subkey.revocation_signatures = [mock.Mock()]

    key = mock.Mock()
    key.userattributes = []
    key.revocation_signatures = []
    key.userids = [_mock_uid_with_one_selfsig()]
    key.subkeys = {"a": subkey}

    assert ApprisePGPController._has_encryption_subkey(key) is False


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_rejects_revoked_primary_key(tmpdir):
    """Reject a serialized key with a revoked primary key."""

    import pgpy
    from pgpy.constants import (
        CompressionAlgorithm,
        HashAlgorithm,
        KeyFlags,
        PubKeyAlgorithm,
        SymmetricKeyAlgorithm,
    )

    primary = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    uid = pgpy.PGPUID.new("Test", email="test@example.com")
    primary.add_uid(
        uid,
        usage={KeyFlags.Sign, KeyFlags.Certify},
        hashes=[HashAlgorithm.SHA256],
        ciphers=[SymmetricKeyAlgorithm.AES256],
        compression=[CompressionAlgorithm.ZLIB],
    )
    subkey = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    primary.add_subkey(
        subkey,
        usage={KeyFlags.EncryptCommunications, KeyFlags.EncryptStorage},
    )

    # Revoke the primary key itself
    revoke_sig = primary.revoke(primary)
    primary |= revoke_sig

    prv_path = str(tmpdir.join("revoked-primary-prv.asc"))
    with open(prv_path, "w") as f:
        f.write(str(primary))

    ctrl = ApprisePGPController(
        path=str(tmpdir), prv_keyfile=prv_path, email="test@example.com"
    )
    private_key = ctrl.private_key()
    assert private_key is not None
    assert len(list(private_key.revocation_signatures)) == 1
    assert not ApprisePGPController._has_encryption_subkey(private_key)
    assert ctrl.autocrypt_header() is None


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_rejects_revoked_subkey(tmpdir):
    """Reject a serialized key with a revoked encryption subkey."""

    import pgpy
    from pgpy.constants import (
        CompressionAlgorithm,
        HashAlgorithm,
        KeyFlags,
        PubKeyAlgorithm,
        SymmetricKeyAlgorithm,
    )

    primary = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    uid = pgpy.PGPUID.new("Test", email="test@example.com")
    primary.add_uid(
        uid,
        usage={KeyFlags.Sign, KeyFlags.Certify},
        hashes=[HashAlgorithm.SHA256],
        ciphers=[SymmetricKeyAlgorithm.AES256],
        compression=[CompressionAlgorithm.ZLIB],
    )
    subkey = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    primary.add_subkey(
        subkey,
        usage={KeyFlags.EncryptCommunications, KeyFlags.EncryptStorage},
    )

    # Revoke only the subkey, not the primary
    revoke_sig = primary.revoke(subkey)
    subkey |= revoke_sig

    prv_path = str(tmpdir.join("revoked-subkey-prv.asc"))
    with open(prv_path, "w") as f:
        f.write(str(primary))

    ctrl = ApprisePGPController(
        path=str(tmpdir), prv_keyfile=prv_path, email="test@example.com"
    )
    private_key = ctrl.private_key()
    assert private_key is not None
    assert not list(private_key.revocation_signatures)  # primary is fine
    reparsed_subkey = next(iter(private_key.subkeys.values()))
    assert len(list(reparsed_subkey.revocation_signatures)) == 1
    assert not ApprisePGPController._has_encryption_subkey(private_key)
    assert ctrl.autocrypt_header() is None


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_preserves_exported_fingerprint(tmpdir):
    """The advertised key retains the exported key's fingerprint."""

    import pgpy

    ctrl = ApprisePGPController(path=str(tmpdir), email="test@example.com")
    assert ctrl.keygen() is True

    private_key = ctrl.private_key()
    exported = bytes(private_key.pubkey)
    reparsed, _ = pgpy.PGPKey.from_blob(exported)

    header = ctrl.autocrypt_header()
    assert header is not None

    # The advertised key must retain the exported primary-key identity.
    assert _keydata_fingerprint(header) == str(reparsed.fingerprint)


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_accepts_nonexportable_signature(tmpdir):
    """Validate the exported form of a key.

    PGPy drops the extra non-exportable signature, leaving one valid UID
    signature in the advertised key.
    """

    import pgpy
    from pgpy.constants import (
        CompressionAlgorithm,
        HashAlgorithm,
        KeyFlags,
        PubKeyAlgorithm,
        SymmetricKeyAlgorithm,
    )

    primary = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    uid = pgpy.PGPUID.new("Test", email="test@example.com")
    primary.add_uid(
        uid,
        usage={KeyFlags.Sign, KeyFlags.Certify},
        hashes=[HashAlgorithm.SHA256],
        ciphers=[SymmetricKeyAlgorithm.AES256],
        compression=[CompressionAlgorithm.ZLIB],
    )
    subkey = pgpy.PGPKey.new(PubKeyAlgorithm.RSAEncryptOrSign, 2048)
    primary.add_subkey(
        subkey,
        usage={KeyFlags.EncryptCommunications, KeyFlags.EncryptStorage},
    )

    # A second, non-exportable certification over the same UID
    extra_sig = primary.certify(uid, exportable=False)
    uid._signatures.insert(0, extra_sig)

    # The live in-memory object has two signatures and fails validation
    assert len(uid._signatures) == 2
    assert not ApprisePGPController._has_encryption_subkey(primary)

    # PGPy omits the extra signature from the exported key.
    exported = bytes(primary.pubkey)
    reparsed, _ = pgpy.PGPKey.from_blob(exported)
    assert len(reparsed.userids[0]._signatures) == 1
    assert ApprisePGPController._has_encryption_subkey(reparsed)

    prv_path = str(tmpdir.join("nonexportable-extra-prv.asc"))
    with open(prv_path, "w") as f:
        f.write(str(primary))

    ctrl = ApprisePGPController(
        path=str(tmpdir), prv_keyfile=prv_path, email="test@example.com"
    )
    # The header validates the exported key rather than the live object.
    header = ctrl.autocrypt_header()
    assert header is not None
    assert _keydata_fingerprint(header) == str(reparsed.fingerprint)


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_handles_reparse_failure(tmpdir):
    """Omit the header when the exported key cannot be parsed."""

    ctrl = ApprisePGPController(path=str(tmpdir), email="test@example.com")
    assert ctrl.keygen() is True

    # Warm the cache so the mock affects only the exported-key reparse.
    assert ctrl.private_key() is not None

    with mock.patch.object(
        pgp_module.pgpy.PGPKey,
        "from_blob",
        side_effect=ValueError("corrupt export"),
    ):
        assert ctrl.autocrypt_header() is None


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_autocrypt_header_folds_long_keydata(tmpdir):
    """Folded keydata stays within line limits and remains decodable."""

    ctrl = ApprisePGPController(path=str(tmpdir), email="test@example.com")
    assert ctrl.keygen() is True

    header = ctrl.autocrypt_header()
    assert header is not None

    # Keep every physical header line within RFC 5322's hard limit.
    rendered = f"Autocrypt: {header}"
    for line in rendered.split("\r\n"):
        assert len(line) <= 998

    # Folding must have actually happened for a real 2048-bit RSA key
    assert "\r\n " in header

    # addr= and prefer-encrypt= must stay intact and unfolded
    assert header.startswith(
        "addr=test@example.com; prefer-encrypt=mutual; keydata="
    )

    # Folding must not alter the advertised key.
    assert _keydata_fingerprint(header) == str(ctrl.private_key().fingerprint)


# prune() WKD delegation


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


# PGP_SUPPORT consistency


def test_pgp_support_flag_present():
    """PGP_SUPPORT is a boolean exported from the pgp module."""
    assert isinstance(pgp_module.PGP_SUPPORT, bool)


# private_keyfile() path resolution


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
    # because the attachment is resolved lazily. It must not be False.
    assert ctrl.prv_keyfile is not False


def test_prv_keyfile_property_false_when_invalid(tmpdir):
    """prv_keyfile property returns False for an unreachable explicit file."""
    ctrl = ApprisePGPController(
        path=str(tmpdir),
        prv_keyfile="/no/such/file.asc",
    )
    assert ctrl.prv_keyfile is False


# Loading private PGP keys


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


@pytest.mark.skipif(not pgp_module.PGP_SUPPORT, reason="Requires PGPy")
def test_private_key_rejects_public_only_file(tmpdir):
    """private_key() rejects public-only files supplied by pgpprv=."""

    ctrl = ApprisePGPController(
        path=str(tmpdir), prv_keyfile=_VALID_PUB_ASC, email="test@example.com"
    )
    result = ctrl.private_key()
    assert result is None

    # autocrypt_header() must not advertise it either
    assert ctrl.autocrypt_header() is None


# Detached PGP signatures


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


# Public-key candidate order


def test_pub_key_candidates_no_email(tmpdir):
    """_pub_key_candidates() returns the four generic fallbacks when no email
    is known and no extra addresses are supplied."""
    ctrl = ApprisePGPController(path=str(tmpdir))
    # No self.email and no caller-supplied email
    candidates = ctrl._pub_key_candidates()
    # Only the four generic names should appear
    assert candidates == [
        "pgp-public.asc",
        "pgp-pub.asc",
        "public.asc",
        "pub.asc",
    ]


def test_pub_key_candidates_with_email(tmpdir):
    """_pub_key_candidates() prepends email-specific names ahead of generics,
    highest priority first (full-email before localpart)."""
    ctrl = ApprisePGPController(path=str(tmpdir), email="Chris@Example.com")
    candidates = ctrl._pub_key_candidates()
    # Full lowercase email is highest priority (index 0)
    assert candidates[0] == "chris@example.com-pub.asc"
    # Localpart shorthand is next
    assert candidates[1] == "chris-pub.asc"
    # Generic fallbacks follow
    assert "pgp-pub.asc" in candidates


def test_pub_key_candidates_extra_email(tmpdir):
    """Recipient lookups never fall back to the sender's key."""
    ctrl = ApprisePGPController(path=str(tmpdir), email="sender@example.com")
    # Simulate a lookup for a recipient address
    candidates = ctrl._pub_key_candidates("recipient@example.com")
    assert candidates[0] == "recipient@example.com-pub.asc"
    assert candidates[1] == "recipient-pub.asc"
    # Sender entries must not appear in a recipient lookup.
    assert "sender@example.com-pub.asc" not in candidates
    assert "sender-pub.asc" not in candidates


# Private-key candidate order


def test_prv_key_candidates_no_email(tmpdir):
    """_prv_key_candidates() returns the four generic fallbacks when no sender
    email is configured."""
    ctrl = ApprisePGPController(path=str(tmpdir))
    candidates = ctrl._prv_key_candidates()
    assert candidates == [
        "pgp-private.asc",
        "pgp-prv.asc",
        "private.asc",
        "prv.asc",
    ]


def test_prv_key_candidates_with_email(tmpdir):
    """_prv_key_candidates() prepends email-specific names ahead of generics,
    highest priority first (full-email before localpart)."""
    ctrl = ApprisePGPController(path=str(tmpdir), email="Sender@Nuxref.com")
    candidates = ctrl._prv_key_candidates()
    # Full lowercase email is highest priority
    assert candidates[0] == "sender@nuxref.com-prv.asc"
    # Localpart shorthand is next
    assert candidates[1] == "sender-prv.asc"
    # Generic fallbacks follow
    assert "pgp-prv.asc" in candidates


# Missing public-key diagnostics


def test_public_key_no_key_emits_path_debug(tmpdir):
    """public_key() emits a DEBUG message listing relative cache paths when
    no public key is found and autogen is disabled.  The message is debug-
    level so the caller's warning remains the only user-visible line."""
    ctrl = ApprisePGPController(path=str(tmpdir), email="user@example.com")
    logging.disable(logging.NOTSET)
    try:
        with mock.patch.object(pgp_module, "PGP_SUPPORT", True):
            result = ctrl.public_key("user@example.com", autogen=False)
    finally:
        logging.disable(logging.CRITICAL)

    # Key not found; result must be None
    assert result is None


def test_public_key_no_key_no_path_emits_generic_debug():
    """public_key() emits a generic 'No PGP public key found' debug message
    in memory-only mode (no path to search, so no filenames to list)."""
    ctrl = ApprisePGPController(path=None)
    logging.disable(logging.NOTSET)
    try:
        with mock.patch.object(pgp_module, "PGP_SUPPORT", True):
            result = ctrl.public_key("user@example.com", autogen=False)
    finally:
        logging.disable(logging.CRITICAL)
    assert result is None


# Missing private-key diagnostics


def test_private_key_not_found_emits_path_debug(tmpdir):
    """private_key() emits a DEBUG message listing searched relative paths
    when no private key file exists on disk.  The message is debug-level so
    the caller's warning remains the only user-visible line."""
    ctrl = ApprisePGPController(path=str(tmpdir), email="sender@example.com")
    logging.disable(logging.NOTSET)
    try:
        result = ctrl.private_key()
    finally:
        logging.disable(logging.CRITICAL)
    assert result is None


def test_private_key_not_found_no_path_emits_generic_debug():
    """private_key() emits a generic 'No PGP private key found' debug
    message in memory-only mode (no storage path, nothing to search)."""
    ctrl = ApprisePGPController(path=None)
    logging.disable(logging.NOTSET)
    try:
        result = ctrl.private_key()
    finally:
        logging.disable(logging.CRITICAL)
    assert result is None
