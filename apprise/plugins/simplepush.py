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

# To use this plugin, you need a Simplepush account and the app installed
# on your phone. Your API Token is in the app settings under **API Token**.
# An organization sends with an integration token (spi_...) instead, created
# by an admin with `sp integration create --scopes send`.
#
# Every message is sent as a task, so it stays in the app after the push.
#
# API reference: https://simplepu.sh/guide/curl
#
# Syntax:
#   spush://{api_token}                    - your own devices
#   spush://{api_token}/{topic}            - everyone holding the topic
#   spush://{password}@{api_token}/{topic} - encrypted with the topic password
#   spush://{integration_token}/@{member}  - an organization member
#   spush://{integration_token}/?broadcast=yes - every organization member
#
# Organization sends are encrypted automatically when the organization has
# encryption turned on; the integration token opens the organization keys.
#
# Optional arguments: priority (1 to 5), critical_volume (iOS only, the
# critical alert sound volume, priority 5 only), sptag (the Simplepush tag),
# links, shared, topic_auth_token

import base64
import hashlib
import hmac
from json import dumps, loads
import re

import requests

from .. import exception
from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_bool, parse_list, validate_regex
from .base import NotifyBase

try:
    import nacl.bindings as sodium
    from nacl.exceptions import CryptoError

    # End-to-end encryption is available
    NOTIFY_SIMPLEPUSH_ENCRYPTION = True

except ImportError:
    # PyNaCl is only required for encrypted sends
    NOTIFY_SIMPLEPUSH_ENCRYPTION = False


# Organization integration tokens are spi_<credential>.<seed>
SIMPLEPUSH_INTEGRATION_PREFIX = "spi_"


# Priority levels 1 (silent) to 5 (critical); the server default is 3
SIMPLEPUSH_PRIORITIES = (1, 2, 3, 4, 5)

SIMPLEPUSH_PRIORITY_MAP = {
    # Maps against string 'minimal'
    "mi": 1,
    # Maps against string 'low'
    "l": 2,
    # Maps against string 'default'
    "d": 3,
    # Maps against string 'normal'
    "n": 3,
    # Maps against string 'high'
    "h": 4,
    # Maps against string 'critical'
    "c": 5,
    # Maps against string 'emergency'
    "e": 5,
    # Maps against string 'max'
    "ma": 5,
}


class NotifySimplePush(NotifyBase):
    """A wrapper for Simplepush; every message is sent as a task."""

    requirements = {
        # Only needed for encrypted sends
        "packages_recommended": "PyNaCl"
    }

    # The default descriptive name associated with the Notification
    service_name = "Simplepush"

    # The services URL
    service_url = "https://simplepu.sh/"

    # The default secure protocol; simplepush:// is also accepted
    secure_protocol = ("spush", "simplepush")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/simplepush/"

    # Task endpoint (JSON body)
    notify_url = "https://api.simplepu.sh/v1/tasks/json"

    # Attachment lifecycle: {id}/upload-url, {id}/complete, {id}/failed
    attachment_url = "https://api.simplepu.sh/v1/attachments/{id}/{step}"

    # Account endpoint; returns the salt of the Personal Password
    user_url = "https://api.simplepu.sh/v1/user"

    # Integration endpoint; returns the scopes and wrapped organization keys
    integration_keys_url = "https://api.simplepu.sh/v1/org/integration/keys"

    # Task content can be rendered as Markdown
    notify_format = NotifyFormat.MARKDOWN

    # Support attachments
    attachment_support = True

    # The server accepts at most 25 links per task
    links_max = 25

    # The server accepts 10000 content and 500 title characters. Encryption
    # grows a field to base64(24 byte nonce + UTF-8 text + 16 byte tag), so
    # these limits leave room for the ciphertext of ASCII text. Text with
    # multi-byte characters grows further and is checked once encrypted.
    body_maxlen = 7000
    title_maxlen = 300

    # The server limits, which apply to the ciphertext of an encrypted field
    encrypted_maxlen = {
        "title": 500,
        "content": 10000,
    }

    # Define object templates
    templates = (
        "{schema}://{token}",
        "{schema}://{token}/{targets}",
        "{schema}://{password}@{token}",
        "{schema}://{password}@{token}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("API Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
            },
            "target_topic": {
                "name": _("Target Topic"),
                "type": "string",
                "map_to": "targets",
            },
            "target_member": {
                "name": _("Target Member"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "broadcast": {
                "name": _("Broadcast"),
                "type": "bool",
                "default": False,
            },
            "shared": {
                "name": _("Shared"),
                "type": "bool",
                "default": False,
            },
            "priority": {
                "name": _("Priority"),
                "type": "choice:int",
                "values": SIMPLEPUSH_PRIORITIES,
            },
            "critical_volume": {
                "name": _("Volume"),
                "type": "float",
                "min": 0,
                "max": 1,
            },
            "sptag": {
                "name": _("Tag"),
                "type": "string",
            },
            "links": {
                "name": _("Link"),
                "type": "list:string",
            },
            "topic_auth_token": {
                "name": _("Auth Token"),
                "type": "string",
                "private": True,
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self,
        token,
        targets=None,
        broadcast=None,
        shared=None,
        priority=None,
        critical_volume=None,
        sptag=None,
        links=None,
        topic_auth_token=None,
        **kwargs,
    ):
        """Initialize Simplepush Object."""
        super().__init__(**kwargs)

        # API Token (personal) or organization integration token
        self.token = validate_regex(token)
        if not self.token:
            msg = f"An invalid Simplepush API Token ({token}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # An integration token authenticates with its credential half; its
        # seed half never leaves this process and opens the organization keys
        self.integration = self.token.startswith(SIMPLEPUSH_INTEGRATION_PREFIX)
        self._credential = self.token
        self._seed = None
        if self.integration:
            self._credential, _, seed = self.token.partition(".")
            try:
                self._seed = base64.urlsafe_b64decode(
                    seed + "=" * (-len(seed) % 4)
                )

            except ValueError:
                self._seed = None

            if (
                self._credential == SIMPLEPUSH_INTEGRATION_PREFIX
                or not self._seed
                or len(self._seed) != 32
            ):
                msg = (
                    "An invalid Simplepush integration token was specified; "
                    "it looks like spi_<credential>.<seed>."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        self.broadcast = parse_bool(
            broadcast, self.template_args["broadcast"]["default"]
        )
        self.shared = parse_bool(
            shared, self.template_args["shared"]["default"]
        )

        # Topics and organization members
        self.topics = []
        self.members = []
        for target in parse_list(targets, allow_whitespace=False, sort=False):
            if not target.startswith("@"):
                self.topics.append(target)
                continue

            member = target[1:].strip()
            if not member:
                msg = f"An invalid Simplepush member ({target}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            self.members.append(member)

        if not self.integration:
            if self.members or self.broadcast:
                msg = (
                    "Simplepush members and broadcast require an "
                    "organization integration token (spi_...)."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        else:
            if self.broadcast and (self.topics or self.members):
                msg = (
                    "A Simplepush broadcast can not be combined with "
                    "topics or members."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            if not (self.broadcast or self.topics or self.members):
                msg = (
                    "A Simplepush organization send requires a topic, "
                    "a member or broadcast."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            if self.password:
                # Organization sends are encrypted with the organization key
                msg = (
                    "Simplepush organization sends can not be encrypted "
                    "with a password; they use the organization key."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        if self.password and not NOTIFY_SIMPLEPUSH_ENCRYPTION:
            msg = "Encrypted Simplepush sends require PyNaCl to be installed."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        self.priority = None
        if priority is not None and str(priority).strip():
            value = str(priority).strip().lower()
            if value in [str(p) for p in SIMPLEPUSH_PRIORITIES]:
                self.priority = int(value)

            elif not value[0].isdigit():
                self.priority = next(
                    (
                        v
                        for k, v in SIMPLEPUSH_PRIORITY_MAP.items()
                        if value.startswith(k)
                    ),
                    None,
                )

            if self.priority is None:
                msg = (
                    f"An invalid Simplepush priority ({priority}) was "
                    "specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # Volume of the iOS critical alert sound; Android ignores it
        self.critical_volume = None
        if critical_volume is not None and str(critical_volume).strip():
            try:
                self.critical_volume = float(critical_volume)

            except (TypeError, ValueError):
                self.critical_volume = None

            if self.critical_volume is None or not (
                0 < self.critical_volume <= 1
            ):
                msg = (
                    "An invalid Simplepush critical volume "
                    f"({critical_volume}) was specified; it must be greater "
                    "than 0 and at most 1."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            if self.priority != 5:
                msg = "The Simplepush critical volume requires priority 5."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        self.sptag = (
            sptag.strip() if isinstance(sptag, str) and sptag.strip() else None
        )
        # Links are separated by whitespace; a URL never contains any
        self.links = [
            link
            for link in (
                re.split(r"\s+", links)
                if isinstance(links, str)
                else list(links or [])
            )
            if link
        ]
        if len(self.links) > self.links_max:
            msg = (
                f"At most {self.links_max} Simplepush links can be specified."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)
        self.topic_auth_token = (
            topic_auth_token.strip()
            if isinstance(topic_auth_token, str) and topic_auth_token.strip()
            else None
        )

        # Derived keys, cached per salt (Argon2id is deliberately slow)
        self._keys = {}

        # The account password salt, fetched on the first encrypted send to
        # your own devices
        self._account_salt = None

        # Organization key per version, fetched on the first send with an
        # integration token; empty when the organization has no encryption
        self._org_keys = None

    def _auth_headers(self):
        """The sender credential."""
        if self.integration:
            return {"Authorization": f"Bearer {self._credential}"}
        return {"API-Token": self._credential}

    def _derive_key(self, salt):
        """Derives the (key, fingerprint) for the password and salt.

        The salt is the topic for topic sends and the account's password salt
        for sends to your own devices:

            sha256(salt)[:16] --Argon2id(password)--> master (64 bytes)
            HKDF-SHA256 expand(master, "symmetric-key") --> key (32 bytes)
            fingerprint = base64(sha256(key)[:8])
        """
        if salt in self._keys:
            return self._keys[salt]

        master = sodium.crypto_pwhash_alg(
            64,
            self.password.encode("utf-8"),
            hashlib.sha256(salt.encode("utf-8")).digest()[
                : sodium.crypto_pwhash_SALTBYTES
            ],
            3,
            64 * 1024 * 1024,
            sodium.crypto_pwhash_ALG_ARGON2ID13,
        )
        key = hmac.new(master, b"symmetric-key\x01", hashlib.sha256).digest()
        fingerprint = base64.b64encode(
            hashlib.sha256(key).digest()[:8]
        ).decode("ascii")

        self._keys[salt] = (key, fingerprint)
        return self._keys[salt]

    @staticmethod
    def _seal(data, key):
        """XChaCha20-Poly1305; 24 byte nonce + ciphertext + 16 byte tag."""
        nonce = sodium.randombytes(
            sodium.crypto_aead_xchacha20poly1305_ietf_NPUBBYTES
        )
        return nonce + sodium.crypto_aead_xchacha20poly1305_ietf_encrypt(
            data, None, nonce, key
        )

    @staticmethod
    def _encrypt(content, key):
        """Encrypts a text field; base64 of the sealed UTF-8 bytes."""
        return base64.b64encode(
            NotifySimplePush._seal(content.encode("utf-8"), key)
        ).decode("ascii")

    def _get_json(self, url, what):
        """GETs a JSON object with the sender credential, or None."""
        self.logger.debug(
            "Simplepush GET URL:"
            f" {url} (cert_verify={self.verify_certificate!r})"
        )

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.get(
                url,
                headers={
                    "User-Agent": self.app_id,
                    "Accept": "application/json",
                    **self._auth_headers(),
                },
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

        except requests.RequestException as e:
            self.logger.warning(
                f"A Connection error occurred fetching {what}."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return None

        if r.status_code != requests.codes.ok:
            self.logger.warning(
                "Failed to fetch {}: {}error={}.".format(
                    what, self._error_message(r), r.status_code
                )
            )
            return None

        try:
            response = loads(r.content)

        except (TypeError, ValueError, AttributeError):
            response = None

        if not isinstance(response, dict):
            self.logger.warning(f"Simplepush returned an unreadable {what}.")
            return None

        return response

    def _password_salt(self):
        """Fetches the salt of the Personal Password, or None on failure."""
        if self._account_salt:
            return self._account_salt

        response = self._get_json(
            self.user_url, "the Simplepush password salt"
        )
        if response is None:
            return None

        if not response.get("passwordSalt"):
            self.logger.warning("Simplepush returned no password salt.")
            return None

        self._account_salt = response["passwordSalt"]
        return self._account_salt

    def _org_key_set(self):
        """Opens the organization keys wrapped for the integration token.

        Returns {version: key}, empty when the organization has no
        encryption, or None on failure.
        """
        if self._org_keys is not None:
            return self._org_keys

        response = self._get_json(
            self.integration_keys_url, "the Simplepush integration keys"
        )
        if response is None:
            return None

        if "send" not in (response.get("scopes") or []):
            self.logger.warning(
                "The Simplepush integration token lacks the send scope."
            )
            return None

        keys = {}
        if response.get("enabled"):
            if not NOTIFY_SIMPLEPUSH_ENCRYPTION:
                self.logger.warning(
                    "The Simplepush organization has encryption turned on, "
                    "which requires PyNaCl to be installed."
                )
                return None

            if not response.get("wrappedKeys"):
                # Sending in the clear would leak into an encrypted
                # organization
                self.logger.warning(
                    "The Simplepush organization has encryption turned on "
                    "but holds no keys for this integration token; create "
                    "a new integration token."
                )
                return None

            # Every key is wrapped by the organization admin to this token:
            # base64(24 byte nonce + crypto_box ciphertext)
            try:
                admin_pubkey = base64.b64decode(response["adminPubkeyB64"])
                _, private_key = sodium.crypto_box_seed_keypair(self._seed)
                for wrap in response["wrappedKeys"]:
                    blob = base64.b64decode(wrap["blob"])
                    keys[int(wrap["version"])] = sodium.crypto_box_open(
                        blob[sodium.crypto_box_NONCEBYTES :],
                        blob[: sodium.crypto_box_NONCEBYTES],
                        admin_pubkey,
                        private_key,
                    )

            except (KeyError, TypeError, ValueError, CryptoError):
                self.logger.warning(
                    "Could not open the Simplepush organization keys with "
                    "this integration token."
                )
                return None

        self._org_keys = keys
        return keys

    def _encryption(self, kind, target):
        """The (key, marker) to encrypt a task with; (None, None) sends it
        in the clear and None means the key could not be obtained."""

        if self.integration:
            keys = self._org_key_set()
            if keys is None:
                return None

            if not keys:
                return (None, None)

            # New content is encrypted with the newest organization key
            version = max(keys)
            return (keys[version], {"type": "org", "v": version})

        if not self.password:
            return (None, None)

        # A topic send is encrypted with the topic password (salted with the
        # topic); a send to your own devices with your Personal Password
        # (salted with the account password salt)
        salt = target if kind == "topic" else self._password_salt()
        if salt is None:
            return None

        key, fingerprint = self._derive_key(salt)
        return (key, {"type": "personal", "keyFingerprint": fingerprint})

    @staticmethod
    def _error_message(r):
        """The server's error message followed by a separator, or ''."""
        try:
            msg = loads(r.content).get("msg")

        except (TypeError, ValueError, AttributeError):
            # TypeError = r.content is not a String
            # ValueError = r.content is Unparsable
            # AttributeError = r.content is None
            msg = None

        if not msg:
            msg = NotifyBase.http_response_code_lookup(r.status_code)

        return f"{msg}, " if msg else ""

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Simplepush Notification."""

        # (filename, content type, bytes) of every attachment
        files = []
        if attach and self.attachment_support:
            for attachment in attach:
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access Simplepush attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                try:
                    with attachment.open() as f:
                        files.append(
                            (
                                attachment.name
                                or f"file{len(files) + 1:03}.dat",
                                attachment.mimetype
                                or "application/octet-stream",
                                f.read(),
                            )
                        )

                except (TypeError, OSError, exception.AppriseException):
                    self.logger.error(
                        "Could not read Simplepush attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

        # One task per topic and member; a single task for a broadcast or a
        # send to your own devices
        targets = [("topic", t) for t in self.topics] + [
            ("member", m) for m in self.members
        ]
        if not targets:
            targets = [(None, None)]

        has_error = False
        for kind, target in targets:
            if self.is_delivered((kind, target)):
                continue

            payload = {}
            if kind:
                payload[kind] = target

            if self.broadcast:
                payload["broadcast"] = True

            if self.shared:
                payload["shared"] = True

            if self.topic_auth_token and kind == "topic":
                payload["topicAuthToken"] = self.topic_auth_token

            if self.priority is not None:
                payload["priority"] = self.priority

            if self.critical_volume is not None:
                payload["criticalVolume"] = self.critical_volume

            if body and self.notify_format == NotifyFormat.MARKDOWN:
                payload["contentFormat"] = "markdown"

            # The server requires content; a message without a body carries
            # its title there, or else the names of its attachments
            content = (
                body or title or ", ".join(name for (name, _, _) in files)
            )
            fields = {
                "title": (title if body else None) or None,
                "content": content or None,
                "tag": self.sptag,
            }
            links = list(self.links)
            blobs = [blob for (_, _, blob) in files]

            encryption = self._encryption(kind, target)
            if encryption is None:
                has_error = True
                continue

            key, marker = encryption
            if key:
                fields = {
                    k: self._encrypt(v, key) if v else None
                    for k, v in fields.items()
                }
                too_long = next(
                    (
                        k
                        for k, maxlen in self.encrypted_maxlen.items()
                        if fields[k] and len(fields[k]) > maxlen
                    ),
                    None,
                )
                if too_long:
                    self.logger.warning(
                        "The Simplepush {} is too long once encrypted; "
                        "{} characters exceed the limit of {}.".format(
                            too_long,
                            len(fields[too_long]),
                            self.encrypted_maxlen[too_long],
                        )
                    )
                    has_error = True
                    continue

                links = [self._encrypt(v, key) for v in links]
                blobs = [self._seal(blob, key) for blob in blobs]
                payload["encryption"] = marker

            payload.update({k: v for k, v in fields.items() if v})

            if links:
                payload["links"] = links

            if blobs:
                payload["files"] = [
                    {
                        "filename": filename,
                        "contentType": content_type,
                        "size": len(blob),
                        "checksumSha256": base64.b64encode(
                            hashlib.sha256(blob).digest()
                        ).decode("ascii"),
                    }
                    for (filename, content_type, _), blob in zip(files, blobs)
                ]

            response = self._send(payload, target)
            if response is None:
                has_error = True
                continue

            # The task exists; a retry must not create it a second time
            self.mark_delivered((kind, target))

            # Upload the attachments into the rows the task created
            created = response.get("attachments") or []
            for att, blob in zip(created, blobs):
                if not self._upload(att.get("id"), blob):
                    has_error = True

        return not has_error

    def _send(self, payload, target):
        """Creates one task; returns the parsed response or None."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            **self._auth_headers(),
        }

        self.logger.debug(
            "Simplepush POST URL:"
            f" {self.notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Simplepush Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code not in (
                requests.codes.ok,
                requests.codes.created,
            ):
                self.logger.warning(
                    "Failed to send Simplepush notification{}: "
                    "{}error={}.".format(
                        f" to {target}" if target else "",
                        self._error_message(r),
                        r.status_code,
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )
                return None

            self.logger.info(
                "Sent Simplepush notification{}.".format(
                    f" to {target}" if target else ""
                )
            )

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Simplepush notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return None

        try:
            response = loads(r.content)

        except (TypeError, ValueError, AttributeError):
            # TypeError = r.content is not a String
            # ValueError = r.content is Unparsable
            # AttributeError = r.content is None
            response = None

        return response if isinstance(response, dict) else {}

    def _upload(self, attachment_id, blob):
        """Uploads one attachment: presign, PUT the bytes, complete.

        A failed upload is reported to the server so the recipient sees it
        as failed instead of waiting for it.
        """
        if not attachment_id:
            return False

        headers = {"User-Agent": self.app_id, **self._auth_headers()}

        def step(name):
            url = self.attachment_url.format(id=attachment_id, step=name)
            self.logger.debug(
                "Simplepush POST URL:"
                f" {url} (cert_verify={self.verify_certificate!r})"
            )
            self.throttle()
            r = requests.post(
                url,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            if r.status_code not in (
                requests.codes.ok,
                requests.codes.created,
                requests.codes.no_content,
            ):
                raise requests.RequestException(
                    f"{name}: {self._error_message(r)}error={r.status_code}"
                )
            return r

        try:
            presigned = loads(step("upload-url").content)["presignedPutUrl"]

            self.throttle()
            r = requests.put(
                presigned,
                data=blob,
                headers={"Content-Type": "application/octet-stream"},
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            if r.status_code not in (
                requests.codes.ok,
                requests.codes.created,
                requests.codes.no_content,
            ):
                raise requests.RequestException(
                    f"upload: error={r.status_code}"
                )

            step("complete")

        except (
            requests.RequestException,
            TypeError,
            ValueError,
            KeyError,
        ) as e:
            self.logger.warning(
                "Failed to upload Simplepush attachment"
                f" {attachment_id}: {e!s}"
            )

            try:
                step("failed")

            except requests.RequestException as e:
                self.logger.debug(f"Socket Exception: {e!s}")

            return False

        self.logger.info(f"Uploaded Simplepush attachment {attachment_id}.")
        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol[0], self.token, self.password)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.broadcast:
            params["broadcast"] = "yes"

        if self.shared:
            params["shared"] = "yes"

        if self.priority is not None:
            params["priority"] = str(self.priority)

        if self.critical_volume is not None:
            params["critical_volume"] = str(self.critical_volume)

        if self.sptag:
            params["sptag"] = self.sptag

        if self.links:
            params["links"] = " ".join(self.links)

        if self.topic_auth_token:
            params["topic_auth_token"] = self.pprint(
                self.topic_auth_token, privacy, safe=""
            )

        auth = ""
        if self.password:
            auth = "{password}@".format(
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )

        return "{schema}://{auth}{token}/{targets}?{params}".format(
            schema=self.secure_protocol[0],
            auth=auth,
            token=self.pprint(self.token, privacy, safe=""),
            targets="/".join(
                [NotifySimplePush.quote(t, safe="") for t in self.topics]
                + [
                    "@" + NotifySimplePush.quote(m, safe="")
                    for m in self.members
                ]
            ),
            params=NotifySimplePush.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return max(1, len(self.topics) + len(self.members))

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The API Token (or organization integration token)
        results["token"] = NotifySimplePush.unquote(results["host"])

        # Topics and @members
        results["targets"] = NotifySimplePush.split_path(results["fullpath"])

        # The password is the user part of the URL
        if results.get("user"):
            results["password"] = NotifySimplePush.unquote(results["user"])
            results["user"] = None

        if "password" in results["qsd"] and len(results["qsd"]["password"]):
            results["password"] = NotifySimplePush.unquote(
                results["qsd"]["password"]
            )

        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifySimplePush.parse_list(
                results["qsd"]["to"]
            )

        for arg in (
            "priority",
            "critical_volume",
            "sptag",
            "links",
            "topic_auth_token",
        ):
            if arg in results["qsd"] and len(results["qsd"][arg]):
                results[arg] = NotifySimplePush.unquote(results["qsd"][arg])

        for arg in ("broadcast", "shared"):
            if arg in results["qsd"] and len(results["qsd"][arg]):
                results[arg] = parse_bool(results["qsd"][arg])

        return results

    @staticmethod
    def runtime_deps():
        """Return a tuple of top-level Python package names that this plugin
        imported as optional runtime dependencies.
        """
        return ("nacl",)
