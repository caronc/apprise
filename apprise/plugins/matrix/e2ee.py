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
import secrets
import struct
import time as _time
import uuid

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import (
        hashes,
        hmac as _hmac_mod,
        padding as _pad_mod,
    )
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
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

# Bump this whenever the custom outbound MegOLM/session serialization or
# interoperability-critical behavior changes. Older cached sessions are then
# treated as incompatible and rotated automatically.
MATRIX_MEGOLM_STORE_VERSION = 1


# -----------------------------------------------------------------------
# Private helpers
# -----------------------------------------------------------------------


def _b64enc(data):
    """Matrix-style unpadded base64 of *data* as ASCII."""
    return base64.b64encode(data).rstrip(b"=").decode("utf-8")


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


def _verify_ed25519(public_key_b64, message_bytes, signature_b64):
    """Verify an Ed25519 signature.

    Returns ``True`` when *signature_b64* is a valid signature of
    *message_bytes* under *public_key_b64*.  Returns ``False`` on any
    error (wrong key, bad signature, decode failure, etc.).

    Requires ``MATRIX_E2EE_SUPPORT`` (the ``cryptography`` package).
    """
    try:
        pub = Ed25519PublicKey.from_public_bytes(_b64dec(public_key_b64))
        pub.verify(_b64dec(signature_b64), message_bytes)
        return True
    except Exception:
        return False


def verify_device_keys(dev_info, user_id, device_id):
    """Verify the Ed25519 self-signature on a /keys/query device object.

    Per the spec, the signed payload must carry ``user_id`` and
    ``device_id`` fields whose values match the identity being
    verified.  This prevents a malicious homeserver from substituting
    keys from one device into the record of another.

    Returns ``True`` only when all of the following hold:
    - ``dev_info["user_id"] == user_id``
    - ``dev_info["device_id"] == device_id``
    - The Ed25519 self-signature over the canonical payload is valid.
    """
    # Reject malformed server data before reading the device fields.
    if not isinstance(dev_info, dict):
        return False

    # Identity binding: payload fields must match who we think we're
    # verifying.  Without this a server could swap key objects across
    # users/devices and the signature would still verify.
    if dev_info.get("user_id") != user_id:
        return False
    if dev_info.get("device_id") != device_id:
        return False

    sig_key = "ed25519:{}".format(device_id)
    keys = dev_info.get("keys")
    ed25519_pub = keys.get(sig_key, "") if isinstance(keys, dict) else ""
    if not ed25519_pub:
        return False

    signatures = dev_info.get("signatures")
    user_sigs = (
        signatures.get(user_id) if isinstance(signatures, dict) else None
    )
    sig = user_sigs.get(sig_key, "") if isinstance(user_sigs, dict) else ""
    if not sig:
        return False

    # Signed payload: all fields except 'signatures' and 'unsigned'
    signed_obj = {
        k: v
        for k, v in dev_info.items()
        if k not in ("signatures", "unsigned")
    }
    return _verify_ed25519(ed25519_pub, _canonical_json(signed_obj), sig)


def verify_signed_otk(otk_obj, user_id, device_id, ed25519_pub_b64):
    """Verify the Ed25519 signature on a ``signed_curve25519`` OTK.

    The device signs the OTK object (excluding ``signatures``) with the
    same Ed25519 key published in its device keys.

    Returns ``True`` only when the signature is present and valid.
    """
    sig = (
        otk_obj.get("signatures", {})
        .get(user_id, {})
        .get("ed25519:{}".format(device_id), "")
    )
    if not sig:
        return False

    signed_obj = {k: v for k, v in otk_obj.items() if k != "signatures"}
    return _verify_ed25519(ed25519_pub_b64, _canonical_json(signed_obj), sig)


def encrypt_attachment(data):
    """Encrypt *data* bytes for upload to a Matrix E2EE room.

    Implements the Matrix attachment encryption spec (v2):
      https://spec.matrix.org/v1.11/client-server-api/#sending-encrypted-attachments

    Algorithm: AES-256-CTR.
    IV: 8 random bytes followed by 8 zero bytes (avoids counter wrap).

    Returns a ``(ciphertext, file_info)`` tuple where *file_info* is the
    ``EncryptedFile`` object to embed in the ``m.room.message`` event:

    .. code-block:: json

        {
            "v": "v2",
            "key": { "kty": "oct", "alg": "A256CTR", "k": "<key>",
                     "key_ops": ["encrypt", "decrypt"], "ext": true },
            "iv": "<base64url-nopad 16-byte IV>",
            "hashes": { "sha256": "<base64 SHA-256 of ciphertext>" }
        }
    """
    key = os.urandom(32)
    # IV: 8 random bytes + 8 zero bytes (spec requirement)
    iv = os.urandom(8) + b"\x00" * 8

    cipher = Cipher(
        algorithms.AES(key),
        modes.CTR(iv),
        backend=default_backend(),
    )
    enc = cipher.encryptor()
    ciphertext = enc.update(data) + enc.finalize()

    # SHA-256 of the ciphertext (for integrity verification by recipients)
    h = hashes.Hash(hashes.SHA256(), backend=default_backend())
    h.update(ciphertext)
    sha256_digest = h.finalize()

    # JWK key: base64url no-padding
    k_b64url = base64.urlsafe_b64encode(key).rstrip(b"=").decode()
    # IV: base64url no-padding (spec uses unpadded base64)
    iv_b64url = base64.urlsafe_b64encode(iv).rstrip(b"=").decode()
    # SHA-256 hash: standard base64 no-padding
    sha256_b64 = base64.b64encode(sha256_digest).rstrip(b"=").decode()

    file_info = {
        "v": "v2",
        "key": {
            "kty": "oct",
            "key_ops": ["encrypt", "decrypt"],
            "alg": "A256CTR",
            "k": k_b64url,
            "ext": True,
        },
        "iv": iv_b64url,
        "hashes": {"sha256": sha256_b64},
    }

    return ciphertext, file_info


class MatrixSASVerification:
    """Verify another session for the same user with Matrix SAS.

    The exchange reuses Apprise's existing encrypted device identity.
    """

    # Allow a generous margin beyond the device and master keys normally sent.
    MAX_MAC_KEYS = 10

    # Bound incoming key and MAC fields before processing them.
    MAX_FIELD_LEN = 512

    METHOD = "m.sas.v1"
    KEY_AGREEMENT = "curve25519-hkdf-sha256"
    HASH = "sha256"
    MAC = "hkdf-hmac-sha256.v2"
    # Advertise only decimal because it is the format Apprise displays.
    SAS_METHODS = ("decimal",)

    def __init__(
        self,
        own_user_id,
        own_device_id,
        peer_user_id,
        peer_device_id,
        start_content,
    ):
        """Create a responder for a validation start event."""
        # Retain both identities because their order affects every SAS MAC.
        self.own_user_id = own_user_id
        self.own_device_id = own_device_id
        self.peer_user_id = peer_user_id
        self.peer_device_id = peer_device_id
        # Copy the proposal so its commitment cannot change during
        # verification.
        self.start_content = dict(start_content)
        self.transaction_id = self.start_content.get("transaction_id")

        # Reject proposals that do not belong to the expected transaction.
        if not self.transaction_id or not self.peer_device_id:
            raise ValueError("Missing SAS transaction or peer device ID")
        if self.start_content.get("from_device") != self.peer_device_id:
            raise ValueError("SAS start device does not match request device")
        if self.start_content.get("method") != self.METHOD:
            raise ValueError("Unsupported SAS verification method")
        if self.KEY_AGREEMENT not in self.start_content.get(
            "key_agreement_protocols", []
        ):
            raise ValueError("Unsupported SAS key agreement")
        if self.HASH not in self.start_content.get("hashes", []):
            raise ValueError("Unsupported SAS hash")
        if self.MAC not in self.start_content.get(
            "message_authentication_codes", []
        ):
            raise ValueError("Unsupported SAS MAC")

        # Preserve only the display methods supported by both devices.
        offered_sas = self.start_content.get("short_authentication_string", [])
        self.sas_methods = [
            method for method in self.SAS_METHODS if method in offered_sas
        ]
        if "decimal" not in self.sas_methods:
            raise ValueError("SAS start does not offer decimal verification")

        # Create a fresh temporary key for this verification attempt.
        self._private_key = X25519PrivateKey.generate()
        self.public_key = _b64enc(
            self._private_key.public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw
            )
        )
        # The shared secret is available only after the peer key arrives.
        self._shared_secret = None
        self._peer_public_key = None
        self.state = "started"

    def accept_content(self):
        """Build ``m.key.verification.accept`` content."""
        if self.state != "started":
            raise ValueError("SAS verification start was already accepted")

        # Commit to our public key and the exact proposal being accepted.
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(self.public_key.encode("ascii"))
        digest.update(_canonical_json(self.start_content))
        commitment = _b64enc(digest.finalize())
        # The next valid event is the peer's temporary public key.
        self.state = "accepted"
        return {
            "transaction_id": self.transaction_id,
            "key_agreement_protocol": self.KEY_AGREEMENT,
            "hash": self.HASH,
            "message_authentication_code": self.MAC,
            "short_authentication_string": self.sas_methods,
            "commitment": commitment,
        }

    def receive_key(self, peer_public_key):
        """Accept the initiator's ephemeral key and establish the SAS."""
        if self.state != "accepted":
            raise ValueError("Unexpected SAS key event")
        if (
            not isinstance(peer_public_key, str)
            or not 0 < len(peer_public_key) <= self.MAX_FIELD_LEN
        ):
            raise ValueError("SAS peer key is missing or malformed")

        # Derive the secret shared only by the two temporary keys.
        peer_key = X25519PublicKey.from_public_bytes(_b64dec(peer_public_key))
        self._shared_secret = self._private_key.exchange(peer_key)
        # The displayed SAS also binds both temporary public keys.
        self._peer_public_key = peer_public_key
        self.state = "key_received"

    def key_content(self):
        """Build our ``m.key.verification.key`` content."""
        if self.state != "key_received":
            raise ValueError("SAS peer key has not been received")
        return {
            "transaction_id": self.transaction_id,
            "key": self.public_key,
        }

    def decimal_sas(self):
        """Derive the decimal Short Authentication String.

        Both devices derive three numbers from the shared secret. Comparing
        those numbers outside Matrix detects an intercepted exchange.
        """
        if self._shared_secret is None or self._peer_public_key is None:
            raise ValueError("SAS shared secret has not been established")

        # The peer initiated this exchange, so its identity and key come first.
        # This SAS context separates fields with "|"; the MAC context does not.
        info = (
            "MATRIX_KEY_VERIFICATION_SAS|"
            + self.peer_user_id
            + "|"
            + self.peer_device_id
            + "|"
            + self._peer_public_key
            + "|"
            + self.own_user_id
            + "|"
            + self.own_device_id
            + "|"
            + self.public_key
            + "|"
            + self.transaction_id
        ).encode("utf-8")
        sas_bytes = _hkdf_sha256(self._shared_secret, 5, salt=None, info=info)

        # The spec takes the top 39 of these 40 bits and splits them into
        # three 13-bit groups, each shown as a number from 1000 to 9191.
        value = int.from_bytes(sas_bytes, "big") >> 1
        return (
            ((value >> 26) & 0x1FFF) + 1000,
            ((value >> 13) & 0x1FFF) + 1000,
            (value & 0x1FFF) + 1000,
        )

    def _calculate_mac(
        self,
        value,
        key_id,
        sender_user_id,
        sender_device_id,
        receiver_user_id,
        receiver_device_id,
    ):
        """Calculate an ``hkdf-hmac-sha256.v2`` SAS MAC."""
        if self._shared_secret is None:
            raise ValueError("SAS shared secret has not been established")

        # Bind the proof to both devices, this transaction, and this key.
        info = (
            "MATRIX_KEY_VERIFICATION_MAC"
            + sender_user_id
            + sender_device_id
            + receiver_user_id
            + receiver_device_id
            + self.transaction_id
            + key_id
        ).encode("utf-8")
        # Derive a separate MAC key for each value being proven.
        mac_key = _hkdf_sha256(self._shared_secret, 32, salt=None, info=info)
        return _b64enc(_hmac_sha256(mac_key, value.encode("utf-8")))

    def mac_content(self, own_signing_key):
        """Build the MAC proving possession of Apprise's device key."""
        if self.state != "key_received":
            raise ValueError("SAS peer key has not been received")

        # Prove ownership of this device's long-term signing key.
        key_id = "ed25519:{}".format(self.own_device_id)
        content = {
            "transaction_id": self.transaction_id,
            "mac": {
                key_id: self._calculate_mac(
                    own_signing_key,
                    key_id,
                    self.own_user_id,
                    self.own_device_id,
                    self.peer_user_id,
                    self.peer_device_id,
                )
            },
            "keys": self._calculate_mac(
                key_id,
                "KEY_IDS",
                self.own_user_id,
                self.own_device_id,
                self.peer_user_id,
                self.peer_device_id,
            ),
        }
        # The responder now waits for the peer's matching proof.
        self.state = "mac_sent"
        return content

    def verify_peer_mac(self, content, peer_keys):
        """Validate the initiator's MACs against the queried keys."""
        if self.state != "mac_sent":
            raise ValueError("Unexpected SAS MAC event")
        if content.get("transaction_id") != self.transaction_id:
            raise ValueError("SAS MAC transaction does not match")

        # The peer must prove at least its own device signing key.
        macs = content.get("mac")
        if not isinstance(macs, dict) or not macs:
            raise ValueError("SAS MAC event contains no keys")
        if len(macs) > self.MAX_MAC_KEYS:
            # Reject oversized key lists before sorting or hashing them.
            raise ValueError("SAS MAC event carries too many keys")

        # Validate each bounded key ID and MAC before processing it.
        for key_id, mac_value in macs.items():
            if (
                not isinstance(key_id, str)
                or not 0 < len(key_id) <= self.MAX_FIELD_LEN
                or not isinstance(mac_value, str)
                or not 0 < len(mac_value) <= self.MAX_FIELD_LEN
            ):
                raise ValueError("SAS MAC event carries a malformed entry")

        device_key_id = "ed25519:{}".format(self.peer_device_id)
        if device_key_id not in macs:
            raise ValueError("SAS MAC omits the peer device key")

        keys_mac = content.get("keys", "")
        if (
            not isinstance(keys_mac, str)
            or not 0 < len(keys_mac) <= self.MAX_FIELD_LEN
        ):
            raise ValueError("SAS MAC event carries a malformed key list MAC")

        # First verify that the advertised key list was not changed in transit.
        key_ids = ",".join(sorted(macs))
        expected_keys_mac = self._calculate_mac(
            key_ids,
            "KEY_IDS",
            self.peer_user_id,
            self.peer_device_id,
            self.own_user_id,
            self.own_device_id,
        )
        if not secrets.compare_digest(keys_mac, expected_keys_mac):
            raise ValueError("SAS key list MAC does not match")

        # Then validate the proof for every key named by the peer.
        for key_id, received_mac in macs.items():
            try:
                public_key = peer_keys[key_id]
            except (KeyError, TypeError):
                raise ValueError("SAS MAC references an unknown key") from None
            if (
                not isinstance(public_key, str)
                or not 0 < len(public_key) <= self.MAX_FIELD_LEN
            ):
                raise ValueError("SAS MAC references a malformed key")
            expected_mac = self._calculate_mac(
                public_key,
                key_id,
                self.peer_user_id,
                self.peer_device_id,
                self.own_user_id,
                self.own_device_id,
            )
            if not secrets.compare_digest(received_mac, expected_mac):
                raise ValueError("SAS device key MAC does not match")

        # Every advertised proof matched the queried keys.
        self.state = "verified"
        return True


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

    def __init__(
        self,
        ik_priv_b64=None,
        sk_priv_b64=None,
        otks=None,
        fallback_otk=None,
    ):
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
        self._otks = dict(otks or {})
        self._fallback_otk = fallback_otk

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
            "otks": self._otks,
            "fallback_otk": self._fallback_otk,
        }

    @staticmethod
    def from_dict(data):
        """Restore from a ``to_dict()`` snapshot."""
        return MatrixOlmAccount(
            ik_priv_b64=data["ik"],
            sk_priv_b64=data["sk"],
            otks=data.get("otks"),
            fallback_otk=data.get("fallback_otk"),
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

    def _signed_curve25519_key(self, user_id, device_id, key_b64):
        """Wrap a Curve25519 key in a signed KeyObject."""
        payload = {"key": key_b64}
        payload["signatures"] = {
            user_id: {
                "ed25519:{}".format(device_id): self.sign(
                    _canonical_json(payload)
                )
            }
        }
        return payload

    def _ensure_otks(self, count=10):
        """Ensure at least *count* signed_curve25519 one-time keys exist."""
        while len(self._otks) < count:
            key_id = uuid.uuid4().hex[:10]
            priv = X25519PrivateKey.generate()
            self._otks[key_id] = _b64enc(
                priv.private_bytes(
                    Encoding.Raw, PrivateFormat.Raw, NoEncryption()
                )
            )

    def one_time_keys_payload(self, user_id, device_id, count=10):
        """Build signed ``one_time_keys`` for ``POST /keys/upload``."""
        self._ensure_otks(count=count)
        payload = {}
        for key_id, priv_b64 in self._otks.items():
            priv = X25519PrivateKey.from_private_bytes(_b64dec(priv_b64))
            pub = priv.public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw
            )
            payload["signed_curve25519:{}".format(key_id)] = (
                self._signed_curve25519_key(user_id, device_id, _b64enc(pub))
            )
        return payload

    def fallback_keys_payload(self, user_id, device_id):
        """Build signed ``fallback_keys`` for ``POST /keys/upload``."""
        if not self._fallback_otk:
            key_id = uuid.uuid4().hex[:10]
            priv = X25519PrivateKey.generate()
            self._fallback_otk = {
                "id": key_id,
                "sk": _b64enc(
                    priv.private_bytes(
                        Encoding.Raw, PrivateFormat.Raw, NoEncryption()
                    )
                ),
            }

        priv = X25519PrivateKey.from_private_bytes(
            _b64dec(self._fallback_otk["sk"])
        )
        pub = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        key_id = self._fallback_otk["id"]
        return {
            "signed_curve25519:{}".format(key_id): self._signed_curve25519_key(
                user_id, device_id, _b64enc(pub)
            )
        }

    def mark_keys_as_published(self):
        """Mark the current OTK batch as published.

        This mirrors stable python-olm's ``Account.mark_keys_as_published()``:
        the uploaded one-time keys are no longer treated as the next
        unpublished batch, so a subsequent upload can generate a fresh set.
        """
        self._otks.clear()

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

        # E_A is Alice's ephemeral key.  It serves BOTH as the Base-Key
        # (outer pre-key field 2) AND as the initial Ratchet-Key (inner
        # field 1).  The Olm spec Section 5.1 is explicit:
        #   "E_A^pub is also the ratchet key for the first message."
        # libolm passes the same keypair to both the X3DH and the ratchet
        # initialisation (ratchet.cpp: initialise_as_alice receives base_key
        # and uses it as the initial sender ratchet key).  Using two
        # different keys here breaks decryption.
        eph = X25519PrivateKey.generate()
        eph_pub = eph.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

        # Triple DH  (Olm spec, Section 4.1)
        #   DH1 = X25519(IK_A, OTK_B)
        #   DH2 = X25519(E_A, IK_B)
        #   DH3 = X25519(E_A, OTK_B)
        dh1 = self._ik.exchange(their_otk)
        dh2 = eph.exchange(their_ik)
        dh3 = eph.exchange(their_otk)

        # Root-key derivation (libolm ratchet.cpp initialise_as_alice /
        # vodozemac shared_secret.rs Shared3DHSecret::expand):
        #   IKM  = DH1 || DH2 || DH3  (96 bytes -- no zero prefix)
        #   salt = nullptr / 0x00*32   (RFC 5869: missing salt = HashLen zeros)
        #   info = "OLM_ROOT"
        #
        # libolm passes the 96-byte secret directly
        # (session.cpp: secret[3 * CURVE25519_SHARED_SECRET_LENGTH]).
        # vodozemac does the same (Shared3DHSecret is Box<[u8; 96]>).
        # Adding any prefix produces a different PRK and therefore
        # different root/chain keys, causing the recipient to fail to
        # decrypt the Olm pre-key message that carries the MegOLM room key.
        ikm = dh1 + dh2 + dh3
        keys = _hkdf_sha256(ikm, 64, salt=None, info=b"OLM_ROOT")
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
        # eph_pub is Alice's ephemeral key E_A.  Per Olm spec Section 5.1,
        # E_A^pub is used in BOTH the outer pre-key Base-Key field AND the
        # inner normal-message Ratchet-Key field.  They must be identical.
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
        # Field numbers from the Olm spec wire format:
        #   0x0A = field 1, wire-type 2 (bytes)  -> Ratchet-Key
        #   0x10 = field 2, wire-type 0 (varint) -> Chain-Index
        #   0x22 = field 4, wire-type 2 (bytes)  -> Cipher-Text
        # Note: there is no field 3 in the normal-message format; the
        # ciphertext is field 4 (tag 0x22), NOT field 3 (tag 0x1A).
        # E_A^pub appears in BOTH the inner Ratchet-Key (field 1) and the
        # outer Base-Key (field 2) -- same bytes, same key, per spec.
        inner = (
            b"\x03"
            + _pb_bytes(1, self._eph_pub)
            + _pb_varint_field(2, self._counter)
            + _pb_bytes(4, ciphertext)
        )
        inner_mac = _hmac_sha256(mac_key, inner)[:8]

        # -- Outer pre-key message  --------------------------------
        # Field numbers from the Olm spec wire format:
        #   0x0A = field 1 (bytes) -> One-Time-Key (Bob's OTK being consumed)
        #   0x12 = field 2 (bytes) -> Base-Key (Alice's E_A; same key as the
        #                              first Ratchet-Key)
        #   0x1A = field 3 (bytes) -> Identity-Key (Alice's identity key)
        #   0x22 = field 4 (bytes) -> Message (inner message + inner MAC)
        #
        # The outer pre-key message has NO trailing MAC of its own.
        # libolm session.cpp allocates exactly
        # encode_one_time_key_message_length() bytes -- no extra space for an
        # outer MAC.  vodozemac decodes the outer payload with prost (strict
        # protobuf) so extra bytes after the last field cause a DecodeError
        # and the session fails to establish.
        outer = (
            b"\x03"
            + _pb_bytes(1, self._their_otk_pub)
            + _pb_bytes(2, self._eph_pub)
            + _pb_bytes(3, self._our_ik_pub)
            + _pb_bytes(4, inner + inner_mac)
        )

        self._counter += 1
        return {"type": 0, "body": _b64enc(outer)}


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

        self._sk_pub = self._sk.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        # Session ID is the base64 of the Ed25519 signing public key
        self.session_id = _b64enc(self._sk_pub)
        self.created_at = (
            created_at if created_at is not None else _time.time()
        )

    # --- Ratchet ----------------------------------------------------------

    def _advance(self):
        """Advance the MegOLM ratchet by one step.

        Mirrors libolm megolm.c ``megolm_advance`` and vodozemac ratchet.rs
        ``Ratchet::advance``.

        The ratchet has 4 parts R[0..3].  On each step, determine the
        highest-index part h that stays constant:
          - counter+1 is a multiple of 2^24  → h=0 (advance R[0..3] from R[0])
          - counter+1 is a multiple of 2^16  → h=1 (advance R[1..3] from R[1])
          - counter+1 is a multiple of 2^8   → h=2 (advance R[2..3] from R[2])
          - otherwise                         → h=3 (advance R[3] from R[3])

        All derived parts are computed from the ORIGINAL value of R[h]
        (saved before any modification), then R[h] itself is updated last.
        This matches libolm's loop which processes higher indices first
        (i = 3 down to h), ensuring data[h] is still the original when it
        is finally overwritten at i==h.
        """
        r = self._ratchet
        n1 = self._counter + 1  # next counter value

        if n1 % (1 << 24) == 0:
            # h=0: all four parts derived from original R[0]
            orig = r[0]
            r[3] = _hmac_sha256(orig, b"\x03")
            r[2] = _hmac_sha256(orig, b"\x02")
            r[1] = _hmac_sha256(orig, b"\x01")
            r[0] = _hmac_sha256(orig, b"\x00")
        elif n1 % (1 << 16) == 0:
            # h=1: R[1..3] derived from original R[1]
            orig = r[1]
            r[3] = _hmac_sha256(orig, b"\x03")
            r[2] = _hmac_sha256(orig, b"\x02")
            r[1] = _hmac_sha256(orig, b"\x01")
        elif n1 % (1 << 8) == 0:
            # h=2: R[2..3] derived from original R[2]
            orig = r[2]
            r[3] = _hmac_sha256(orig, b"\x03")
            r[2] = _hmac_sha256(orig, b"\x02")
        else:
            # h=3: R[3] re-seeded from itself
            r[3] = _hmac_sha256(r[3], b"\x03")

        self._counter += 1

    def _message_keys(self):
        """Derive (aes_key, mac_key, iv) from the full ratchet state R_i.

        Per the MegOLM spec Section 4.3 and vodozemac (cipher/key.rs
        ``new_megolm``), the HKDF IKM is the complete 128-byte ratchet value
        R_i = R[0]||R[1]||R[2]||R[3].  Using only R[3] (32 bytes) produces
        different keys from what any standard client derives.

        Spec:  AES_KEY||HMAC_KEY||AES_IV = HKDF(0, R_i, "MEGOLM_KEYS", 80)
        """
        keys = _hkdf_sha256(
            b"".join(self._ratchet), 80, salt=None, info=b"MEGOLM_KEYS"
        )
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

        Wire format (MegOLM spec, Section 4):
          version (1 B = 0x03)
          | Protobuf body (field 8: message_index varint,
          |                field 9: ciphertext bytes)
          | HMAC-SHA-256 (8 B)
          | Ed25519 sig (64 B)

        Reference: MegOLM spec, Section 4.
        """
        # Keep Unicode compact so encryption does not carry JSON escape bloat.
        # Replace invalid code points before converting plaintext to bytes.
        plaintext = dumps(payload_dict, ensure_ascii=False).encode(
            "utf-8", errors="replace"
        )
        aes_key, mac_key, iv = self._message_keys()

        ct_bytes = _aes_cbc_encrypt(aes_key, iv, plaintext)
        # MegOLM spec wire format (libolm message.cpp):
        #   GROUP_MESSAGE_INDEX_TAG = 0x08  (field 1, wire-type 0 varint)
        #   GROUP_CIPHERTEXT_TAG    = 0x12  (field 2, wire-type 2 bytes)
        pb_body = _pb_varint_field(1, self._counter) + _pb_bytes(2, ct_bytes)
        body = b"\x03" + pb_body
        mac = _hmac_sha256(mac_key, body)[:8]
        sig = self._sk.sign(body + mac)

        self._advance()
        return _b64enc(body + mac + sig)

    # --- Session-key export  (shared via Olm to room members) ------------

    def session_key(self):
        """Base64 MegOLM session key for sharing in ``m.room_key`` events.

        Wire format (libolm outbound_group_session.c,
        ``olm_outbound_group_session_key``):
          version (1 B = 0x02) | counter (4 B big-endian)
          | R[0..3] (128 B) | Ed25519 signing pub key (32 B)
          | Ed25519 signature (64 B) over all preceding 165 bytes

        The signature lets the recipient verify the session key came from the
        device that owns the Ed25519 signing key published in /keys/upload.
        Without it, vodozemac and other clients reject the key.

        Reference: MegOLM spec, Section 2; libolm
        ``outbound_group_session.c``.
        """
        payload = (
            b"\x02"
            + struct.pack(">I", self._counter)
            + b"".join(self._ratchet)
            + self._sk_pub
        )
        sig = self._sk.sign(payload)
        return _b64enc(payload + sig)

    # --- Serialisation ---------------------------------------------------

    def to_dict(self):
        """Export session state for persistent storage."""
        return {
            "version": MATRIX_MEGOLM_STORE_VERSION,
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
        if data.get("version") != MATRIX_MEGOLM_STORE_VERSION:
            raise ValueError("Incompatible MegOLM session cache format")
        return MatrixMegOlmSession(
            ratchet=[_b64dec(r) for r in data["ratchet"]],
            counter=data["counter"],
            sk_priv_b64=data["sk"],
            created_at=data.get("created_at"),
        )
