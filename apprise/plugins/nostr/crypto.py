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


# Signing and encryption used by the Nostr plugin.
#
# Nostr events are signed with BIP-340 Schnorr signatures over the
# secp256k1 curve.  The curve math below is done in plain Python so a
# public note can be sent without any extra packages.  Direct messages
# also need the optional cryptography package for ChaCha20 and AES.
#
# Resources:
# - https://github.com/nostr-protocol/nips/blob/master/01.md
# - https://github.com/nostr-protocol/nips/blob/master/19.md
# - https://github.com/nostr-protocol/nips/blob/master/44.md
# - https://github.com/nostr-protocol/nips/blob/master/59.md
# - https://github.com/bitcoin/bips/blob/master/bip-0340.mediawiki

from __future__ import annotations

from base64 import b64encode
import hashlib
import hmac
from json import dumps
import os
import re
import secrets
import time
from typing import Any, Optional

try:
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import (
        Cipher,
        algorithms,
        modes,
    )
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    # Direct messages can be encrypted
    NOSTR_CRYPTOGRAPHY_SUPPORT = True

except ImportError:
    # Only public notes can be sent
    NOSTR_CRYPTOGRAPHY_SUPPORT = False

# The secp256k1 field size, group order and generator point
SECP256K1_P = (
    0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
)
SECP256K1_N = (
    0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
)
SECP256K1_G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)

# The characters used by bech32 strings such as npub1... and nsec1...
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

# A key written as 64 hex characters
IS_HEX_KEY = re.compile(r"^[0-9a-f]{64}$", re.I)

# A signature as it appears in an event (128 lowercase hex characters)
IS_HEX_SIG = re.compile(r"^[0-9a-f]{128}$")

# Gift wrapped messages are back-dated by up to two days so their real
# send time stays hidden.
NOSTR_TIMESTAMP_JITTER = 2 * 24 * 60 * 60

# A point on the curve is an (x, y) tuple; None is the point at infinity
Point = Optional[tuple[int, int]]


def _point_add(p1: Point, p2: Point) -> Point:
    """Return the sum of two curve points."""
    # Adding the point at infinity changes nothing.
    if p1 is None:
        return p2

    if p2 is None:
        return p1

    # A point plus its own mirror image is the point at infinity.
    if p1[0] == p2[0] and p1[1] != p2[1]:
        return None

    # Doubling and adding use a different slope.
    lam = (
        3 * p1[0] * p1[0] * pow(2 * p1[1], -1, SECP256K1_P)
        if p1 == p2
        else (p2[1] - p1[1]) * pow(p2[0] - p1[0], -1, SECP256K1_P)
    ) % SECP256K1_P

    # Work out where the line meets the curve again.
    x3 = (lam * lam - p1[0] - p2[0]) % SECP256K1_P
    return (x3, (lam * (p1[0] - x3) - p1[1]) % SECP256K1_P)


def _point_mul(point: Point, scalar: int) -> Point:
    """Return ``point`` added to itself ``scalar`` times."""
    # Double and add, one bit of the scalar at a time.
    result = None
    for i in range(256):
        if (scalar >> i) & 1:
            result = _point_add(result, point)

        point = _point_add(point, point)

    return result


def _lift_x(x: int) -> Point:
    """Return the curve point with an even y for ``x``, or None."""
    # Values outside of the field are never valid.
    if x >= SECP256K1_P:
        return None

    # Solve y^2 = x^3 + 7 and confirm a square root exists.
    y_sq = (pow(x, 3, SECP256K1_P) + 7) % SECP256K1_P
    y = pow(y_sq, (SECP256K1_P + 1) // 4, SECP256K1_P)
    if pow(y, 2, SECP256K1_P) != y_sq:
        return None

    # BIP-340 keys always refer to the point with an even y.
    return (x, y if y % 2 == 0 else SECP256K1_P - y)


def _tagged_hash(tag: str, data: bytes) -> bytes:
    """Return the BIP-340 tagged SHA-256 hash of ``data``."""
    # The tag is hashed and repeated so each use gets its own hash.
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + data).digest()


def _bytes32(value: int) -> bytes:
    """Return ``value`` as 32 big-endian bytes."""
    # Every key, coordinate and signature half is 32 bytes long.
    return value.to_bytes(32, "big")


def _bech32_polymod(values: list[int]) -> int:
    """Return the bech32 checksum state for ``values``."""
    # These constants come from the bech32 specification (BIP-173).
    generator = (
        0x3B6A57B2,
        0x26508E6D,
        0x1EA119FA,
        0x3D4233DD,
        0x2A1462B3,
    )
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= generator[i] if (top >> i) & 1 else 0

    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    """Return the prefix (npub, nsec) in the form the checksum uses."""
    # The high bits come first, then a separator, then the low bits.
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _convert_bits(
    data: bytes, from_bits: int, to_bits: int, pad: bool
) -> Optional[list[int]]:
    """Regroup ``data`` from ``from_bits`` to ``to_bits`` sized values."""
    # Bits are pushed into an accumulator and pulled out in new sizes.
    acc = 0
    bits = 0
    result = []
    max_value = (1 << to_bits) - 1
    for value in data:
        acc = (acc << from_bits) | value
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            result.append((acc >> bits) & max_value)

    if pad:
        # Encoding pads the final group with zero bits.
        if bits:
            result.append((acc << (to_bits - bits)) & max_value)

    elif bits >= from_bits or ((acc << (to_bits - bits)) & max_value):
        # Decoding must not leave meaningful bits behind.
        return None

    return result


def bech32_encode(hrp: str, data: bytes) -> str:
    """Return ``data`` as a bech32 string starting with ``hrp``."""
    # Regroup the bytes into 5-bit values and add the checksum.
    values = _convert_bits(data, 8, 5, True)
    polymod = _bech32_polymod(_bech32_hrp_expand(hrp) + values + [0] * 6) ^ 1
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(BECH32_CHARSET[v] for v in values + checksum)


def bech32_decode(value: str) -> Optional[tuple[str, bytes]]:
    """Return the prefix and bytes held in a bech32 string, or None."""
    # The prefix is everything before the last "1".
    value = value.lower()
    pos = value.rfind("1")
    if pos < 1 or pos + 7 > len(value):
        return None

    # Every character after the prefix must be a bech32 character.
    hrp = value[:pos]
    if any(c not in BECH32_CHARSET for c in value[pos + 1 :]):
        return None

    # The checksum must agree with the rest of the string.
    values = [BECH32_CHARSET.index(c) for c in value[pos + 1 :]]
    if _bech32_polymod(_bech32_hrp_expand(hrp) + values) != 1:
        return None

    # Drop the checksum and regroup the remainder back into bytes.
    data = _convert_bits(bytes(values[:-6]), 5, 8, False)
    return None if data is None else (hrp, bytes(data))


def decode_key(value: Any, hrp: str) -> Optional[str]:
    """Return a key in hex from 64 hex characters or a bech32 ``hrp``."""
    # Anything other than a string can not be a key.
    if not isinstance(value, str):
        return None

    # Hex keys are used as they are.
    value = value.strip()
    if IS_HEX_KEY.match(value):
        return value.lower()

    # Otherwise it must be a bech32 key with the expected prefix.
    decoded = bech32_decode(value)
    if decoded and decoded[0] == hrp and len(decoded[1]) == 32:
        return decoded[1].hex()

    return None


def is_public_key(pubkey: str) -> bool:
    """Return True if ``pubkey`` (hex) is a usable point on the curve."""
    # A public key is the x coordinate of a point on the curve.
    return _lift_x(int(pubkey, 16)) is not None


def event_id(event: dict[str, Any]) -> str:
    """Return the NIP-01 id of ``event``."""
    # The id is the hash of a compact JSON array of the event fields.
    serialized = dumps(
        [
            0,
            event["pubkey"],
            event["created_at"],
            event["kind"],
            event["tags"],
            event["content"],
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def verify_event(event: Any) -> bool:
    """Return True if ``event`` has a valid id and signature."""
    # Every field must have the shape NIP-01 describes before it is used;
    # bool is left out on purpose as Python treats it as an int
    if not (
        isinstance(event, dict)
        and all(
            isinstance(event.get(name), str)
            for name in ("id", "pubkey", "sig", "content")
        )
        and IS_HEX_KEY.match(event["id"])
        and IS_HEX_KEY.match(event["pubkey"])
        and IS_HEX_SIG.match(event["sig"])
        and all(
            type(event.get(name)) is int for name in ("created_at", "kind")
        )
        and isinstance(event.get("tags"), list)
        and all(
            isinstance(tag, list) and all(isinstance(v, str) for v in tag)
            for tag in event["tags"]
        )
    ):
        return False

    # The id must match the content and the signature must be ours.
    pubkey = _lift_x(int(event["pubkey"], 16))
    sig = bytes.fromhex(event["sig"])
    if pubkey is None or event_id(event) != event["id"]:
        return False

    # Split the signature into its point (r) and scalar (s) halves.
    r = int.from_bytes(sig[:32], "big")
    s = int.from_bytes(sig[32:], "big")
    if r >= SECP256K1_P or s >= SECP256K1_N:
        return False

    # Rebuild the point the signer committed to and compare.
    e = (
        int.from_bytes(
            _tagged_hash(
                "BIP0340/challenge",
                sig[:32] + _bytes32(pubkey[0]) + bytes.fromhex(event["id"]),
            ),
            "big",
        )
        % SECP256K1_N
    )
    point = _point_add(
        _point_mul(SECP256K1_G, s),
        _point_mul(pubkey, SECP256K1_N - e),
    )
    return point is not None and point[1] % 2 == 0 and point[0] == r


class NostrKey:
    """A secp256k1 key pair used to sign Nostr events."""

    __slots__ = ("public_key", "secret", "signing_secret")

    def __init__(self, secret: Optional[int] = None) -> None:
        """Load ``secret``, or make a new random key when it is None."""
        # A random key is used for each gift wrap envelope.
        self.secret = (
            secret if secret else secrets.randbelow(SECP256K1_N - 1) + 1
        )

        # Our public key is the x coordinate of secret * G, in hex.
        point = _point_mul(SECP256K1_G, self.secret)
        self.public_key = _bytes32(point[0]).hex()

        # BIP-340 signs with whichever of d or n - d gives an even y.
        self.signing_secret = (
            self.secret if point[1] % 2 == 0 else SECP256K1_N - self.secret
        )

    def sign(
        self,
        kind: int,
        content: str,
        tags: Optional[list[list[str]]] = None,
        created_at: Optional[int] = None,
    ) -> dict[str, Any]:
        """Return a new signed event."""
        # Build the event and work out its id.
        event = rumor(self.public_key, kind, content, tags, created_at)
        msg = bytes.fromhex(event["id"])

        # Derive the nonce from the key, the message and fresh randomness.
        d = self.signing_secret
        pubkey = bytes.fromhex(self.public_key)
        t = _bytes32(
            d
            ^ int.from_bytes(
                _tagged_hash("BIP0340/aux", os.urandom(32)), "big"
            )
        )
        k0 = (
            int.from_bytes(
                _tagged_hash("BIP0340/nonce", t + pubkey + msg),
                "big",
            )
            % SECP256K1_N
        )

        # Commit to the nonce point, again using the even y version.
        r = _point_mul(SECP256K1_G, k0)
        k = k0 if r[1] % 2 == 0 else SECP256K1_N - k0
        e = (
            int.from_bytes(
                _tagged_hash(
                    "BIP0340/challenge",
                    _bytes32(r[0]) + pubkey + msg,
                ),
                "big",
            )
            % SECP256K1_N
        )

        # The signature is the nonce point followed by the scalar.
        event["sig"] = (
            _bytes32(r[0]) + _bytes32((k + e * d) % SECP256K1_N)
        ).hex()
        return event

    def shared_x(self, pubkey: str) -> bytes:
        """Return the ECDH shared x coordinate with ``pubkey``."""
        # Both NIP-04 and NIP-44 use the raw (unhashed) x coordinate.
        return _bytes32(_point_mul(_lift_x(int(pubkey, 16)), self.secret)[0])

    def conversation_key(self, pubkey: str) -> bytes:
        """Return the NIP-44 conversation key shared with ``pubkey``."""
        # This is an HKDF-extract with the fixed "nip44-v2" salt.
        return hmac.new(
            b"nip44-v2", self.shared_x(pubkey), hashlib.sha256
        ).digest()


def rumor(
    pubkey: str,
    kind: int,
    content: str,
    tags: Optional[list[list[str]]] = None,
    created_at: Optional[int] = None,
) -> dict[str, Any]:
    """Return an unsigned event with its id filled in."""
    # Events default to the current time.
    event = {
        "pubkey": pubkey,
        "created_at": (int(time.time()) if created_at is None else created_at),
        "kind": kind,
        "tags": tags or [],
        "content": content,
    }

    # The id covers every field above.
    event["id"] = event_id(event)
    return event


def _nip44_padded_len(length: int) -> int:
    """Return the NIP-44 padded size for a ``length`` byte message."""
    # Short messages all pad to 32 bytes.
    if length <= 32:
        return 32

    # Longer ones pad up in chunks that grow with the message.
    next_power = 1 << (length - 1).bit_length()
    chunk = 32 if next_power <= 256 else next_power // 8
    return chunk * ((length - 1) // chunk + 1)


def nip44_encrypt(
    plaintext: str, conversation_key: bytes, nonce: Optional[bytes] = None
) -> str:
    """Return ``plaintext`` encrypted with NIP-44 version 2."""
    # A fresh random nonce is used for every message.
    nonce = nonce or os.urandom(32)

    # Expand the conversation key into this message's keys (HKDF-expand).
    keys = b""
    block = b""
    for counter in range(1, 4):
        block = hmac.new(
            conversation_key,
            block + nonce + bytes([counter]),
            hashlib.sha256,
        ).digest()
        keys += block

    # Prefix the length and pad the message so its size is hidden.
    data = plaintext.encode("utf-8")
    prefix = (
        len(data).to_bytes(2, "big")
        if len(data) < 65536
        else b"\x00\x00" + len(data).to_bytes(4, "big")
    )
    padded = prefix + data + bytes(_nip44_padded_len(len(data)) - len(data))

    # ChaCha20 here takes a 4 byte counter (zero) before the nonce.
    encryptor = Cipher(
        algorithms.ChaCha20(keys[:32], bytes(4) + keys[32:44]), mode=None
    ).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    # Authenticate the nonce and ciphertext together.
    mac = hmac.new(keys[44:76], nonce + ciphertext, hashlib.sha256).digest()
    return b64encode(b"\x02" + nonce + ciphertext + mac).decode()


def nip04_encrypt(plaintext: str, shared_x: bytes) -> str:
    """Return ``plaintext`` encrypted the older NIP-04 way."""
    # Pad the message to the AES block size.
    padder = padding.PKCS7(128).padder()
    data = padder.update(plaintext.encode("utf-8")) + padder.finalize()

    # Encrypt with AES-256-CBC using the shared x coordinate as the key.
    iv = os.urandom(16)
    encryptor = Cipher(algorithms.AES(shared_x), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(data) + encryptor.finalize()

    # The IV travels alongside the message like a query string.
    return "{}?iv={}".format(
        b64encode(ciphertext).decode(), b64encode(iv).decode()
    )


def encrypt_file(data: bytes) -> tuple[bytes, str, str]:
    """Return ``data`` encrypted with AES-256-GCM, its key and nonce."""
    # Each file gets its own key and a 16 byte nonce, as NIP-17 clients
    # such as Amethyst expect.  Both are shared inside the sealed message.
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(16)
    return (AESGCM(key).encrypt(nonce, data, None), key.hex(), nonce.hex())


def gift_wrap(
    sender: NostrKey, pubkey: str, message: dict[str, Any]
) -> dict[str, Any]:
    """Return ``message`` sealed and gift wrapped for ``pubkey``."""
    # The seal proves who sent the message while hiding what it says.
    now = int(time.time())
    seal = sender.sign(
        13,
        nip44_encrypt(
            dumps(message, ensure_ascii=False),
            sender.conversation_key(pubkey),
        ),
        created_at=now - secrets.randbelow(NOSTR_TIMESTAMP_JITTER),
    )

    # A throwaway key wraps the seal so the sender stays hidden too.
    wrapper = NostrKey()
    return wrapper.sign(
        1059,
        nip44_encrypt(
            dumps(seal, ensure_ascii=False),
            wrapper.conversation_key(pubkey),
        ),
        tags=[["p", pubkey]],
        created_at=now - secrets.randbelow(NOSTR_TIMESTAMP_JITTER),
    )
