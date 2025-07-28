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

from datetime import datetime, timedelta, timezone
import hashlib
import os

from ..apprise_attachment import AppriseAttachment
from ..asset import AppriseAsset
from ..exception import ApprisePluginException
from ..logger import logger

try:
    import pgpy

    # Pretty Good Privacy (PGP) Support enabled
    PGP_SUPPORT = True

except ImportError:
    # Pretty Good Privacy (PGP) Support disabled
    PGP_SUPPORT = False


class ApprisePGPException(ApprisePluginException):
    """Thrown when there is an error with the Pretty Good Privacy
    Controller."""

    def __init__(self, message, error_code=602):
        super().__init__(message, error_code=error_code)


class ApprisePGPController:
    """Pretty Good Privacy Controller Tool for the Apprise Library."""

    # There is no reason a PGP Public Key should exceed 8K in size
    # If it is more than this, then it is not accepted
    max_pgp_public_key_size = 8000

    def __init__(
        self, path, pub_keyfile=None, email=None, asset=None, **kwargs
    ):
        """Path should be the directory keys can be written and read from such
        as <notifyobject>.store.path.

        Optionally additionally specify a keyfile to explicitly open
        """

        # PGP hash
        self.__key_lookup = {}

        # Directory we can work with
        self.path = path

        # Our email
        self.email = email

        # Prepare our Asset Object
        self.asset = (
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()
        )

        if pub_keyfile:
            # Create ourselves an Attachment to work with; this grants us the
            # ability to pull this key from a remote site or anything else
            # supported by the Attachment object
            self._pub_keyfile = AppriseAttachment(asset=self.asset)

            # Add our definition to our pgp_key reference
            self._pub_keyfile.add(pub_keyfile)

            # Enforce maximum file size
            self._pub_keyfile[0].max_file_size = self.max_pgp_public_key_size

        else:
            self._pub_keyfile = None

    def keygen(self, email=None, name=None, force=False):
        """Generates a set of keys based on email configured."""

        try:
            # Create a new RSA key pair with 2048-bit strength
            key = pgpy.PGPKey.new(
                pgpy.constants.PubKeyAlgorithm.RSAEncryptOrSign, 2048
            )

        except NameError:
            # PGPy not installed
            logger.debug("PGPy not installed; keygen disabled")
            return False

        if self._pub_keyfile is not None or not self.path:
            logger.trace(
                "PGP keygen disabled, reason=%s",
                (
                    "keyfile-defined"
                    if self._pub_keyfile is not None
                    else "no-write-path"
                ),
            )
            return False

        if not name:
            name = self.asset.app_id

        if not email:
            email = self.email

        # Prepare our UID
        uid = pgpy.PGPUID.new(name, email=email)

        # Filenames
        file_prefix = email.split("@")[0].lower()

        pub_path = os.path.join(self.path, f"{file_prefix}-pub.asc")
        prv_path = os.path.join(self.path, f"{file_prefix}-prv.asc")

        if os.path.isfile(pub_path) and not force:
            logger.debug(
                "PGP generation skipped; Public Key already exists: %s",
                pub_path,
            )
            return True

        # Persistent Storage Key
        lookup_key = hashlib.sha1(
            os.path.abspath(pub_path).encode("utf-8")
        ).hexdigest()
        if lookup_key in self.__key_lookup:
            # Ensure our key no longer exists
            del self.__key_lookup[lookup_key]

        # Add the user ID to the key
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

        try:
            # Write our keys to disk
            with open(pub_path, "w") as f:
                f.write(str(key.pubkey))

        except OSError as e:
            logger.warning("Error writing PGP file %s", pub_path)
            logger.debug(f"I/O Exception: {e}")

            # Cleanup
            try:
                os.unlink(pub_path)
                logger.trace("Removed %s", pub_path)

            except OSError:
                pass

        try:
            with open(prv_path, "w") as f:
                f.write(str(key))

        except OSError as e:
            logger.warning("Error writing PGP file %s", prv_path)
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

        logger.info(
            "Wrote PGP Keys for %s/%s",
            os.path.dirname(pub_path),
            os.path.basename(pub_path),
        )
        return True

    def public_keyfile(self, *emails):
        """Returns the first match of a useable public key based emails
        provided."""

        if not PGP_SUPPORT:
            msg = "PGP Support unavailable; install PGPy library"
            logger.warning(msg)
            raise ApprisePGPException(msg)

        if self._pub_keyfile is not None:
            # If our code reaches here, then we fetch our public key
            pgp_key = self._pub_keyfile[0]
            if not pgp_key:
                # We could not access the attachment
                logger.error(
                    "Could not access PGP Public Key"
                    f" {pgp_key.url(privacy=True)}."
                )
                return False

            return pgp_key.path

        elif not self.path:
            # No path
            return None

        fnames = [
            "pgp-public.asc",
            "pgp-pub.asc",
            "public.asc",
            "pub.asc",
        ]

        if self.email:
            # Include our email in the list
            emails = [self.email, *emails]

        for email in emails:
            _entry = email.split("@")[0].lower()
            fnames.insert(0, f"{_entry}-pub.asc")

            # Lowercase email (Highest Priority)
            _entry = email.lower()
            fnames.insert(0, f"{_entry}-pub.asc")

        return next(
            (
                os.path.join(self.path, fname)
                for fname in fnames
                if os.path.isfile(os.path.join(self.path, fname))
            ),
            None,
        )

    def public_key(self, *emails, autogen=None):
        """Opens a spcified pgp public file and returns the key from it which
        is used to encrypt the message."""
        path = self.public_keyfile(*emails)
        if not path:
            if (
                autogen if autogen is not None else self.asset.pgp_autogen
            ) and self.keygen(*emails):
                path = self.public_keyfile(*emails)
                if path:
                    # We should get a hit now
                    return self.public_key(*emails)

            logger.warning("No PGP Public Key could be loaded")
            return None

        # Persistent Storage Key
        key = hashlib.sha1(os.path.abspath(path).encode("utf-8")).hexdigest()
        if key in self.__key_lookup:
            # Take an early exit
            return self.__key_lookup[key]["public_key"]

        try:
            with open(path) as key_file:
                public_key, _ = pgpy.PGPKey.from_blob(key_file.read())

        except NameError:
            # PGPy not installed
            logger.debug("PGPy not installed; skipping PGP support: %s", path)
            return None

        except FileNotFoundError:
            # Generate keys
            logger.debug("PGP Public Key file not found: %s", path)
            return None

        except OSError as e:
            logger.warning("Error accessing PGP Public Key file %s", path)
            logger.debug(f"I/O Exception: {e}")
            return None

        self.__key_lookup[key] = {
            "public_key": public_key,
            "expires": datetime.now(timezone.utc) + timedelta(seconds=86400),
        }
        return public_key

    # Encrypt message using the recipient's public key
    def encrypt(self, message, *emails):
        """If provided a path to a pgp-key, content is encrypted."""

        # Acquire our key
        public_key = self.public_key(*emails)
        if not public_key:
            # Encryption not possible
            return False

        try:
            message_object = pgpy.PGPMessage.new(message)
            encrypted_message = public_key.encrypt(message_object)
            return str(encrypted_message)

        except pgpy.errors.PGPError:
            # Encryption not Possible
            logger.debug("PGP Public Key Corruption; encryption not possible")

        except NameError:
            # PGPy not installed
            logger.debug("PGPy not installed; Skipping PGP encryption")

        return None

    def prune(self):
        """Prunes old entries from the public_key index."""
        self.__key_lookup = {
            key: value
            for key, value in self.__key_lookup.items()
            if value["expires"] > datetime.now(timezone.utc)
        }

    @property
    def pub_keyfile(self):
        """Returns the Public Keyfile Path if set otherwise it returns None
        This property returns False if a keyfile was provided, but was
        invalid."""
        return (
            None
            if self._pub_keyfile is None
            else (
                False
                if not self._pub_keyfile[0]
                else self._pub_keyfile[0].path
            )
        )
