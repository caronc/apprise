# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

import base64
import binascii
import json
import os
import struct
from typing import Optional, Union

from ..apprise_attachment import AppriseAttachment
from ..asset import AppriseAsset
from ..exception import ApprisePluginException
from ..logger import logger
from ..utils.base64 import base64_urldecode, base64_urlencode

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import (
        decode_dss_signature,
    )
    from cryptography.hazmat.primitives.ciphers import (
        Cipher,
        algorithms,
        modes,
    )
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    # PEM Support enabled
    PEM_SUPPORT = True

except ImportError:
    # PEM Support disabled
    PEM_SUPPORT = False


class ApprisePEMException(ApprisePluginException):
    """Thrown when there is an error with the PEM Controller."""

    def __init__(self, message, error_code=612):
        super().__init__(message, error_code=error_code)


class ApprisePEMController:
    """PEM Controller Tool for the Apprise Library."""

    # There is no reason a PEM Public Key should exceed 8K in size
    # If it is more than this, then it is not accepted
    max_pem_public_key_size = 8000

    # There is no reason a PEM Private Key should exceed 8K in size
    # If it is more than this, then it is not accepted
    max_pem_private_key_size = 8000

    # Maximum Vapid Message Size
    max_webpush_record_size = 4096

    def __init__(
        self,
        path: str,
        pub_keyfile: Optional[str] = None,
        prv_keyfile: Optional[str] = None,
        name: Optional[str] = None,
        asset: Optional[AppriseAsset] = None,
        **kwargs,
    ) -> None:
        """Path should be the directory keys can be written and read from such
        as <notifyobject>.store.path.

        Optionally additionally specify a keyfile to explicitly open
        """

        # Directory we can work with
        self.path = path

        # Prepare our Key Placeholders
        self.__private_key = None
        self.__public_key = None

        # Our name (id)
        self.name = (
            name.strip(" \t/-+!$@#*").lower() if isinstance(name, str) else ""
        )

        # Prepare our Asset Object
        self.asset = (
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()
        )

        # Our temporary reference points
        self._prv_keyfile = AppriseAttachment(asset=self.asset)
        self._pub_keyfile = AppriseAttachment(asset=self.asset)

        if prv_keyfile:
            self.load_private_key(prv_keyfile)

        elif pub_keyfile:
            self.load_public_key(pub_keyfile)

        else:
            self._pub_keyfile = None

    def load_private_key(
        self, path: Optional[str] = None, *names: str
    ) -> bool:
        """Load Private key and from that we can prepare our public key."""

        if path is None:
            # Auto-load our content
            return bool(self.private_keyfile(*names))

        # Create ourselves an Attachment to work with; this grants us the
        # ability to pull this key from a remote site or anything else
        # supported by the Attachment object
        self._prv_keyfile = AppriseAttachment(asset=self.asset)

        # Add our definition to our pem_key reference
        self._prv_keyfile.add(path)

        # Enforce maximum file size
        self._prv_keyfile[0].max_file_size = self.max_pem_private_key_size

        #
        # Reset Public key
        #
        self._pub_keyfile = AppriseAttachment(asset=self.asset)

        #
        # Reset our internal keys
        #
        self.__private_key = None
        self.__public_key = None

        if not self._prv_keyfile.sync():
            # Early exit
            logger.error(f"Could not access PEM Private Key {path}.")
            return False

        try:
            with open(self._prv_keyfile[0].path, "rb") as f:
                self.__private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,  # or provide the password if encrypted
                    backend=default_backend(),
                )

        except (ValueError, TypeError):
            logger.debug(
                "PEM Private Key file specified is not supported (%s)",
                type(path),
            )
            return False

        except FileNotFoundError:
            logger.debug("PEM Private Key file not found: %s", path)
            return False

        except OSError as e:
            logger.warning("Error accessing PEM Private Key file %s", path)
            logger.debug(f"I/O Exception: {e}")
            return False

        #
        # Generate our public key
        #
        self.__public_key = self.__private_key.public_key()

        # Load our private key
        return bool(self.__private_key)

    def load_public_key(self, path: Optional[str] = None, *names: str) -> bool:
        """Load Public key only.

        Note: with just a public key you can only decrypt, encryption is not
              possible.
        """

        if path is None:
            # Auto-load our content
            return bool(self.public_keyfile(*names))

        # Create ourselves an Attachment to work with; this grants us the
        # ability to pull this key from a remote site or anything else
        # supported by the Attachment object
        self._pub_keyfile = AppriseAttachment(asset=self.asset)

        # Add our definition to our pem_key reference
        self._pub_keyfile.add(path)

        # Enforce maximum file size
        self._pub_keyfile[0].max_file_size = self.max_pem_public_key_size

        #
        # Reset Private key
        #
        self._prv_keyfile = AppriseAttachment(asset=self.asset)

        #
        # Reset our internal keys
        #
        self.__private_key = None
        self.__public_key = None

        if not self._pub_keyfile.sync():
            # Early exit
            logger.error(f"Could not access PEM Public Key {path}.")
            return False

        try:
            with open(path, "rb") as key_file:
                self.__public_key = serialization.load_pem_public_key(
                    key_file.read(), backend=default_backend()
                )

        except (ValueError, TypeError):
            logger.debug(
                "PEM Public Key file specified is not supported (%s)",
                type(path),
            )
            return False

        except FileNotFoundError:
            # Generate keys
            logger.debug("PEM Public Key file not found: %s", path)
            return False

        except OSError as e:
            logger.warning("Error accessing PEM Public Key file %s", path)
            logger.debug(f"I/O Exception: {e}")
            return False

        # Load our private key
        return bool(self.__public_key)

    def keygen(self, name: "Optional[str]" = None, force: bool = False):
        """Generates a set of keys based on name configured."""

        if not PEM_SUPPORT:
            msg = "PEM Support unavailable; install cryptography library"
            logger.warning(msg)
            raise ApprisePEMException(msg)

        # Detect if a key has been loaded or not
        has_key = bool(
            self.private_key(autogen=False) or self.public_key(autogen=False)
        )

        if (has_key and not (name or force)) or not self.path:
            logger.trace(
                "PEM keygen disabled, reason=%s",
                "keyfile-defined" if not has_key else "no-write-path",
            )
            return False

        # Create a new private/public key pair
        self.__private_key = ec.generate_private_key(
            ec.SECP256R1(), default_backend()
        )
        self.__public_key = self.__private_key.public_key()

        #
        # Prepare our PEM formatted output files
        #
        private_key = self.__private_key.private_bytes(
            Encoding.PEM,
            PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )

        public_key = self.__public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        )

        if not name:
            name = self.name

        file_prefix = "" if not name else f"{name}-"
        pub_path = os.path.join(self.path, f"{file_prefix}public_key.pem")
        prv_path = os.path.join(self.path, f"{file_prefix}private_key.pem")

        if not force:
            if os.path.isfile(pub_path):
                logger.debug(
                    "PEM generation skipped; Public Key already exists: %s/%s",
                    os.path.dirname(pub_path),
                    os.path.basename(pub_path),
                )
                return False

            if os.path.isfile(prv_path):
                logger.debug(
                    "PEM generation skipped; Private Key already exists: %s%s",
                    os.path.dirname(prv_path),
                    os.path.basename(prv_path),
                )
                return False

        try:
            # Write our keys to disk
            with open(pub_path, "wb") as f:
                f.write(public_key)

        except OSError as e:
            logger.warning("Error writing Public PEM file %s", pub_path)
            logger.debug(f"I/O Exception: {e}")

            # Cleanup
            try:
                os.unlink(pub_path)
                logger.trace("Removed %s", pub_path)

            except OSError:
                pass

            return False

        try:
            with open(prv_path, "wb") as f:
                f.write(private_key)

        except OSError as e:
            logger.warning("Error writing Private PEM file %s", prv_path)
            logger.debug(f"I/O Exception: {e}")

            try:
                os.unlink(pub_path)
                logger.trace("Removed %s", pub_path)

            except OSError:
                pass

            try:
                os.unlink(prv_path)
                logger.trace("Removed %s", prv_path)

            except OSError:
                pass

            return False

        # Update our local file references
        self._prv_keyfile = AppriseAttachment(asset=self.asset)
        self._prv_keyfile.add(prv_path)

        self._pub_keyfile = AppriseAttachment(asset=self.asset)
        self._pub_keyfile.add(pub_path)

        logger.info(
            "Wrote Public/Private PEM key pair for %s/%s",
            os.path.dirname(pub_path),
            os.path.basename(pub_path),
        )
        return True

    def public_keyfile(self, *names: str) -> Optional[str]:
        """Returns the first match of a useable public key based names
        provided."""

        if not PEM_SUPPORT:
            msg = "PEM Support unavailable; install cryptography library"
            logger.warning(msg)
            raise ApprisePEMException(msg)

        if self._pub_keyfile:
            # If our code reaches here, then we fetch our public key
            pem_key = self._pub_keyfile[0]
            if not pem_key:
                # We could not access the attachment
                logger.error(
                    "Could not access PEM Public Key"
                    f" {pem_key.url(privacy=True)}."
                )
                return False

            return pem_key.path

        elif not self.path:
            # No path
            return None

        fnames = [
            "public_key.pem",
            "public.pem",
            "pub.pem",
        ]

        if self.name:
            # Include our name in the list
            fnames = [self.name, *names]

        for name in names:
            fnames.insert(0, f"{name}-public_key.pem")

            _entry = name.lower()
            fnames.insert(0, f"{_entry}-public_key.pem")

        return next(
            (
                os.path.join(self.path, fname)
                for fname in fnames
                if os.path.isfile(os.path.join(self.path, fname))
            ),
            None,
        )

    def private_keyfile(self, *names: str) -> Optional[str]:
        """Returns the first match of a useable private key based names
        provided."""

        if not PEM_SUPPORT:
            msg = "PEM Support unavailable; install cryptography library"
            logger.warning(msg)
            raise ApprisePEMException(msg)

        if self._prv_keyfile:
            # If our code reaches here, then we fetch our private key
            pem_key = self._prv_keyfile[0]
            if not pem_key:
                # We could not access the attachment
                logger.error(
                    "Could not access PEM Private Key"
                    f" {pem_key.url(privacy=True)}."
                )
                return False

            return pem_key.path

        elif not self.path:
            # No path
            return None

        fnames = [
            "private_key.pem",
            "private.pem",
            "prv.pem",
        ]

        if self.name:
            # Include our name in the list
            fnames = [self.name, *names]

        for name in names:
            fnames.insert(0, f"{name}-private_key.pem")

            _entry = name.lower()
            fnames.insert(0, f"{_entry}-private_key.pem")

        return next(
            (
                os.path.join(self.path, fname)
                for fname in fnames
                if os.path.isfile(os.path.join(self.path, fname))
            ),
            None,
        )

    def public_key(
        self,
        *names: str,
        autogen: Optional[bool] = None,
        autodetect: bool = True,
    ) -> Optional["ec.EllipticCurvePublicKey"]:
        """Opens a spcified pem public file and returns the key from it which
        is used to decrypt the message."""
        if self.__public_key or not autodetect:
            return self.__public_key

        path = self.public_keyfile(*names)
        if not path:
            if (
                autogen if autogen is not None else self.asset.pem_autogen
            ) and self.keygen(*names):
                path = self.public_keyfile(*names)
                if path:
                    # We should get a hit now
                    return self.public_key(autogen=False)

            logger.warning("No PEM Public Key could be loaded")
            return None

        return (
            self.__public_key
            if (
                self.load_public_key(path)
                or
                # Try to see if we can load a private key (which we ca
                # generate a public from)
                self.private_key(*names, autogen=autogen)
            )
            else None
        )

    def private_key(
        self,
        *names: str,
        autogen: Optional[bool] = None,
        autodetect: bool = True,
    ) -> Optional["ec.EllipticCurvePrivateKey"]:
        """Opens a spcified pem private file and returns the key from it which
        is used to encrypt the message."""
        if self.__private_key or not autodetect:
            return self.__private_key

        path = self.private_keyfile(*names)
        if not path:
            if (
                autogen if autogen is not None else self.asset.pem_autogen
            ) and self.keygen(*names):
                path = self.private_keyfile(*names)
                if path:
                    # We should get a hit now
                    return self.private_key(autogen=False)

            logger.warning("No PEM Private Key could be loaded")
            return None

        return self.__private_key if self.load_private_key(path) else None

    def encrypt_webpush(
        self,
        message: Union[str, bytes],
        public_key: "ec.EllipticCurvePublicKey",
        auth_secret: bytes,
    ) -> bytes:
        """Encrypt a WebPush message using the recipient's public key and auth
        secret.

        Accepts input message as str or bytes.
        """
        if isinstance(message, str):
            message = message.encode("utf-8")

        # 1. Generate ephemeral EC private/Public key
        ephemeral_private_key = ec.generate_private_key(
            ec.SECP256R1(), default_backend()
        )
        ephemeral_public_key = ephemeral_private_key.public_key().public_bytes(
            encoding=Encoding.X962, format=PublicFormat.UncompressedPoint
        )

        # 2. Random salt
        salt = os.urandom(16)

        # 3. Generate shared secret via ECDH
        shared_secret = ephemeral_private_key.exchange(ec.ECDH(), public_key)

        # 4. Derive PRK using HKDF (first phase)
        recipient_public_key_bytes = public_key.public_bytes(
            encoding=Encoding.X962,
            format=PublicFormat.UncompressedPoint,
        )

        # 5. Derive Encryption key
        hkdf_secret = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=auth_secret,
            info=b"WebPush: info\x00"
            + recipient_public_key_bytes
            + ephemeral_public_key,
            backend=default_backend(),
        ).derive(shared_secret)

        # 6. Derive Content Encryption Key
        hkdf_key = HKDF(
            algorithm=hashes.SHA256(),
            length=16,
            salt=salt,
            info=b"Content-Encoding: aes128gcm\x00",
            backend=default_backend(),
        ).derive(hkdf_secret)

        # 7. Derive Nonce
        hkdf_nonce = HKDF(
            algorithm=hashes.SHA256(),
            length=12,
            salt=salt,
            info=b"Content-Encoding: nonce\x00",
            backend=default_backend(),
        ).derive(hkdf_secret)

        # 8. Encrypt the message
        aesgcm = AESGCM(hkdf_key)
        # RFC8291 requires us to add '\0x02' byte to end of message
        ciphertext = aesgcm.encrypt(
            hkdf_nonce, message + b"\x02", associated_data=None
        )

        # 9. Build WebPush header + payload
        header = salt
        header += struct.pack("!L", self.max_webpush_record_size)
        header += struct.pack("!B", len(ephemeral_public_key))
        header += ephemeral_public_key
        header += ciphertext

        return header

    def encrypt(
        self,
        message: Union[str, bytes],
        public_key: "Optional[ec.EllipticCurvePublicKey]" = None,
        salt: Optional[bytes] = None,
    ) -> Optional[str]:
        """Encrypts a message using the recipient's public key (or self public
        key if none provided).

        Message can be str or bytes.
        """

        if not PEM_SUPPORT:
            msg = "PEM Support unavailable; install cryptography library"
            logger.warning(msg)
            raise ApprisePEMException(msg)

        # 1. Handle string vs bytes input
        if isinstance(message, str):
            message = message.encode("utf-8")

        # 2. Select public key
        if public_key is None:
            public_key = self.public_key()
            if public_key is None:
                logger.debug("No public key available for encryption.")
                return None

        # 3. Generate ephemeral EC private key
        ephemeral_private_key = ec.generate_private_key(ec.SECP256R1())

        # 4. Derive shared secret
        shared_secret = ephemeral_private_key.exchange(ec.ECDH(), public_key)

        # 5. Derive symmetric AES key using HKDF
        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,  # Allow salt=None if not provided
            info=b"ecies-encryption",
            backend=default_backend(),
        ).derive(shared_secret)

        # 6. Encrypt the message using AES-GCM
        iv = os.urandom(12)  # 96-bit random IV for GCM
        encryptor = Cipher(
            algorithms.AES(derived_key),
            modes.GCM(iv),
            backend=default_backend(),
        ).encryptor()

        ciphertext = encryptor.update(message) + encryptor.finalize()
        tag = encryptor.tag

        # 7. Serialize ephemeral public key as X9.62 Uncompressed Point
        ephemeral_public_key_bytes = (
            ephemeral_private_key.public_key().public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint,
            )
        )

        # 8. Combine everything cleanly
        full_payload = {
            "ephemeral_pubkey": base64_urlencode(ephemeral_public_key_bytes),
            "iv": base64_urlencode(iv),
            "tag": base64_urlencode(tag),
            "ciphertext": base64_urlencode(ciphertext),
        }

        return base64.b64encode(
            json.dumps(full_payload).encode("utf-8")
        ).decode("utf-8")

    def decrypt(
        self,
        encrypted_payload: Union[str, bytes],
        private_key: "Optional[ec.EllipticCurvePrivateKey]" = None,
        salt: Optional[bytes] = None,
    ) -> Optional[str]:
        """Decrypts a message using the provided private key or fallback to
        self's private key.

        Payload is the base64-encoded JSON from encrypt().
        """

        if not PEM_SUPPORT:
            msg = "PEM Support unavailable; install cryptography library"
            logger.warning(msg)
            raise ApprisePEMException(msg)

        # 1. Parse input
        try:
            if isinstance(encrypted_payload, str):
                payload_bytes = base64.b64decode(
                    encrypted_payload.encode("utf-8")
                )

            else:
                payload_bytes = base64.b64decode(encrypted_payload)

        except binascii.Error:
            # Bad Padding
            logger.debug("Unparseable encrypted content provided")
            return None

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))

        except UnicodeDecodeError:
            logger.debug("Unparseable encrypted content provided")
            return None

        ephemeral_pubkey_bytes = base64_urldecode(payload["ephemeral_pubkey"])
        iv = base64_urldecode(payload["iv"])
        tag = base64_urldecode(payload["tag"])
        ciphertext = base64_urldecode(payload["ciphertext"])

        # 2. Select private key
        if private_key is None:
            private_key = self.private_key()
            if private_key is None:
                logger.debug("No private key available for decryption.")
                return None

        # 3. Load ephemeral public key from sender
        ephemeral_pubkey = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), ephemeral_pubkey_bytes
        )

        # 4. ECDH shared secret
        shared_secret = private_key.exchange(ec.ECDH(), ephemeral_pubkey)

        # 5. Derive symmetric AES key with HKDF
        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"ecies-encryption",
        ).derive(shared_secret)

        # 6. Decrypt using AES-GCM
        decryptor = Cipher(
            algorithms.AES(derived_key),
            modes.GCM(iv, tag),
        ).decryptor()

        try:
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        except InvalidTag:
            logger.debug("Decryption failed - Authentication Mismatch")
            # Reason for Error:
            #   - Mismatched or missing salt
            #   - Mismatched iv, tag, or ciphertext
            #   - Incorrect or corrupted ephemeral_pubkey
            #   - Wrong or incomplete key derivation
            #   - Data being altered between encryption and decryption
            #     (truncated/corrupted)

            # Basically if we get here, we tried to decrypt encrypted content
            # using the wrong key.
            return None

        # 7. Return decoded message
        return plaintext.decode("utf-8")

    def sign(self, content: bytes) -> Optional[bytes]:
        """Sign the message using ES256 (ECDSA w/ SHA256) via private key."""

        try:
            # Sign the message using ES256 (ECDSA w/ SHA256)
            der_sig = self.private_key().sign(
                content, ec.ECDSA(hashes.SHA256())
            )

        except AttributeError:
            # NoneType; could not load key
            return None

        # Convert DER to raw R||S
        r, s = decode_dss_signature(der_sig)
        return r.to_bytes(32, byteorder="big") + s.to_bytes(
            32, byteorder="big"
        )

    @property
    def pub_keyfile(self) -> Optional[Union[str, bool]]:
        """Returns the Public Keyfile Path if set otherwise it returns None
        This property returns False if a keyfile was provided, but was
        invalid."""
        return (
            None
            if not self._pub_keyfile
            else (
                False
                if not self._pub_keyfile[0]
                else self._pub_keyfile[0].path
            )
        )

    @property
    def prv_keyfile(self) -> Optional[Union[str, bool]]:
        """Returns the Private Keyfile Path if set otherwise it returns None
        This property returns False if a keyfile was provided, but was
        invalid."""
        return (
            None
            if not self._prv_keyfile
            else (
                False
                if not self._prv_keyfile[0]
                else self._prv_keyfile[0].path
            )
        )

    @property
    def x962_str(self) -> str:
        """X962 serialization based on public key."""
        try:
            return base64_urlencode(
                self.public_key().public_bytes(
                    encoding=serialization.Encoding.X962,
                    format=serialization.PublicFormat.UncompressedPoint,
                )
            )
        except AttributeError:
            # Public Key could not be generated (public_key() returned None)
            return ""

    def __bool__(self) -> bool:
        """Returns True if at least 1 key was loaded."""
        return bool(self.private_key() or self.public_key())
