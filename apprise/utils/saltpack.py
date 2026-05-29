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

# NaCl signing and encryption utilities for Apprise.
#
# This module implements:
#
#  - Saltpack v2.0 attached signing (Ed25519).  Output is compatible
#    with `keybase verify` and any Saltpack-aware client.
#
#  - NaCl box encryption (Curve25519 + XSalsa20-Poly1305), the same
#    primitive used by Threema E2EE and other Apprise plugins.
#
#  - Convenience helpers for Keybase public key lookup via the
#    public HTTPS API.
#
# Saltpack v2.0 signing format references:
#   https://saltpack.org/signing-crypto-format
#   https://saltpack.org/armoring
#
# Keybase key lookup API:
#   https://keybase.io/docs/api/1.0/call/user/lookup

import hashlib
import math
import struct

import requests

from ..exception import ApprisePluginException
from ..logger import logger

try:
    from nacl.public import (
        Box as _NaclBox,
        PrivateKey as _NaclPrivateKey,
        PublicKey as _NaclPublicKey,
    )
    from nacl.signing import SigningKey as _NaclSigningKey
    from nacl.utils import random as _nacl_random

    # PyNaCl is available
    NACL_SUPPORT = True

except ImportError:
    _NaclBox = None
    _NaclPrivateKey = None
    _NaclPublicKey = None
    _NaclSigningKey = None
    _nacl_random = None

    # PyNaCl is not installed
    NACL_SUPPORT = False


# Armor header and footer markers
_SP_BEGIN_SIGNED = "BEGIN KEYBASE SALTPACK SIGNED MESSAGE."
_SP_END_SIGNED = "END KEYBASE SALTPACK SIGNED MESSAGE."

# Base62 alphabet used by Saltpack (digits, then upper, then lower)
_BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

# Saltpack armor chunking: 32 raw bytes -> 43 base62 characters
# (62^43 > 2^256, so 43 chars can represent any 32-byte value)
_ARMOR_CHUNK_BYTES = 32
_ARMOR_CHUNK_CHARS = 43

# Armor line width (characters per line)
_ARMOR_LINE_WIDTH = 70

# Saltpack signing payload chunk size (per spec: 1 MB)
_PAYLOAD_CHUNK = 1_000_000


# ---------------------------------------------------------------------------
# Inline msgpack encoder
#
# Only the subset of types needed for Saltpack v2.0 headers and packets
# is implemented here, so no external msgpack library is required.
# ---------------------------------------------------------------------------


def _mp_fixstr(s):
    """Encode a short ASCII string as msgpack fixstr (length <= 31)."""
    b = s.encode("ascii")
    if len(b) > 31:
        raise ValueError("fixstr too long ({} bytes)".format(len(b)))
    # fixstr: 0xa0 | length, then the UTF-8 bytes
    return bytes([0xA0 | len(b)]) + b


def _mp_uint(n):
    """Encode a small non-negative integer as msgpack positive fixint."""
    if 0 <= n <= 127:
        return bytes([n])
    raise ValueError("uint out of positive fixint range: {}".format(n))


def _mp_bool(v):
    """Encode a boolean as msgpack bool."""
    # 0xc3 = true, 0xc2 = false
    return b"\xc3" if v else b"\xc2"


def _mp_bytes(data):
    """Encode a bytes object as msgpack bin8, bin16, or bin32."""
    n = len(data)
    if n <= 255:
        # bin8: 0xc4, length (1 byte), data
        return b"\xc4" + bytes([n]) + data
    if n <= 65535:
        # bin16: 0xc5, length (2 bytes big-endian), data
        return b"\xc5" + struct.pack(">H", n) + data
    # bin32: 0xc6, length (4 bytes big-endian), data
    return b"\xc6" + struct.pack(">I", n) + data


def _mp_array(items):
    """Encode a list of pre-encoded msgpack items as a msgpack array."""
    n = len(items)
    body = b"".join(items)
    if n <= 15:
        # fixarray: 0x90 | count
        return bytes([0x90 | n]) + body
    if n <= 65535:
        # array16: 0xdc, count (2 bytes big-endian)
        return b"\xdc" + struct.pack(">H", n) + body
    # array32: 0xdd, count (4 bytes big-endian)
    return b"\xdd" + struct.pack(">I", n) + body


# ---------------------------------------------------------------------------
# Base62 codec (Saltpack armoring)
# ---------------------------------------------------------------------------


def _b62_encode(data):
    """Encode a byte string using Saltpack base62 armor.

    Processes 32-byte chunks at a time, mapping each chunk to exactly
    43 base62 characters.  The final partial chunk uses the minimum
    number of chars that can represent its value.  Returns the encoded
    characters as a single string (without armor headers or line-breaks).
    """
    parts = []
    for i in range(0, len(data), _ARMOR_CHUNK_BYTES):
        chunk = data[i : i + _ARMOR_CHUNK_BYTES]
        # Number of output chars for this chunk
        if len(chunk) == _ARMOR_CHUNK_BYTES:
            n_chars = _ARMOR_CHUNK_CHARS
        else:
            # ceil(k * 8 / log2(62)) for a k-byte partial chunk
            n_chars = math.ceil(len(chunk) * 8 / math.log2(62))

        # Convert chunk to a big-endian integer and base62-encode it
        n = int.from_bytes(chunk, "big")
        chars = []
        for _ in range(n_chars):
            n, r = divmod(n, 62)
            chars.append(_BASE62[r])
        # Reverse because we built the digits least-significant first
        parts.extend(reversed(chars))

    return "".join(parts)


def _b62_decode(text):
    """Decode a Saltpack base62 armor string to bytes.

    Processes 43-char chunks at a time, each mapping back to exactly
    32 bytes.  The final partial chunk infers its byte count from the
    number of remaining characters.
    """
    # Strip all whitespace first
    text = "".join(text.split())

    parts = []
    pos = 0
    while pos < len(text):
        remaining = len(text) - pos
        if remaining >= _ARMOR_CHUNK_CHARS:
            # Full 43-char chunk -> 32 bytes
            chunk_text = text[pos : pos + _ARMOR_CHUNK_CHARS]
            pos += _ARMOR_CHUNK_CHARS
            n_bytes = _ARMOR_CHUNK_BYTES
        else:
            # Partial last chunk: infer byte count
            chunk_text = text[pos:]
            pos = len(text)
            # floor(n_chars * log2(62) / 8)
            n_bytes = int(remaining * math.log2(62) / 8)

        # Decode base62 chars to integer then to bytes
        n = 0
        for ch in chunk_text:
            n = n * 62 + _BASE62.index(ch)
        parts.append(n.to_bytes(n_bytes, "big"))

    return b"".join(parts)


class AppriseSaltpackException(ApprisePluginException):
    """Thrown when a Saltpack or NaCl operation fails."""

    def __init__(self, message, error_code=610):
        super().__init__(message, error_code=error_code)


class AppriseSaltpackController:
    """Saltpack signing and NaCl encryption controller for Apprise.

    Provides:
      - Saltpack v2.0 attached signing (Ed25519) via sign().
      - NaCl box encryption (Curve25519 + XSalsa20-Poly1305)
        via box_encrypt(), matching the primitive used by
        Threema E2EE and other plugins.
      - Ed25519 and Curve25519 key generation helpers.
      - Keybase public-key lookup via the HTTPS API.

    Requires: pip install PyNaCl
    """

    def sign(self, message, signing_key_hex):
        """Create a Saltpack v2.0 armored signed message.

        Output is compatible with any Saltpack client (including
        ``keybase verify``).

        Args:
            message:
                Text or bytes to sign.
            signing_key_hex:
                64-character hex string of the 32-byte Ed25519
                signing-key seed.

        Returns the full armored signed-message string.
        Raises AppriseSaltpackException on any error.
        """
        if not NACL_SUPPORT:
            raise AppriseSaltpackException(
                "PyNaCl is required for Saltpack signing;"
                " install with: pip install PyNaCl"
            )

        # Parse and validate the signing key seed
        try:
            seed = bytes.fromhex(signing_key_hex)
        except (ValueError, TypeError) as exc:
            raise AppriseSaltpackException(
                "Invalid signing key: expected 64 hex characters"
            ) from exc

        if len(seed) != 32:
            raise AppriseSaltpackException(
                "Invalid signing key length: expected 32 bytes, got {}".format(
                    len(seed)
                )
            )

        # Build the Ed25519 signing key and extract the verify key
        signing_key = _NaclSigningKey(seed)
        verify_key_bytes = bytes(signing_key.verify_key)

        # Normalize message to bytes
        if isinstance(message, str):
            message = message.encode("utf-8")

        # Generate a random 32-byte nonce for the header
        nonce = _nacl_random(32)

        # Build and hash the Saltpack v2.0 signing header
        header = self._build_header(verify_key_bytes, nonce)
        header_hash = hashlib.sha512(header).digest()

        # Build payload packets (split into 1 MB chunks per spec)
        packets = [header]
        chunks = [
            message[i : i + _PAYLOAD_CHUNK]
            for i in range(0, len(message), _PAYLOAD_CHUNK)
        ]
        # An empty message still produces one payload packet
        if not chunks:
            chunks = [b""]

        for idx, chunk in enumerate(chunks):
            # Mark the final packet
            is_final = idx == len(chunks) - 1
            # Build the packet and append it to the stream
            pkt = self._build_payload_packet(
                header_hash, chunk, is_final, signing_key
            )
            packets.append(pkt)

        # Concatenate all msgpack-encoded packets into one binary stream
        stream = b"".join(packets)

        # Base62-encode the stream
        encoded = _b62_encode(stream)

        # Wrap encoded output at the armor line width
        lines = [
            encoded[i : i + _ARMOR_LINE_WIDTH]
            for i in range(0, len(encoded), _ARMOR_LINE_WIDTH)
        ]

        # Assemble the final armored message
        body = "\n".join(lines)
        return ". {begin}\n{body}\n. {end}".format(
            begin=_SP_BEGIN_SIGNED,
            body=body,
            end=_SP_END_SIGNED,
        )

    @staticmethod
    def _build_header(verify_key_bytes, nonce):
        """Return the msgpack-encoded Saltpack v2.0 signing header.

        Header structure (from the Saltpack spec):
          ["saltpack", [2, 0], 1, sender_public_key, nonce]
        """
        return _mp_array(
            [
                _mp_fixstr("saltpack"),
                _mp_array([_mp_uint(2), _mp_uint(0)]),
                _mp_uint(1),  # mode 1 = attached signing
                _mp_bytes(verify_key_bytes),
                _mp_bytes(nonce),
            ]
        )

    @staticmethod
    def _build_payload_packet(header_hash, chunk, is_final, signing_key):
        """Build and msgpack-encode one Saltpack v2.0 payload packet.

        The signature covers (per spec):
          "saltpack\\0" + "attached signing\\0" +
          final_byte + header_hash + sha512(chunk)
        """
        # Construct the byte string to sign
        final_byte = b"\x01" if is_final else b"\x00"
        to_sign = (
            b"saltpack\x00"
            + b"attached signing\x00"
            + final_byte
            + header_hash
            + hashlib.sha512(chunk).digest()
        )

        # Sign and extract the 64-byte Ed25519 signature
        sig = signing_key.sign(to_sign).signature

        # Encode as [is_final, signature, payload_chunk]
        return _mp_array(
            [
                _mp_bool(is_final),
                _mp_bytes(sig),
                _mp_bytes(chunk),
            ]
        )

    @staticmethod
    def keygen_signing():
        """Generate a new Ed25519 key pair for Saltpack signing.

        Returns a (signing_key_hex, verify_key_hex) tuple where each
        element is a 64-character lowercase hex string representing a
        32-byte key.  Raises AppriseSaltpackException when PyNaCl is
        not available.
        """
        if not NACL_SUPPORT:
            raise AppriseSaltpackException(
                "PyNaCl is required for key generation;"
                " install with: pip install PyNaCl"
            )

        # Generate a random 32-byte seed
        sk = _NaclSigningKey(_nacl_random(32))
        signing_key_hex = bytes(sk).hex()
        verify_key_hex = bytes(sk.verify_key).hex()
        return signing_key_hex, verify_key_hex

    @staticmethod
    def keygen_box():
        """Generate a new Curve25519 key pair for NaCl box encryption.

        Returns a (private_key_hex, public_key_hex) tuple where each
        element is a 64-character lowercase hex string.  Raises
        AppriseSaltpackException when PyNaCl is not available.
        """
        if not NACL_SUPPORT:
            raise AppriseSaltpackException(
                "PyNaCl is required for key generation;"
                " install with: pip install PyNaCl"
            )

        # Generate a new Curve25519 private key
        priv = _NaclPrivateKey(_nacl_random(32))
        private_key_hex = bytes(priv).hex()
        public_key_hex = bytes(priv.public_key).hex()
        return private_key_hex, public_key_hex

    @staticmethod
    def box_encrypt(plaintext, sender_privkey_hex, recipient_pubkey_bytes):
        """Encrypt plaintext using NaCl Box (Curve25519 + XSalsa20-Poly1305).

        Note: This is the same primitive used by Threema E2EE.

        Args:
            plaintext:
                Message to encrypt (str or bytes).
            sender_privkey_hex:
                64-character hex string of the sender's 32-byte
                Curve25519 private key.
            recipient_pubkey_bytes:
                32-byte Curve25519 public key of the recipient.

        Returns a (nonce_bytes, ciphertext_bytes) tuple.
        Raises AppriseSaltpackException on error.
        """
        if not NACL_SUPPORT:
            raise AppriseSaltpackException(
                "PyNaCl is required for NaCl box encryption;"
                " install with: pip install PyNaCl"
            )

        # Parse the sender private key
        try:
            privkey_bytes = bytes.fromhex(sender_privkey_hex)
        except (ValueError, TypeError) as exc:
            raise AppriseSaltpackException(
                "Invalid private key: expected 64 hex characters"
            ) from exc

        # Normalize plaintext to bytes
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        # Construct the NaCl Box and encrypt
        sender_key = _NaclPrivateKey(privkey_bytes)
        recipient_key = _NaclPublicKey(recipient_pubkey_bytes)
        box = _NaclBox(sender_key, recipient_key)

        nonce = _nacl_random(_NaclBox.NONCE_SIZE)
        encrypted = box.encrypt(plaintext, nonce)
        return encrypted.nonce, encrypted.ciphertext

    @staticmethod
    def fetch_keybase_keys(username):
        """Fetch the NaCl public keys for a Keybase user.

        Uses the public Keybase HTTPS API to look up the user's
        Curve25519 (DH) and Ed25519 (signing) public keys.

        Returns a dict:
          {
            'dh':    bytes  -- 32-byte Curve25519 public key
            'eddsa': bytes  -- 32-byte Ed25519 verify key
          }
        or None on any error (user not found, network failure, etc.).
        """
        # Build the Keybase user lookup URL
        url = (
            "https://keybase.io/_/api/1.0/user/lookup.json"
            "?username={}&fields=public_keys".format(username)
        )

        logger.debug("Fetching Keybase public keys for user: %s", username)

        try:
            # Perform the HTTPS GET request
            r = requests.get(url, timeout=10)
            if r.status_code != requests.codes.ok:
                logger.warning(
                    "Keybase key lookup failed for %s: HTTP %d",
                    username,
                    r.status_code,
                )
                return None

            data = r.json()

        except requests.RequestException as exc:
            logger.warning(
                "Network error fetching Keybase keys for %s",
                username,
            )
            logger.debug("RequestException: %s", exc)
            return None

        except (ValueError, TypeError) as exc:
            logger.warning(
                "Invalid JSON in Keybase key response for %s",
                username,
            )
            logger.debug("JSONDecodeError: %s", exc)
            return None

        # Extract the NaCl key fields from the response
        try:
            them = data.get("them") or []
            user_data = them[0] if isinstance(them, list) else them
            nacl = user_data["public_keys"]["nacl"]

            # Parse the hex-encoded keys
            dh_hex = nacl.get("dh", "")
            eddsa_hex = nacl.get("eddsa", "")

            if not dh_hex or not eddsa_hex:
                logger.warning(
                    "Keybase user %s has no NaCl keys in profile",
                    username,
                )
                return None

            return {
                "dh": bytes.fromhex(dh_hex),
                "eddsa": bytes.fromhex(eddsa_hex),
            }

        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning(
                "Could not parse NaCl keys for Keybase user %s",
                username,
            )
            logger.debug("Key parse error: %s", exc)
            return None
