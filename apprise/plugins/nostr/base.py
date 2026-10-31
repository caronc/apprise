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


# Nostr is an open, decentralized social network.  Messages are signed by
# your own key and published to one or more relays (servers) that anyone
# can run.
#
# Steps to get your key:
#  1. Create a Nostr account in any client (Damus, Primal, Amethyst,
#     0xchat, ...).  A separate account just for notifications is best.
#  2. Export the private key from the client's settings.  It starts with
#     nsec1... (64 hexadecimal characters also work).
#
#  To post a public note:
#     nostr://{nsec}
#
#  To send a private direct message to one or more people, add their
#  public key (npub1...) or Nostr address (name@example.com):
#     nostr://{nsec}/{npub}/{name@example.com}
#
# Direct messages use NIP-17 by default (?mode=nip17).  Older clients
# that only understand NIP-04 messages can use ?mode=nip04 instead.
#
# Attachments are uploaded to a Blossom media server and linked in the
# message.  Files sent in NIP-17 direct messages are encrypted first.
#
# Resources:
# - https://nostr.com/
# - https://github.com/nostr-protocol/nips
# - https://github.com/hzrd149/blossom

from __future__ import annotations

from base64 import urlsafe_b64encode
import hashlib
from json import dumps, loads
import re
import time
from typing import Any, Optional
from urllib.parse import urlsplit

import requests

from ...attachment.base import AttachBase
from ...common import NotifyFormat, NotifyType, PersistentStoreMode
from ...exception import AppriseImproperlyConfigured
from ...locale import gettext_lazy as _
from ...utils.http import is_secure_http_url, read_bounded_response
from ...utils.parse import is_hostname, parse_list
from ...utils.socket import AppriseSocketError
from ..base import NotifyBase
from .crypto import (
    IS_HEX_KEY,
    NOSTR_CRYPTOGRAPHY_SUPPORT,
    SECP256K1_N,
    NostrKey,
    bech32_encode,
    decode_key,
    encrypt_file,
    gift_wrap,
    is_public_key,
    nip04_encrypt,
    rumor,
    verify_event,
)
from .relay import NostrRelay


class NostrMode:
    """The ways a direct message can be sent."""

    # Private messages that hide who is talking to whom (NIP-17)
    NIP17 = "nip17"

    # Older encrypted messages understood by more clients (NIP-04)
    NIP04 = "nip04"


# Define our Nostr modes
NOSTR_MODES = (
    NostrMode.NIP17,
    NostrMode.NIP04,
)

# Well known public relays used when none are specified
NOSTR_DEFAULT_RELAYS = (
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.primal.net",
)

# A public Blossom server that accepts uploads from any key
NOSTR_DEFAULT_BLOSSOM = "https://nostr.download"

# Event kinds used by this plugin
NOSTR_KIND_NOTE = 1
NOSTR_KIND_NIP04 = 4
NOSTR_KIND_CHAT = 14
NOSTR_KIND_FILE = 15
NOSTR_KIND_INBOX_RELAYS = 10050
NOSTR_KIND_BLOSSOM_SERVERS = 10063
NOSTR_KIND_BLOSSOM_AUTH = 24242

# How long a Blossom upload permission stays valid (in seconds)
NOSTR_UPLOAD_AUTH_EXPIRY = 300

# The most relays we use from a recipient's list; NIP-17 asks for 1 to 3
NOSTR_MAX_INBOX_RELAYS = 3

# The most we read from a Nostr address or Blossom server reply (in bytes)
NOSTR_MAX_RESPONSE = 1048576

# The longest download link we accept from a Blossom server
NOSTR_MAX_URL_LENGTH = 2048

# A Nostr address (NIP-05) such as name@example.com
IS_NIP05 = re.compile(
    r"^(?P<name>[a-z0-9._-]+)@(?P<domain>[a-z0-9-]+(\.[a-z0-9-]+)+)$",
    re.I,
)

# A relay such as relay.example.com or wss://relay.example.com:7777/path
IS_RELAY = re.compile(
    r"^(?P<schema>wss?://)?(?P<host>[a-z0-9._~%-]+(:[0-9]+)?)"
    r"(?P<path>/[^\s?#]*)?$",
    re.I,
)


def normalize_relay(value: str) -> Optional[str]:
    """Return ``value`` as a relay URL, or None if it is not one."""
    match = (
        IS_RELAY.match(value) if len(value) <= NOSTR_MAX_URL_LENGTH else None
    )
    if not match:
        return None

    # wss:// is assumed when no schema is given
    url = (
        (match.group("schema") or "wss://").lower()
        + match.group("host")
        + (match.group("path") or "")
    )
    try:
        # Reading a port outside of 0-65535 raises a ValueError
        parsed = urlsplit(url)
        port = parsed.port

    except ValueError:
        return None

    # The host must be a real name or address, and port zero can not be
    # connected to
    return url if is_hostname(parsed.hostname or "") and port != 0 else None


class NotifyNostr(NotifyBase):
    """A wrapper for Nostr Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Nostr"

    # Direct messages are encrypted with the cryptography package
    requirements = {
        "packages_recommended": "cryptography",
    }

    # The services URL
    service_url = "https://nostr.com/"

    # The default secure protocol
    secure_protocol = "nostr"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/nostr/"

    # Files are uploaded to a Blossom server and linked in the message
    attachment_support = True

    # Relays are separate servers, so there is nothing to throttle against
    request_rate_per_sec = 0

    # Nostr messages are plain text
    notify_format = NotifyFormat.TEXT

    # Nostr has no title field
    title_maxlen = 0

    # Many relays refuse events larger than 64KB.  A direct message grows
    # a lot once sealed and wrapped, and this keeps even text made only of
    # 4 byte characters (such as emoji) under that size.
    body_maxlen = 7000

    # Cache relay lists, Blossom servers and Nostr addresses
    storage_mode = PersistentStoreMode.AUTO

    # Look these up again every 6 hours so changes are picked up
    default_cache_expiry_sec = 60 * 60 * 6

    # Define object URL templates
    templates = (
        "{schema}://{secret_key}",
        "{schema}://{secret_key}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "secret_key": {
                "name": _("Secret Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "target_user": {
                "name": _("Target User"),
                "type": "string",
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
            "key": {
                "alias_of": "secret_key",
            },
            "to": {
                "alias_of": "targets",
            },
            "mode": {
                "name": _("Mode"),
                "type": "choice:string",
                "values": NOSTR_MODES,
                "default": NostrMode.NIP17,
            },
            "relay": {
                "name": _("Relays"),
                "type": "list:string",
            },
            "blossom": {
                "name": _("Blossom Server"),
                "type": "string",
            },
        },
    )

    def __init__(
        self,
        secret_key: Optional[str] = None,
        targets: Optional[Any] = None,
        mode: Optional[str] = None,
        relay: Optional[Any] = None,
        blossom: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Nostr Object."""
        super().__init__(**kwargs)

        # Accept the secret key as nsec1... or 64 hex characters
        secret = decode_key(secret_key, "nsec")
        if not secret or not 0 < int(secret, 16) < SECP256K1_N:
            msg = "An invalid Nostr secret key was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Load our key; this also works out our public key
        self.key = NostrKey(int(secret, 16))

        # Pick how direct messages are sent
        self.mode = (
            mode.strip().lower()
            if isinstance(mode, str) and mode.strip()
            else NostrMode.NIP17
        )
        if self.mode not in NOSTR_MODES:
            msg = "The Nostr mode specified ({}) is invalid.".format(mode)
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Relays we publish to; wss:// is assumed when no schema is given
        self.relays = []
        for entry in parse_list(relay, sort=False):
            url = normalize_relay(entry)
            if not url:
                msg = "An invalid Nostr relay ({}) was specified.".format(
                    entry
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            self.relays.append(url)

        if not self.relays:
            # Fall back to some well known public relays
            self.relays = list(NOSTR_DEFAULT_RELAYS)

        # An optional Blossom server for attachments; https:// is assumed
        self.blossom = None
        if isinstance(blossom, str) and blossom.strip():
            self.blossom = blossom.strip().rstrip("/")
            if not re.match(r"^https?://", self.blossom, re.I):
                self.blossom = "https://" + self.blossom

        # Recipients are public keys (stored as hex) or Nostr addresses
        self.targets = []
        self.invalid_targets = []
        for target in parse_list(targets, sort=False):
            pubkey = decode_key(target, "npub")
            if pubkey and is_public_key(pubkey):
                self.targets.append(pubkey)
                continue

            if IS_NIP05.match(target):
                # Looked up when the first message is sent
                self.targets.append(target.lower())
                continue

            self.logger.warning(
                "Dropped invalid Nostr recipient (%s) specified.", target
            )
            self.invalid_targets.append(target)

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        attach: Optional[list[AttachBase]] = None,
        **kwargs: Any,
    ) -> bool:
        """Perform Nostr Notification."""
        # Attachments are skipped when attachment support is turned off
        if not self.attachment_support:
            attach = None

        if not self.targets:
            if self.invalid_targets:
                # Recipients were given but none of them were usable
                self.logger.warning(
                    "There are no valid Nostr recipients to notify."
                )
                return False

            # No recipients means a public note
            return self._send_note(body, attach)

        if not NOSTR_CRYPTOGRAPHY_SUPPORT:
            # Direct messages can not be encrypted without it
            self.logger.warning(
                "Nostr direct messages require the cryptography package."
            )
            return False

        # Upload any attachments once so every recipient shares them
        uploads = (
            self._upload_files(attach)
            if self.mode == NostrMode.NIP17
            else self._upload_links(attach)
        )
        if uploads is None:
            return False

        # Pick how each direct message is built
        send_dm = (
            self._send_nip17
            if self.mode == NostrMode.NIP17
            else self._send_nip04
        )

        has_error = False
        for target in self.targets:
            # Skip a recipient that already has this message
            if self.is_delivered(target):
                continue

            # Turn a Nostr address into a public key if needed
            pubkey = self._resolve(target)
            if not pubkey or not send_dm(pubkey, body, uploads):
                self.logger.warning(
                    "Failed to send Nostr direct message to %s.", target
                )

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this recipient
            self.logger.info("Sent Nostr direct message to %s.", target)
            self.mark_delivered(target)

        return not has_error

    def _send_note(
        self, body: str, attach: Optional[list[AttachBase]]
    ) -> bool:
        """Post a public note (kind 1)."""
        # A retry resends the same note so relays can spot the duplicate
        event = self.recall("note")
        if event is None:
            # Upload any attachments first
            links = self._upload_links(attach)
            if links is None:
                return False

            # Link each file in the note and describe it in an imeta tag
            urls, tags = links
            event = self.key.sign(
                NOSTR_KIND_NOTE,
                "\n".join(x for x in (body, *urls) if x),
                tags,
            )
            self.remember("note", event)

        if not self._publish(self.relays, [event]):
            self.logger.warning("Failed to send Nostr note.")
            return False

        self.logger.info("Sent Nostr note.")
        return True

    def _send_nip04(
        self,
        pubkey: str,
        body: str,
        links: tuple[list[str], list[list[str]]],
    ) -> bool:
        """Send an older style NIP-04 direct message to ``pubkey``."""
        # A retry resends the same message so relays can spot the duplicate
        event = self.recall(("nip04", pubkey))
        if event is None:
            # Link each uploaded file in the message and encrypt it all
            content = "\n".join(x for x in (body, *links[0]) if x)
            event = self.key.sign(
                NOSTR_KIND_NIP04,
                nip04_encrypt(content, self.key.shared_x(pubkey)),
                [["p", pubkey]],
            )
            self.remember(("nip04", pubkey), event)

        return self._publish(self.relays, [event])

    def _send_nip17(
        self, pubkey: str, body: str, files: list[dict[str, Any]]
    ) -> bool:
        """Send a private NIP-17 direct message to ``pubkey``."""
        # NIP-17 messages may only go to relays the recipient listed
        relays = self._inbox_relays(pubkey)
        if relays is None:
            self.logger.warning(
                "Could not look up the Nostr direct message relays of %s.",
                bech32_encode("npub", bytes.fromhex(pubkey)),
            )
            return False

        if not relays:
            self.logger.warning(
                "%s has not listed any relays for NIP-17 direct messages;"
                " ?mode=nip04 may reach them instead.",
                bech32_encode("npub", bytes.fromhex(pubkey)),
            )
            return False

        # A message to ourselves is already our own copy
        to_self = pubkey == self.key.public_key

        # A retry resends the same messages so relays can spot duplicates
        wraps = self.recall(("nip17", pubkey))
        if wraps is None:
            # The text itself is a chat message (kind 14)
            messages = []
            if body:
                messages.append(
                    rumor(
                        self.key.public_key,
                        NOSTR_KIND_CHAT,
                        body,
                        [["p", pubkey]],
                    )
                )

            # Each attachment becomes an encrypted file message (kind 15)
            for blob in files:
                messages.append(
                    rumor(
                        self.key.public_key,
                        NOSTR_KIND_FILE,
                        blob["url"],
                        [
                            ["p", pubkey],
                            ["file-type", blob["type"]],
                            ["encryption-algorithm", "aes-gcm"],
                            ["decryption-key", blob["key"]],
                            ["decryption-nonce", blob["nonce"]],
                            ["x", blob["sha256"]],
                            ["ox", blob["original"]],
                            ["size", str(blob["size"])],
                        ],
                    )
                )

            # Seal and gift wrap each one for the recipient, and again for
            # ourselves so our other Nostr clients show what was sent
            wraps = {
                "to": [gift_wrap(self.key, pubkey, m) for m in messages],
                "self": []
                if to_self
                else [
                    gift_wrap(self.key, self.key.public_key, m)
                    for m in messages
                ],
            }
            self.remember(("nip17", pubkey), wraps)

        # Only a list signed by someone else is kept to public addresses
        if not self._publish(relays, wraps["to"], public_only=not to_self):
            return False

        # Our own copy is kept when we list relays of our own; losing it
        # does not undo the delivery.  Our own list is signed by our own
        # key, so private relays are allowed there.
        own = wraps["self"] and self._inbox_relays(self.key.public_key)
        if own and not self._publish(own, wraps["self"]):
            self.logger.debug("Nostr could not keep a copy of the message.")

        return True

    def _publish(
        self,
        relays: list[str],
        events: list[dict[str, Any]],
        public_only: bool = False,
    ) -> bool:
        """Send ``events`` to each relay; True if each reached one.

        Set ``public_only`` for relays taken from someone's relay list.
        """
        accepted = set()
        for url in relays:
            # Always throttle before any remote server i/o is made
            self.throttle()

            self.logger.debug(
                "Nostr publishing %d event(s) to %s (cert_verify=%s)",
                len(events),
                url,
                self.verify_certificate,
            )
            try:
                with NostrRelay(
                    url,
                    self.key,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    user_agent=self.app_id,
                    public_only=public_only,
                ) as relay:
                    for event in events:
                        ok, reason = relay.publish(event)
                        if ok:
                            # One relay is enough, but more is safer
                            accepted.add(event["id"])
                            continue

                        self.logger.warning(
                            "Nostr relay %s rejected the message: %s",
                            url,
                            reason,
                        )

            except AppriseSocketError as e:
                self.logger.warning(
                    "A connection error occurred with Nostr relay %s.", url
                )
                self.logger.debug("Socket Exception: %s", str(e))

        # Every event must have reached at least one relay
        return len(accepted) == len(events)

    def _lookup(
        self, kind: int, pubkey: str
    ) -> tuple[Optional[dict[str, Any]], bool]:
        """Return the newest signed event of ``kind`` from ``pubkey``.

        The second value is False when no relay could be asked at all.
        """
        newest = None
        answered = False
        for url in self.relays:
            # Always throttle before any remote server i/o is made
            self.throttle()
            try:
                with NostrRelay(
                    url,
                    self.key,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    user_agent=self.app_id,
                ) as relay:
                    events = relay.query(
                        {"kinds": [kind], "authors": [pubkey], "limit": 1}
                    )

            except AppriseSocketError as e:
                # Another relay may still have it
                self.logger.debug("Nostr lookup on %s failed: %s", url, str(e))
                continue

            # This relay answered, even if it had nothing
            answered = True
            for event in events:
                # Only trust correctly signed events from the right author
                if (
                    verify_event(event)
                    and event["kind"] == kind
                    and event["pubkey"] == pubkey
                    and (
                        newest is None
                        or event["created_at"] > newest["created_at"]
                    )
                ):
                    newest = event

        return (newest, answered)

    def _lookup_tags(
        self, kind: int, pubkey: str, name: str
    ) -> Optional[list[str]]:
        """Return the values of each ``name`` tag in a looked up list.

        None is returned when no relay could be asked.
        """
        # Lists such as relays or servers are kept in the event's tags
        event, answered = self._lookup(kind, pubkey)
        if not answered:
            return None

        # Verified events always hold tags as lists of strings
        return [
            tag[1]
            for tag in (event["tags"] if event else [])
            if len(tag) > 1 and tag[0] == name
        ]

    def _inbox_relays(self, pubkey: str) -> Optional[list[str]]:
        """Return the relays ``pubkey`` reads direct messages from.

        An empty list means none are listed; None means the lookup failed.
        """
        # NIP-17 recipients list their preferred relays (kind 10050)
        cache_key = "inbox_{}".format(pubkey)
        relays = self.store.get(cache_key)
        if relays is not None:
            return relays

        listed = self._lookup_tags(NOSTR_KIND_INBOX_RELAYS, pubkey, "relay")
        if listed is None:
            # Try again next time rather than remember the failure
            return None

        # Only a few well formed, secure relays are accepted from someone
        # else's list
        relays = []
        for entry in listed:
            url = (
                normalize_relay(entry)
                if entry.lower().startswith("wss://")
                else None
            )
            if url and url not in relays:
                relays.append(url)
                if len(relays) >= NOSTR_MAX_INBOX_RELAYS:
                    break

        self.store.set(
            cache_key, relays, expires=self.default_cache_expiry_sec
        )
        return relays

    def _blossom_server(self) -> str:
        """Return the Blossom server attachments are uploaded to."""
        # An explicit server always wins
        if self.blossom:
            return self.blossom

        # Otherwise use the first server from our own list (kind 10063)
        server = self.store.get("blossom")
        if server is None:
            listed = self._lookup_tags(
                NOSTR_KIND_BLOSSOM_SERVERS, self.key.public_key, "server"
            )
            servers = [
                url.rstrip("/")
                for url in listed or []
                if is_secure_http_url(url)
            ]
            server = servers[0] if servers else NOSTR_DEFAULT_BLOSSOM
            if listed is not None:
                # Only remember an answer that really came from a relay
                self.store.set(
                    "blossom", server, expires=self.default_cache_expiry_sec
                )

        return server

    def _resolve(self, target: str) -> Optional[str]:
        """Return the public key (hex) for a recipient."""
        # Public keys were already decoded when we loaded
        if IS_HEX_KEY.match(target):
            return target

        # Nostr addresses are looked up once and cached
        cache_key = "nip05_{}".format(target)
        pubkey = self.store.get(cache_key)
        if pubkey:
            return pubkey

        # name@example.com is found at example.com/.well-known/nostr.json
        name, domain = target.split("@", 1)
        url = "https://{}/.well-known/nostr.json".format(domain)
        self.logger.debug(
            "Nostr address lookup: %s (cert_verify=%s)",
            url,
            self.verify_certificate,
        )

        # Always throttle before any remote server i/o is made
        self.throttle()
        try:
            # NIP-05 requires that redirects are never followed
            r = requests.get(
                url,
                params={"name": name},
                headers={
                    "User-Agent": self.app_id,
                    "Accept": "application/json",
                },
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=False,
                stream=True,
            )

            # Never read more than a sensible amount
            data = read_bounded_response(r, NOSTR_MAX_RESPONSE)

        except requests.RequestException as e:
            self.logger.warning(
                "A connection error occurred looking up Nostr address %s.",
                target,
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return None

        try:
            content = loads(data)

        except (RecursionError, TypeError, ValueError):
            # Not JSON, so there is nothing to find
            content = {}

        # The answer looks like {"names": {"<name>": "<hex pubkey>"}}
        names = content.get("names") if isinstance(content, dict) else None
        pubkey = names.get(name) if isinstance(names, dict) else None
        if (
            r.status_code != requests.codes.ok
            or not isinstance(pubkey, str)
            or not IS_HEX_KEY.match(pubkey)
            or not is_public_key(pubkey)
        ):
            self.logger.warning("Could not find Nostr address %s.", target)
            return None

        # Cache the answer for next time
        pubkey = pubkey.lower()
        self.store.set(
            cache_key, pubkey, expires=self.default_cache_expiry_sec
        )
        return pubkey

    def _upload_links(
        self, attach: Optional[list[AttachBase]]
    ) -> Optional[tuple[list[str], list[list[str]]]]:
        """Upload attachments; return their URLs and imeta tags."""
        urls: list[str] = []
        tags: list[list[str]] = []
        for index, attachment in enumerate(attach or []):
            # A retry reuses files that were already uploaded
            blob = self.recall(("upload", index), per_message=True)
            if blob is None:
                data = self._read(attachment)
                blob = (
                    None
                    if data is None
                    else self._upload(data, attachment.mimetype)
                )
                if blob is None:
                    return None

                self.remember(("upload", index), blob, per_message=True)

            # Clients show a preview using the details in the imeta tag
            urls.append(blob["url"])
            tags.append(
                [
                    "imeta",
                    "url {}".format(blob["url"]),
                    "m {}".format(blob["type"]),
                    "x {}".format(blob["sha256"]),
                    "size {}".format(blob["size"]),
                ]
            )

        return (urls, tags)

    def _upload_files(
        self, attach: Optional[list[AttachBase]]
    ) -> Optional[list[dict[str, Any]]]:
        """Encrypt and upload attachments for NIP-17 file messages."""
        files = []
        for index, attachment in enumerate(attach or []):
            # A retry reuses files that were already uploaded
            blob = self.recall(("encrypted", index), per_message=True)
            if blob is None:
                data = self._read(attachment)
                if data is None:
                    return None

                # Encrypt the file and upload it as anonymous binary data
                encrypted, key, nonce = encrypt_file(data)
                blob = self._upload(encrypted, "application/octet-stream")
                if blob is None:
                    return None

                # Keep what the recipient needs to download and decrypt it
                blob.update(
                    {
                        "type": attachment.mimetype,
                        "key": key,
                        "nonce": nonce,
                        "original": hashlib.sha256(data).hexdigest(),
                    }
                )
                self.remember(("encrypted", index), blob, per_message=True)

            files.append(blob)

        return files

    def _read(self, attachment: AttachBase) -> Optional[bytes]:
        """Return the contents of ``attachment``, or None."""
        # Make sure the file is there before opening it
        if not attachment:
            self.logger.warning(
                "Could not access Nostr attachment %s.",
                attachment.url(privacy=True),
            )
            return None

        try:
            # The handle is closed as soon as the file is read
            with attachment.open() as handle:
                return handle.read()

        except OSError as e:
            self.logger.warning(
                "An I/O error occurred while reading %s.",
                attachment.name or "attachment",
            )
            self.logger.debug("I/O Exception: %s", str(e))
            return None

    def _upload(self, data: bytes, mimetype: str) -> Optional[dict[str, Any]]:
        """Upload ``data`` to our Blossom server; return its details."""
        # Uploads are named by the SHA-256 of their content
        digest = hashlib.sha256(data).hexdigest()
        server = self._blossom_server()

        # Sign a short lived permission to upload this exact file
        auth = self.key.sign(
            NOSTR_KIND_BLOSSOM_AUTH,
            "Upload Blob",
            [
                ["t", "upload"],
                ["x", digest],
                [
                    "expiration",
                    str(int(time.time()) + NOSTR_UPLOAD_AUTH_EXPIRY),
                ],
            ],
        )

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": mimetype,
            "X-SHA-256": digest,
            # The permission travels as unpadded URL-safe base64
            "Authorization": "Nostr {}".format(
                urlsafe_b64encode(dumps(auth).encode()).rstrip(b"=").decode()
            ),
        }

        url = "{}/upload".format(server)
        self.logger.debug(
            "Nostr Blossom upload: %s (cert_verify=%s)",
            url,
            self.verify_certificate,
        )

        # Always throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.put(
                url,
                data=data,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
                stream=True,
            )

            # Never read more than a sensible amount
            reply = read_bounded_response(r, NOSTR_MAX_RESPONSE)

        except requests.RequestException as e:
            self.logger.warning(
                "A connection error occurred uploading to Blossom server %s.",
                server,
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return None

        try:
            content = loads(reply)

        except (RecursionError, TypeError, ValueError):
            # Not JSON, so there is no download link to use
            content = {}

        # The reply describes the stored file (BUD-02); it must be the
        # file we sent, and its link must be as secure as the server
        content = content if isinstance(content, dict) else {}
        link = content.get("url")
        valid = (
            isinstance(link, str)
            and len(link) <= NOSTR_MAX_URL_LENGTH
            and (
                re.match(r"^https://", link, re.I)
                or (
                    re.match(r"^http://", server, re.I)
                    and re.match(r"^http://", link, re.I)
                )
            )
            and str(content.get("sha256", "")).lower() == digest
            and content.get("size", len(data)) == len(data)
        )

        # 200 means the file was already there; 201 means it is new
        if (
            r.status_code not in (requests.codes.ok, requests.codes.created)
            or not valid
        ):
            status_str = NotifyNostr.http_response_code_lookup(r.status_code)
            self.logger.warning(
                "Failed to upload Nostr attachment to %s: %s%serror=%s.",
                server,
                status_str,
                ", " if status_str else "",
                r.status_code,
            )
            self.logger.debug(
                "Response Details:\r\n%s",
                r.headers.get("X-Reason") or reply,
            )
            return None

        return {
            "url": link,
            "type": mimetype,
            "sha256": digest,
            "size": len(data),
        }

    @property
    def url_identifier(self) -> tuple[str, str]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.key.public_key)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""
        # Only options that differ from the defaults are included
        params = {}
        if self.mode != NostrMode.NIP17:
            params["mode"] = self.mode

        if self.relays != list(NOSTR_DEFAULT_RELAYS):
            params["relay"] = ",".join(self.relays)

        if self.blossom:
            params["blossom"] = self.blossom

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{key}/{targets}?{params}".format(
            schema=self.secure_protocol,
            key=self.pprint(
                bech32_encode("nsec", self.key.secret.to_bytes(32, "big")),
                privacy,
                safe="",
            ),
            targets="/".join(
                NotifyNostr.quote(
                    bech32_encode("npub", bytes.fromhex(t))
                    if IS_HEX_KEY.match(t)
                    else t,
                    safe="@",
                )
                for t in (*self.targets, *self.invalid_targets)
            ),
            params=NotifyNostr.urlencode(params),
        )

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # A public note still counts as one notification
        return max(1, len(self.targets))

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The secret key is our host, unless ?key= is given
        results["secret_key"] = NotifyNostr.unquote(
            results["qsd"]["key"]
            if results["qsd"].get("key")
            else results["host"]
        )

        # Recipients are found in the path
        results["targets"] = NotifyNostr.split_path(results["fullpath"])

        # Support ?to= for recipients too
        if results["qsd"].get("to"):
            results["targets"] += NotifyNostr.parse_list(results["qsd"]["to"])

        # How direct messages are sent
        if results["qsd"].get("mode"):
            results["mode"] = NotifyNostr.unquote(results["qsd"]["mode"])

        # The relays to publish to
        if results["qsd"].get("relay"):
            results["relay"] = NotifyNostr.unquote(results["qsd"]["relay"])

        # The Blossom server used for attachments
        if results["qsd"].get("blossom"):
            results["blossom"] = NotifyNostr.unquote(results["qsd"]["blossom"])

        return results

    @staticmethod
    def runtime_deps() -> tuple[str, ...]:
        """Return optional runtime dependency package names."""
        return ("cryptography",)
