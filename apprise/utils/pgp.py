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

from datetime import datetime, timedelta, timezone
import hashlib
import os

from ..apprise_attachment import AppriseAttachment
from ..asset import AppriseAsset
from ..exception import ApprisePluginException
from ..logger import logger


def _ensure_imghdr_shim():
    """Install a minimal imghdr shim when the module is absent.

    pgpy 0.6.0 imports imghdr, which was removed from the standard
    library in Python 3.13 (PEP 594). pgpy's only use of imghdr is
    ImageEncoding.encodingof(), which Apprise never calls. Returning
    None from what() is the same safe fallback the library uses
    internally for non-JPEG data.
    """
    try:
        import imghdr  # noqa: F401
    except ImportError:
        import sys
        import types

        # Build a minimal stand-in with the single function pgpy calls
        shim = types.ModuleType("imghdr")
        shim.what = lambda file=None, h=None: None
        sys.modules["imghdr"] = shim


# Install shim before pgpy attempts its top-level import of imghdr
_ensure_imghdr_shim()

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

    # Private keys can be materially larger than public keys, especially for
    # 4096-bit RSA or keys carrying multiple subkeys and UIDs; 32K is
    # generous enough to accommodate all realistic cases without being
    # unbounded.
    max_pgp_private_key_size = 32000

    def __init__(
        self,
        path,
        pub_keyfile=None,
        prv_keyfile=None,
        email=None,
        asset=None,
        wkd=None,
        **kwargs,
    ):
        """Path should be the directory keys can be written and read from such
        as <notifyobject>.store.path.

        Optionally additionally specify a pub_keyfile and/or prv_keyfile to
        use explicit key files, and/or an AppriseWKDController to enable Web
        Key Directory key discovery when no local key is found.
        """

        # PGP hash
        self.__key_lookup = {}

        # Directory we can work with
        self.path = path

        # Our email
        self.email = email

        # Optional WKD controller for automatic key discovery
        self.wkd = wkd

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

        if prv_keyfile:
            # Create an Attachment for the private key as well so that remote
            # paths and other Apprise-supported sources are supported
            self._prv_keyfile = AppriseAttachment(asset=self.asset)

            # Add our definition to our pgp_key reference
            self._prv_keyfile.add(prv_keyfile)

            # Enforce a private-key-specific size limit; private keys can be
            # larger than public keys (4096-bit RSA, multiple subkeys/UIDs)
            self._prv_keyfile[0].max_file_size = self.max_pgp_private_key_size

        else:
            self._prv_keyfile = None

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

    def _pub_key_candidates(self, *emails):
        """Returns the ordered list of candidate public-key filenames to
        search, highest priority first.

        Shared by public_keyfile() and the diagnostic warning in public_key()
        so both always reflect exactly the same search order.
        """

        # Base candidates, lowest priority first
        fnames = [
            "pgp-public.asc",
            "pgp-pub.asc",
            "public.asc",
            "pub.asc",
        ]

        # Merge the controller's own email with any caller-supplied addresses.
        # Two filenames are prepended per address: localpart shorthand is
        # inserted at index 0 first, then the full address is also inserted
        # at index 0 -- so the full address lands ahead of the localpart in
        # the list (full address has higher priority as it is more specific).
        all_emails = [self.email, *emails] if self.email else list(emails)
        for em in all_emails:
            # Localpart shorthand (e.g. "chris-pub.asc")
            fnames.insert(0, f"{em.split('@')[0].lower()}-pub.asc")
            # Full lowercase email (e.g. "chris@nuxref.com-pub.asc")
            fnames.insert(0, f"{em.lower()}-pub.asc")

        return fnames

    def _prv_key_candidates(self):
        """Returns the ordered list of candidate private-key filenames to
        search, highest priority first.

        Shared by private_keyfile() and the diagnostic warning in private_key()
        so both always reflect exactly the same search order.
        """

        # Base candidates, lowest priority first
        fnames = [
            "pgp-private.asc",
            "pgp-prv.asc",
            "private.asc",
            "prv.asc",
        ]

        # Prefer keys named after the sender's email address when known
        if self.email:
            # Localpart shorthand (e.g. "chris-prv.asc")
            fnames.insert(0, f"{self.email.split('@')[0].lower()}-prv.asc")
            # Full lowercase email (e.g. "chris@nuxref.com-prv.asc")
            fnames.insert(0, f"{self.email.lower()}-prv.asc")

        return fnames

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

        # Use shared candidate list so the search order is always consistent
        # with any diagnostic messages that reference the same list
        fnames = self._pub_key_candidates(*emails)

        return next(
            (
                os.path.join(self.path, fname)
                for fname in fnames
                if os.path.isfile(os.path.join(self.path, fname))
            ),
            None,
        )

    def private_keyfile(self):
        """Returns the path to the private key file if one can be found.

        Returns the explicit path when prv_keyfile was provided, looks for a
        matching auto-generated key in self.path otherwise.  Returns False
        when an explicit keyfile was given but could not be accessed, and
        None when no key file could be located at all.
        """

        if self._prv_keyfile is not None:
            # Use the explicitly-provided private key attachment
            pgp_key = self._prv_keyfile[0]
            if not pgp_key:
                # We could not access the attachment
                logger.error(
                    "Could not access PGP Private Key"
                    f" {pgp_key.url(privacy=True)}."
                )
                return False

            return pgp_key.path

        elif not self.path:
            # No storage path; cannot search for auto-generated keys
            return None

        # Use shared candidate list so the search order is always consistent
        # with any diagnostic messages that reference the same list
        fnames = self._prv_key_candidates()

        return next(
            (
                os.path.join(self.path, fname)
                for fname in fnames
                if os.path.isfile(os.path.join(self.path, fname))
            ),
            None,
        )

    def private_key(self):
        """Loads and returns the PGP private key object.

        Reads from the explicit prv_keyfile if one was provided, otherwise
        scans the persistent storage path for an auto-generated private key.
        Returns None when no usable private key could be found or loaded.
        Passphrase-protected keys are not supported and will be rejected.
        """

        # Locate the private key file
        path = self.private_keyfile()
        if not path:
            if path is False:
                # An explicit pgpprv= file was given but could not be accessed;
                # keep as WARNING because the user made an explicit choice that
                # failed -- this is always actionable regardless of plugin
                logger.warning("PGP Private Key could not be accessed")

            elif self.path:
                # path is None: storage was searched but nothing matched.
                # Only hash + filename is shown -- never an absolute path.
                ns = os.path.basename(self.path)
                candidates = self._prv_key_candidates()
                shown = ", ".join(f"'{ns}/{fn}'" for fn in candidates[:4])
                extra = ", ..." if len(candidates) > 4 else ""
                logger.debug(
                    "No PGP private key found; searched: %s%s",
                    shown,
                    extra,
                )

            else:
                # No storage path at all -- nothing was searched
                logger.debug("No PGP private key found")

            return None

        # Build a cache key distinct from public-key entries for the same path
        cache_key = hashlib.sha1(
            ("prv:" + os.path.abspath(path)).encode("utf-8")
        ).hexdigest()

        # Return the cached key when it is still valid
        if cache_key in self.__key_lookup:
            entry = self.__key_lookup[cache_key]
            if entry["expires"] > datetime.now(timezone.utc):
                return entry["private_key"]

            # Expired -- remove and re-load below
            del self.__key_lookup[cache_key]

        try:
            with open(path) as key_file:
                private_key, _ = pgpy.PGPKey.from_blob(key_file.read())

        except NameError:
            # PGPy not installed
            logger.debug("PGPy not installed; skipping PGP signing: %s", path)
            return None

        except FileNotFoundError:
            # File was found but disappeared before we could open it
            logger.debug("PGP Private Key file not found: %s", path)
            return None

        except OSError as e:
            logger.warning("Error accessing PGP Private Key file %s", path)
            logger.debug(f"I/O Exception: {e}")
            return None

        except Exception:
            # Malformed or non-PGP file content
            logger.warning(
                "PGP Private Key file could not be parsed: %s", path
            )
            return None

        if private_key.is_protected:
            # Apprise does not support passphrase-protected private keys
            # because it runs unattended; a protected key would block sending
            logger.warning(
                "PGP Private Key is passphrase-protected; "
                "Apprise does not support passphrase-protected keys"
            )
            return None

        # Cache the successfully loaded key
        self.__key_lookup[cache_key] = {
            "private_key": private_key,
            "expires": datetime.now(timezone.utc) + timedelta(seconds=86400),
        }

        return private_key

    def sign(self, message):
        """Creates a detached PGP signature for the given message string.

        Returns a (signature_str, micalg) tuple on success where
        signature_str is the armored PGP signature block and micalg is the
        MIME hash algorithm label (e.g. 'pgp-sha256') for the
        Content-Type header of the multipart/signed container.
        Returns None when signing is not possible.
        """

        # Load our private key
        private_key = self.private_key()
        if not private_key:
            logger.debug("PGP signing skipped: no usable private key")
            return None

        try:
            # Create a detached signature over the message text
            sig = private_key.sign(message)

            # Map the hash algorithm to the MIME micalg label
            micalg = "pgp-" + sig.hash_algorithm.name.lower()

            return (str(sig), micalg)

        except NameError:
            # PGPy not installed; must come before pgpy.errors.PGPError so
            # that evaluating that except clause doesn't itself raise NameError
            logger.debug("PGPy not installed; skipping PGP signing")

        except pgpy.errors.PGPError:
            # Key may lack the Sign capability or be otherwise incompatible
            logger.debug("PGP signing failed; key may lack Sign capability")

        return None

    def _fetch_wkd_key(self, *emails):
        """Attempt a Web Key Directory lookup for each email in turn.

        Returns a pgpy.PGPKey on the first successful fetch, or None if
        WKD is not configured, no emails are provided, or all lookups
        fail.
        """

        if self.wkd is None:
            # No WKD controller configured
            return None

        # Use only the supplied recipient emails when provided. Fall back
        # to self.email only when no recipient emails were supplied
        # (for example, an explicit self-send). Otherwise a missed
        # recipient WKD lookup could incorrectly encrypt to the sender's
        # key, leaving the intended recipient unable to decrypt.
        candidates = (
            list(emails) if emails else ([self.email] if self.email else [])
        )

        for email in candidates:
            if not email:
                continue

            # Derive a stable cache key from the email address
            cache_key = hashlib.sha1(
                ("wkd:" + email.lower()).encode("utf-8")
            ).hexdigest()

            # Return the previously parsed key when still valid
            if cache_key in self.__key_lookup:
                entry = self.__key_lookup[cache_key]
                if entry["expires"] > datetime.now(timezone.utc):
                    return entry["public_key"]
                # Expired; remove so we re-fetch below
                del self.__key_lookup[cache_key]

            # Fetch raw binary key material from WKD
            key_bytes = self.wkd.fetch(email)
            if not key_bytes:
                continue

            try:
                public_key, _ = pgpy.PGPKey.from_blob(key_bytes)

            except NameError:
                # pgpy not installed
                logger.debug(
                    "PGPy not installed; skipping WKD key for %s",
                    email,
                )
                continue

            except Exception:
                # Malformed or unsupported key data from WKD
                logger.debug("WKD key parse failed for %s; skipping", email)
                continue

            # Cache the successfully parsed key
            self.__key_lookup[cache_key] = {
                "public_key": public_key,
                "expires": datetime.now(timezone.utc)
                + timedelta(seconds=86400),
            }

            logger.debug("Loaded PGP public key via WKD for %s", email)
            return public_key

        return None

    def public_key(self, *emails, autogen=None):
        """Opens a spcified pgp public file and returns the key from it which
        is used to encrypt the message."""
        path = self.public_keyfile(*emails)
        if not path:
            # Try Web Key Directory before falling back to autogen
            wkd_key = self._fetch_wkd_key(*emails)
            if wkd_key is not None:
                return wkd_key

            if (
                autogen if autogen is not None else self.asset.pgp_autogen
            ) and self.keygen(*emails):
                path = self.public_keyfile(*emails)
                if path:
                    # We should get a hit now
                    return self.public_key(*emails)

            # All discovery methods exhausted (local file, WKD, autogen).
            # Log at DEBUG so the caller's warning (with plugin-specific hints)
            # is the only user-visible message.  Only the namespace hash +
            # filename is shown -- never an absolute path -- so no sensitive
            # filesystem layout is revealed.
            if self.path:
                ns = os.path.basename(self.path)
                candidates = self._pub_key_candidates(*emails)
                shown = ", ".join(f"'{ns}/{fn}'" for fn in candidates[:4])
                extra = ", ..." if len(candidates) > 4 else ""
                logger.debug(
                    "No PGP public key found; searched: %s%s",
                    shown,
                    extra,
                )
            else:
                logger.debug("No PGP public key found")

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

        except Exception:
            # Malformed or non-PGP file content (e.g. pgpy.errors.PGPError)
            logger.warning("PGP Public Key file could not be parsed: %s", path)
            return None

        self.__key_lookup[key] = {
            "public_key": public_key,
            "expires": datetime.now(timezone.utc) + timedelta(seconds=86400),
        }
        return public_key

    # Encrypt message using the recipient's public key
    def encrypt(self, message, *emails, autogen=None):
        """If provided a path to a pgp-key, content is encrypted.

        Pass autogen=False to suppress key auto-generation during the
        public-key lookup.  This is used in sign mode for opportunistic
        encryption: only encrypt when a pre-existing key is found.
        """

        # Acquire our key; autogen controls whether a missing key is created
        public_key = self.public_key(*emails, autogen=autogen)
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

        # Also prune the WKD in-memory cache when a controller is set
        if self.wkd is not None:
            self.wkd.prune()

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

    @property
    def prv_keyfile(self):
        """Returns the Private Keyfile Path if set, otherwise returns None.
        Returns False when an explicit keyfile was provided but could not
        be accessed."""
        return (
            None
            if self._prv_keyfile is None
            else (
                False
                if not self._prv_keyfile[0]
                else self._prv_keyfile[0].path
            )
        )
