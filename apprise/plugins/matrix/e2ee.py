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

# Minimal Olm + MegOLM outbound implementation for Matrix E2EE.
#
# Only the *sending* path is implemented, which is all Apprise requires.
# All cryptographic primitives come from the `cryptography` package that
# is already an optional Apprise dependency (used by pem.py, VAPID, FCM).
#
# Protocol references:
#  Olm spec:
#   https://gitlab.matrix.org/matrix-org/olm/-/blob/master/docs/olm.md
#  MegOLM spec:
#   https://gitlab.matrix.org/matrix-org/olm/-/blob/master/docs/megolm.md
#  Matrix E2EE client-server API:
#   https://spec.matrix.org/v1.11/client-server-api/
#   #end-to-end-encryption

import base64
from json import dumps
import os
import struct
import time as _time

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import (
        hashes,
        hmac as _hmac_mod,
        padding as _pad_mod,
    )
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey,
        X25519PublicKey,
    )
    from cryptography.hazmat.primitives.ciphers import (
        Cipher,
        algorithms,
        modes,
    )
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    # E2EE support is available
    MATRIX_E2EE_SUPPORT = True

except ImportError:
    # E2EE support unavailable; `pip install cryptography` to enable
    MATRIX_E2EE_SUPPORT = False


# Rotate the MegOLM session after this many messages
MEGOLM_ROTATION_MSGS = 100

# Rotate the MegOLM session after this many seconds (7 days)
MEGOLM_ROTATION_AGE = 60 * 60 * 24 * 7


# -----------------------------------------------------------------------
# Private helpers
# -----------------------------------------------------------------------


def _b64enc(data):
    """Standard base64 of *data* as a padded ASCII string."""
    return base64.b64encode(data).decode("utf-8")


def _b64dec(s):
    """Decode a base64 string; tolerates missing padding and URL-safe chars."""
    s = s.replace("-", "+").replace("_", "/")
    pad = len(s) % 4
    if pad:
        s += "=" * (4 - pad)
    return base64.b64decode(s)


def _hmac_sha256(key, data):
    """32-byte HMAC-SHA-256 of *data* keyed by *key*."""
    h = _hmac_mod.HMAC(key, hashes.SHA256(), backend=default_backend())
    h.update(data)
    return h.finalize()


def _hkdf_sha256(ikm, length, salt, info):
    """HKDF-SHA-256.  *salt* may be ``None`` or explicit ``bytes``."""
    return HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info,
        backend=default_backend(),
    ).derive(ikm)


def _aes_cbc_encrypt(key, iv, plaintext):
    """AES-256-CBC-encrypt *plaintext* with PKCS#7 padding."""
    padder = _pad_mod.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend(),
    )
    enc = cipher.encryptor()
    return enc.update(padded) + enc.finalize()


def _varint(n):
    """Encode *n* as a protobuf-style base-128 varint."""
    if n == 0:
        return b"\x00"
    out = []
    while n:
        byte = n & 0x7F
        n >>= 7
        if n:
            byte |= 0x80
        out.append(byte)
    return bytes(out)


def _pb_bytes(field_num, data):
    """Protobuf wire-type 2 (length-delimited bytes) field."""
    tag = _varint((field_num << 3) | 2)
    return tag + _varint(len(data)) + data


def _pb_varint_field(field_num, value):
    """Protobuf wire-type 0 (varint) field."""
    tag = _varint((field_num << 3) | 0)
    return tag + _varint(value)


def _canonical_json(obj):
    """UTF-8 canonical JSON (sorted keys, no spaces) for signing."""
    return dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


# -----------------------------------------------------------------------
# MatrixOlmAccount
# -----------------------------------------------------------------------


class MatrixOlmAccount:
    """Device-level Curve25519 + Ed25519 key pair.

    Generates a new key pair on first use and persists it via
    ``to_dict()`` / ``from_dict()``.  Also creates outbound Olm sessions
    used to distribute MegOLM room keys to other devices.

    Reference: Olm spec, Section 2 ("Keys").
    """

    def __init__(self, ik_priv_b64=None, sk_priv_b64=None):
        """Initialise from saved keys or generate a fresh key pair.

        Parameters are the base64-encoded raw 32-byte private key bytes
        for the Curve25519 identity key (*ik*) and Ed25519 signing key
        (*sk*).  Supply both or neither.
        """
        if ik_priv_b64 and sk_priv_b64:
            self._ik = X25519PrivateKey.from_private_bytes(
                _b64dec(ik_priv_b64)
            )
            self._sk = Ed25519PrivateKey.from_private_bytes(
                _b64dec(sk_priv_b64)
            )
        else:
            self._ik = X25519PrivateKey.generate()
            self._sk = Ed25519PrivateKey.generate()

        # Cache public-key bytes for efficiency
        self._ik_pub = self._ik.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        self._sk_pub = self._sk.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )

    # --- Public-key properties -------------------------------------------

    @property
    def identity_key(self):
        """Base64-encoded Curve25519 public identity key."""
        return _b64enc(self._ik_pub)

    @property
    def signing_key(self):
        """Base64-encoded Ed25519 public signing key."""
        return _b64enc(self._sk_pub)

    # --- Signing ---------------------------------------------------------

    def sign(self, data):
        """Ed25519-sign *data* (bytes or str) and return base64."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        return _b64enc(self._sk.sign(data))

    # --- Serialisation ---------------------------------------------------

    def to_dict(self):
        """Export private keys for persistent storage."""
        return {
            "ik": _b64enc(
                self._ik.private_bytes(
                    Encoding.Raw, PrivateFormat.Raw, NoEncryption()
                )
            ),
            "sk": _b64enc(
                self._sk.private_bytes(
                    Encoding.Raw, PrivateFormat.Raw, NoEncryption()
                )
            ),
        }

    @staticmethod
    def from_dict(data):
        """Restore from a ``to_dict()`` snapshot."""
        return MatrixOlmAccount(
            ik_priv_b64=data["ik"],
            sk_priv_b64=data["sk"],
        )

    # --- Key-upload payload ----------------------------------------------

    def device_keys_payload(self, user_id, device_id):
        """Build the signed ``device_keys`` object for ``POST /keys/upload``.

        Reference:
          https://spec.matrix.org/v1.11/client-server-api/
          #post_matrixclientv3keysupload
        """
        device_keys = {
            "algorithms": [
                "m.olm.v1.curve25519-aes-sha2",
                "m.megolm.v1.aes-sha2",
            ],
            "device_id": device_id,
            "keys": {
                "curve25519:{}".format(device_id): self.identity_key,
                "ed25519:{}".format(device_id): self.signing_key,
            },
            "user_id": user_id,
        }
        sig = self.sign(_canonical_json(device_keys))
        device_keys["signatures"] = {
            user_id: {"ed25519:{}".format(device_id): sig}
        }
        return device_keys

    # --- Outbound session ------------------------------------------------

    def create_outbound_session(
        self, their_identity_key_b64, their_one_time_key_b64
    ):
        """Create an outbound Olm session to a remote device.

        Performs the X3DH triple-DH key exchange and returns a
        :class:`MatrixOlmSession` ready to encrypt the first message.

        Parameters:
          their_identity_key_b64  - recipient's base64 Curve25519 pub key
          their_one_time_key_b64  - recipient's base64 Curve25519 OTK

        Reference: Olm spec, Section 4.1 ("Session establishment").
        """
        their_ik = X25519PublicKey.from_public_bytes(
            _b64dec(their_identity_key_b64)
        )
        their_otk = X25519PublicKey.from_public_bytes(
            _b64dec(their_one_time_key_b64)
        )

        # Ephemeral key pair (EK_A) -- discarded after session creation
        eph = X25519PrivateKey.generate()
        eph_pub = eph.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

        # Triple DH  (Olm spec, Section 4.1)
        #   DH1 = X25519(IK_A, OTK_B)
        #   DH2 = X25519(EK_A, IK_B)
        #   DH3 = X25519(EK_A, OTK_B)
        dh1 = self._ik.exchange(their_otk)
        dh2 = eph.exchange(their_ik)
        dh3 = eph.exchange(their_otk)

        # Root-key derivation
        #   IKM  = 0xFF*32 || DH1 || DH2 || DH3
        #   salt = 0x00*32
        #   info = "OLM_ROOT"
        ikm = b"\xff" * 32 + dh1 + dh2 + dh3
        keys = _hkdf_sha256(ikm, 64, salt=b"\x00" * 32, info=b"OLM_ROOT")
        root_key = keys[:32]
        chain_key = keys[32:]

        return MatrixOlmSession(
            our_ik_pub=self._ik_pub,
            eph_pub=eph_pub,
            their_otk_pub=_b64dec(their_one_time_key_b64),
            their_ik_pub=_b64dec(their_identity_key_b64),
            root_key=root_key,
            chain_key=chain_key,
        )


# -----------------------------------------------------------------------
# MatrixOlmSession
# -----------------------------------------------------------------------


class MatrixOlmSession:
    """Single-use outbound Olm session (type-0 pre-key messages only).

    Sufficient for delivering the MegOLM room-key to one recipient device.
    Each call to :meth:`encrypt` advances the chain ratchet once.

    Reference: Olm spec, Section 5 ("Message format").
    """

    def __init__(
        self,
        our_ik_pub,
        eph_pub,
        their_otk_pub,
        their_ik_pub,
        root_key,
        chain_key,
    ):
        self._our_ik_pub = our_ik_pub
        self._eph_pub = eph_pub
        self._their_otk_pub = their_otk_pub
        self._their_ik_pub = their_ik_pub
        self._root_key = root_key
        self._chain_key = chain_key
        self._counter = 0

    @property
    def their_identity_key(self):
        """Base64-encoded Curve25519 identity key of the remote device."""
        return _b64enc(self._their_ik_pub)

    def encrypt(self, plaintext):
        """Encrypt *plaintext* (str) as an Olm pre-key (type-0) message.

        Returns ``{"type": 0, "body": "<base64>"}`` suitable for
        inclusion in the ``ciphertext`` object of an
        ``m.olm.v1.curve25519-aes-sha2`` event.

        Reference: Olm spec, Section 5.1.
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        # -- Chain ratchet (Olm spec Section 6.1) -----------------
        msg_key = _hmac_sha256(self._chain_key, b"\x01")
        self._chain_key = _hmac_sha256(self._chain_key, b"\x02")

        # -- Expand msg_key -> AES key / MAC key / IV  -----------
        #    HKDF(msg_key, 80, salt=0x00*32, info="OLM_KEYS")
        keys = _hkdf_sha256(msg_key, 80, salt=b"\x00" * 32, info=b"OLM_KEYS")
        aes_key = keys[:32]
        mac_key = keys[32:64]
        iv = keys[64:80]

        # -- AES-256-CBC ------------------------------------------
        ciphertext = _aes_cbc_encrypt(aes_key, iv, plaintext)

        # -- Inner message  (version | fields | MAC) ---------------
        inner = (
            b"\x03"
            + _pb_bytes(1, self._eph_pub)
            + _pb_varint_field(2, self._counter)
            + _pb_bytes(3, ciphertext)
        )
        inner_mac = _hmac_sha256(mac_key, inner)[:8]

        # -- Outer pre-key message  --------------------------------
        outer = (
            b"\x03"
            + _pb_bytes(1, self._their_otk_pub)
            + _pb_bytes(2, self._eph_pub)
            + _pb_bytes(3, self._our_ik_pub)
            + _pb_bytes(4, inner + inner_mac)
        )
        outer_mac = _hmac_sha256(mac_key, outer)[:8]

        self._counter += 1
        return {"type": 0, "body": _b64enc(outer + outer_mac)}


# -----------------------------------------------------------------------
# MatrixMegOlmSession
# -----------------------------------------------------------------------


class MatrixMegOlmSession:
    """Outbound MegOLM session for room-message encryption.

    State: a 4-component 256-bit ratchet R[0..3], a 32-bit counter,
    and a per-session Ed25519 signing key.  The ratchet advances after
    every encrypted message.  See :data:`MEGOLM_ROTATION_MSGS` and
    :data:`MEGOLM_ROTATION_AGE` for rotation thresholds.

    Reference: MegOLM spec.
    """

    def __init__(
        self,
        ratchet=None,
        counter=0,
        sk_priv_b64=None,
        created_at=None,
    ):
        """New session (random state) or restore from ``to_dict()``."""
        self._ratchet = (
            [os.urandom(32) for _ in range(4)]
            if ratchet is None
            else [bytes(r) for r in ratchet]
        )
        self._counter = counter

        if sk_priv_b64 is None:
            self._sk = Ed25519PrivateKey.generate()
        else:
            self._sk = Ed25519PrivateKey.from_private_bytes(
                _b64dec(sk_priv_b64)
            )

        sk_pub = self._sk.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        self._sk_pub = sk_pub
        # Session ID is the base64 of the Ed25519 signing public key
        self.session_id = _b64enc(sk_pub)
        self.created_at = (
            created_at if created_at is not None else _time.time()
        )

    # --- Ratchet ----------------------------------------------------------

    def _advance(self):
        """Advance the MegOLM ratchet by one step.

        Advancement rule (MegOLM spec):
          - Every message: R[3] = HMAC-SHA256(R[2], b'\\x03')
          - Every 256 messages: first advance R[2], then cascade to R[3]
          - Every 65536 messages: advance R[1] then cascade down
          - Every 2^24 messages: advance R[0] then cascade all the way
        """
        r = self._ratchet
        i = self._counter

        if i > 0 and i % (1 << 24) == 0:
            r[0] = _hmac_sha256(r[0], b"\x00")
            r[1] = _hmac_sha256(r[0], b"\x01")
            r[2] = _hmac_sha256(r[1], b"\x02")
            r[3] = _hmac_sha256(r[2], b"\x03")
        elif i > 0 and i % (1 << 16) == 0:
            r[1] = _hmac_sha256(r[1], b"\x01")
            r[2] = _hmac_sha256(r[1], b"\x02")
            r[3] = _hmac_sha256(r[2], b"\x03")
        elif i > 0 and i % (1 << 8) == 0:
            r[2] = _hmac_sha256(r[2], b"\x02")
            r[3] = _hmac_sha256(r[2], b"\x03")
        else:
            r[3] = _hmac_sha256(r[2], b"\x03")

        self._counter += 1

    def _message_keys(self):
        """Derive (aes_key, mac_key, iv) from the current ratchet state."""
        # All four 32-byte ratchet components concatenated = 128 bytes
        state = b"".join(self._ratchet)
        keys = _hkdf_sha256(state, 80, salt=None, info=b"MEGOLM_KEYS")
        return keys[:32], keys[32:64], keys[64:80]

    # --- Rotation --------------------------------------------------------

    def should_rotate(self, msg_count=None):
        """Return ``True`` if this session has reached a rotation threshold."""
        if msg_count is None:
            msg_count = self._counter
        if msg_count >= MEGOLM_ROTATION_MSGS:
            return True
        return (_time.time() - self.created_at) >= MEGOLM_ROTATION_AGE

    # --- Encryption ------------------------------------------------------

    def encrypt(self, payload_dict):
        """Encrypt *payload_dict* and return base64 MegOLM ciphertext.

        Wire format:
          version (1 B = 0x03) | counter (4 B big-endian)
          | AES-CBC ciphertext | HMAC-SHA-256 (8 B) | Ed25519 sig (64 B)

        Reference: MegOLM spec, Section 4.
        """
        plaintext = dumps(payload_dict).encode("utf-8")
        aes_key, mac_key, iv = self._message_keys()

        ciphertext = _aes_cbc_encrypt(aes_key, iv, plaintext)
        body = b"\x03" + struct.pack(">I", self._counter) + ciphertext
        mac = _hmac_sha256(mac_key, body)[:8]
        sig = self._sk.sign(body + mac)

        self._advance()
        return _b64enc(body + mac + sig)

    # --- Session-key export  (shared via Olm to room members) ------------

    def session_key(self):
        """Base64 MegOLM session key for sharing in ``m.room_key`` events.

        Wire format:
          version (1 B = 0x02) | counter (4 B big-endian)
          | R[0..3] (128 B) | Ed25519 signing pub key (32 B)

        Reference: MegOLM spec, Section 2.
        """
        data = (
            b"\x02"
            + struct.pack(">I", self._counter)
            + b"".join(self._ratchet)
            + self._sk_pub
        )
        return _b64enc(data)

    # --- Serialisation ---------------------------------------------------

    def to_dict(self):
        """Export session state for persistent storage."""
        return {
            "ratchet": [_b64enc(r) for r in self._ratchet],
            "counter": self._counter,
            "sk": _b64enc(
                self._sk.private_bytes(
                    Encoding.Raw, PrivateFormat.Raw, NoEncryption()
                )
            ),
            "session_id": self.session_id,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(data):
        """Restore from a ``to_dict()`` snapshot."""
        return MatrixMegOlmSession(
            ratchet=[_b64dec(r) for r in data["ratchet"]],
            counter=data["counter"],
            sk_priv_b64=data["sk"],
            created_at=data.get("created_at"),
        )
