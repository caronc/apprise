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

import logging
from unittest import mock

import pytest

from apprise.utils.saltpack import (
    NACL_SUPPORT,
    AppriseSaltpackController,
    AppriseSaltpackException,
    _b62_decode,
    _b62_encode,
    _mp_array,
    _mp_bool,
    _mp_bytes,
    _mp_fixstr,
    _mp_uint,
)

logging.disable(logging.CRITICAL)


# ---------------------------------------------------------------------------
# Inline msgpack encoder
# ---------------------------------------------------------------------------


def test_saltpack_mp_fixstr_basic():
    """Short ASCII strings are encoded as msgpack fixstr."""
    # "saltpack" is 8 chars -> 0xa8 + b"saltpack"
    encoded = _mp_fixstr("saltpack")
    assert encoded == b"\xa8saltpack"


def test_saltpack_mp_fixstr_too_long():
    """Strings > 31 bytes raise ValueError."""
    with pytest.raises(ValueError):
        _mp_fixstr("x" * 32)


def test_saltpack_mp_uint_small():
    """Small integers use msgpack positive fixint."""
    assert _mp_uint(0) == b"\x00"
    assert _mp_uint(1) == b"\x01"
    assert _mp_uint(127) == b"\x7f"


def test_saltpack_mp_uint_out_of_range():
    """Values outside 0-127 raise ValueError."""
    with pytest.raises(ValueError):
        _mp_uint(128)
    with pytest.raises(ValueError):
        _mp_uint(-1)


def test_saltpack_mp_bool():
    """Booleans are encoded as msgpack bool."""
    assert _mp_bool(True) == b"\xc3"
    assert _mp_bool(False) == b"\xc2"


def test_saltpack_mp_bytes_bin8():
    """Bytes up to 255 use msgpack bin8."""
    data = b"\x01\x02\x03"
    encoded = _mp_bytes(data)
    # 0xc4 = bin8 marker, then length byte, then data
    assert encoded == b"\xc4\x03\x01\x02\x03"


def test_saltpack_mp_bytes_bin16():
    """Bytes 256-65535 use msgpack bin16."""
    data = b"\xff" * 256
    encoded = _mp_bytes(data)
    assert encoded[0:1] == b"\xc5"
    assert int.from_bytes(encoded[1:3], "big") == 256


def test_saltpack_mp_bytes_bin32():
    """Bytes > 65535 use msgpack bin32."""
    data = b"\xaa" * 65536
    encoded = _mp_bytes(data)
    assert encoded[0:1] == b"\xc6"
    assert int.from_bytes(encoded[1:5], "big") == 65536


def test_saltpack_mp_array_fixarray():
    """Arrays up to 15 elements use msgpack fixarray."""
    items = [_mp_uint(i) for i in range(5)]
    encoded = _mp_array(items)
    # fixarray(5) = 0x90 | 5 = 0x95
    assert encoded[0:1] == b"\x95"


def test_saltpack_mp_array_array16():
    """Arrays of 16-65535 elements use msgpack array16."""
    items = [_mp_uint(0)] * 16
    encoded = _mp_array(items)
    # array16 marker
    assert encoded[0:1] == b"\xdc"


def test_saltpack_mp_array_array32():
    """Arrays of >65535 elements use msgpack array32."""
    items = [_mp_uint(0)] * 65536
    encoded = _mp_array(items)
    # array32 marker
    assert encoded[0:1] == b"\xdd"


# ---------------------------------------------------------------------------
# Base62 codec
# ---------------------------------------------------------------------------


def test_saltpack_b62_encode_roundtrip_full_chunk():
    """A 32-byte value round-trips through base62 encode/decode."""
    data = bytes(range(32))
    encoded = _b62_encode(data)
    # Full chunk should produce exactly 43 chars
    assert len(encoded) == 43
    decoded = _b62_decode(encoded)
    assert decoded == data


def test_saltpack_b62_encode_roundtrip_partial_chunk():
    """A partial chunk round-trips correctly."""
    for n in range(1, 32):
        data = bytes(range(n))
        encoded = _b62_encode(data)
        decoded = _b62_decode(encoded)
        assert decoded == data, f"Failed for {n} bytes"


def test_saltpack_b62_encode_roundtrip_multi_chunk():
    """Multiple full chunks plus a partial chunk round-trip."""
    data = bytes(range(70))  # 2 full chunks (64 bytes) + 6 bytes
    encoded = _b62_encode(data)
    decoded = _b62_decode(encoded)
    assert decoded == data


def test_saltpack_b62_encode_leading_zero_bytes():
    """Leading zero bytes in a chunk are preserved after round-trip."""
    data = b"\x00\x00\x01" + bytes(29)  # starts with 2 zero bytes
    encoded = _b62_encode(data)
    decoded = _b62_decode(encoded)
    assert decoded == data


def test_saltpack_b62_decode_ignores_whitespace():
    """Whitespace (spaces and newlines) in encoded text is ignored."""
    data = bytes(range(32))
    encoded = _b62_encode(data)
    # Insert spaces and newlines
    spaced = " ".join(encoded[i : i + 10] for i in range(0, len(encoded), 10))
    newlined = "\n".join(spaced.split())
    decoded = _b62_decode(newlined)
    assert decoded == data


# ---------------------------------------------------------------------------
# AppriseSaltpackController -- no-PyNaCl paths
# ---------------------------------------------------------------------------


def test_saltpack_sign_no_nacl_raises():
    """sign() raises AppriseSaltpackException when PyNaCl is absent."""
    ctrl = AppriseSaltpackController()
    with (
        mock.patch("apprise.utils.saltpack.NACL_SUPPORT", False),
        pytest.raises(AppriseSaltpackException),
    ):
        ctrl.sign("hello", "ab" * 32)


def test_saltpack_keygen_signing_no_nacl_raises():
    """keygen_signing() raises when PyNaCl is absent."""
    with (
        mock.patch("apprise.utils.saltpack.NACL_SUPPORT", False),
        pytest.raises(AppriseSaltpackException),
    ):
        AppriseSaltpackController.keygen_signing()


def test_saltpack_keygen_box_no_nacl_raises():
    """keygen_box() raises when PyNaCl is absent."""
    with (
        mock.patch("apprise.utils.saltpack.NACL_SUPPORT", False),
        pytest.raises(AppriseSaltpackException),
    ):
        AppriseSaltpackController.keygen_box()


def test_saltpack_box_encrypt_no_nacl_raises():
    """box_encrypt() raises when PyNaCl is absent."""
    with (
        mock.patch("apprise.utils.saltpack.NACL_SUPPORT", False),
        pytest.raises(AppriseSaltpackException),
    ):
        AppriseSaltpackController.box_encrypt("msg", "ab" * 32, b"\x00" * 32)


# ---------------------------------------------------------------------------
# AppriseSaltpackController -- sign() input validation
# ---------------------------------------------------------------------------


def test_saltpack_sign_invalid_key_non_hex():
    """sign() raises when the signing key contains non-hex chars."""
    ctrl = AppriseSaltpackController()
    with (
        mock.patch("apprise.utils.saltpack.NACL_SUPPORT", True),
        pytest.raises(AppriseSaltpackException),
    ):
        ctrl.sign("hello", "zz" * 32)


def test_saltpack_sign_invalid_key_wrong_length():
    """sign() raises when the signing key is not 32 bytes (64 hex chars)."""
    ctrl = AppriseSaltpackController()
    with (
        mock.patch("apprise.utils.saltpack.NACL_SUPPORT", True),
        pytest.raises(AppriseSaltpackException),
    ):
        ctrl.sign("hello", "ab" * 16)  # only 16 bytes


# ---------------------------------------------------------------------------
# AppriseSaltpackController -- with PyNaCl (skip if not installed)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_saltpack_keygen_signing_returns_hex_pair():
    """keygen_signing() returns two 64-char hex strings."""
    sk_hex, vk_hex = AppriseSaltpackController.keygen_signing()
    assert len(sk_hex) == 64
    assert len(vk_hex) == 64
    # Verify both strings are valid hex
    bytes.fromhex(sk_hex)
    bytes.fromhex(vk_hex)


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_saltpack_keygen_box_returns_hex_pair():
    """keygen_box() returns two 64-char hex strings."""
    priv_hex, pub_hex = AppriseSaltpackController.keygen_box()
    assert len(priv_hex) == 64
    assert len(pub_hex) == 64
    bytes.fromhex(priv_hex)
    bytes.fromhex(pub_hex)


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_saltpack_sign_produces_armored_output():
    """sign() produces a properly armored Saltpack message."""
    sk_hex, _ = AppriseSaltpackController.keygen_signing()
    ctrl = AppriseSaltpackController()
    result = ctrl.sign("Hello, Keybase!", sk_hex)

    assert "BEGIN KEYBASE SALTPACK SIGNED MESSAGE" in result
    assert "END KEYBASE SALTPACK SIGNED MESSAGE" in result
    # Verify the armor block is non-empty between the markers
    lines = result.splitlines()
    assert len(lines) >= 3


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_saltpack_sign_bytes_message():
    """sign() accepts a bytes message as well as str."""
    sk_hex, _ = AppriseSaltpackController.keygen_signing()
    ctrl = AppriseSaltpackController()
    result = ctrl.sign(b"bytes message", sk_hex)
    assert "BEGIN KEYBASE SALTPACK SIGNED MESSAGE" in result


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_saltpack_sign_empty_message():
    """sign() handles an empty message without error."""
    sk_hex, _ = AppriseSaltpackController.keygen_signing()
    ctrl = AppriseSaltpackController()
    result = ctrl.sign("", sk_hex)
    assert "BEGIN KEYBASE SALTPACK SIGNED MESSAGE" in result


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_saltpack_sign_long_message():
    """sign() splits messages > 1 MB into multiple payload packets."""
    sk_hex, _ = AppriseSaltpackController.keygen_signing()
    ctrl = AppriseSaltpackController()
    # 1.5 MB message produces two payload packets
    big = "A" * (1_000_000 + 500_000)
    result = ctrl.sign(big, sk_hex)
    assert "BEGIN KEYBASE SALTPACK SIGNED MESSAGE" in result


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_saltpack_box_encrypt_returns_nonce_and_ciphertext():
    """box_encrypt() returns a (nonce, ciphertext) tuple."""
    priv_hex, pub_hex = AppriseSaltpackController.keygen_box()
    pub_bytes = bytes.fromhex(pub_hex)
    nonce, ct = AppriseSaltpackController.box_encrypt(
        "secret", priv_hex, pub_bytes
    )
    # NaCl Box nonce is 24 bytes
    assert len(nonce) == 24
    assert len(ct) > 0


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_saltpack_box_encrypt_bytes_plaintext():
    """box_encrypt() accepts a bytes plaintext (not just str)."""
    priv_hex, pub_hex = AppriseSaltpackController.keygen_box()
    pub_bytes = bytes.fromhex(pub_hex)
    nonce, ct = AppriseSaltpackController.box_encrypt(
        b"bytes secret", priv_hex, pub_bytes
    )
    assert len(nonce) == 24
    assert len(ct) > 0


@pytest.mark.skipif(not NACL_SUPPORT, reason="PyNaCl not installed")
def test_saltpack_box_encrypt_bad_privkey_raises():
    """box_encrypt() raises when the private key is not valid hex."""
    with pytest.raises(AppriseSaltpackException):
        AppriseSaltpackController.box_encrypt("msg", "zz" * 32, b"\x00" * 32)


# ---------------------------------------------------------------------------
# AppriseSaltpackController -- fetch_keybase_keys()
# ---------------------------------------------------------------------------


def test_saltpack_fetch_keybase_keys_success():
    """fetch_keybase_keys() parses a successful API response."""
    dh_hex = "aa" * 32
    eddsa_hex = "bb" * 32
    response_json = {
        "them": [
            {
                "public_keys": {
                    "nacl": {
                        "dh": dh_hex,
                        "eddsa": eddsa_hex,
                    }
                }
            }
        ]
    }

    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = response_json

    with mock.patch("requests.get", return_value=mock_resp):
        result = AppriseSaltpackController.fetch_keybase_keys("alice")

    assert result is not None
    assert result["dh"] == bytes.fromhex(dh_hex)
    assert result["eddsa"] == bytes.fromhex(eddsa_hex)


def test_saltpack_fetch_keybase_keys_http_error():
    """fetch_keybase_keys() returns None on HTTP error status."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 404

    with mock.patch("requests.get", return_value=mock_resp):
        result = AppriseSaltpackController.fetch_keybase_keys("nosuchuser")

    assert result is None


def test_saltpack_fetch_keybase_keys_network_error():
    """fetch_keybase_keys() returns None on network failure."""
    import requests as _requests

    with mock.patch(
        "requests.get",
        side_effect=_requests.RequestException("timeout"),
    ):
        result = AppriseSaltpackController.fetch_keybase_keys("alice")

    assert result is None


def test_saltpack_fetch_keybase_keys_bad_json():
    """fetch_keybase_keys() returns None when response is not valid JSON."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("not json")

    with mock.patch("requests.get", return_value=mock_resp):
        result = AppriseSaltpackController.fetch_keybase_keys("alice")

    assert result is None


def test_saltpack_fetch_keybase_keys_missing_nacl_fields():
    """fetch_keybase_keys() returns None when nacl keys are absent."""
    response_json = {
        "them": [
            {
                "public_keys": {
                    "nacl": {
                        "dh": "",
                        "eddsa": "",
                    }
                }
            }
        ]
    }

    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = response_json

    with mock.patch("requests.get", return_value=mock_resp):
        result = AppriseSaltpackController.fetch_keybase_keys("alice")

    assert result is None


def test_saltpack_fetch_keybase_keys_unexpected_structure():
    """fetch_keybase_keys() returns None for unexpected JSON structure."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"unexpected": "structure"}

    with mock.patch("requests.get", return_value=mock_resp):
        result = AppriseSaltpackController.fetch_keybase_keys("alice")

    assert result is None
