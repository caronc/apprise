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

from collections.abc import Iterable
import contextlib
import json
import os
import stat
import tempfile
from typing import Optional, Union
from urllib.parse import urlparse

from ...apprise_attachment import AppriseAttachment
from ...asset import AppriseAsset
from ...common import ContentLocation
from ...exception import AppriseInvalidData
from ...logger import logger
from ...utils.base64 import base64_urldecode
from ...utils.cwe312 import cwe312_url
from ...utils.parse import is_hostname

try:
    from cryptography.hazmat.primitives.asymmetric import ec

    # Cryptography Support enabled
    CRYPTOGRAPHY_SUPPORT = True

except ImportError:
    # Cryptography Support disabled
    CRYPTOGRAPHY_SUPPORT = False


def loggable_file(path: Optional[str], secure: bool = True) -> str:
    """Returns a log-safe path or URL, masking remote credentials."""

    if not path:
        return "(none)"

    return cwe312_url(path) if secure else path


def webpush_origin(endpoint: Optional[str]) -> Optional[str]:
    """Validates an endpoint and returns its JWT audience origin.

    Web Push requires HTTPS, and the token names the endpoint's origin. The
    origin includes a non-default port when present.

    ``None`` is returned when the endpoint:
     - is not a string or valid URL
     - does not use HTTPS
     - has no hostname
     - contains a username or password, even an empty one
     - uses an invalid port
     - has a hostname that is not a valid host or IP address

    Private and loopback addresses remain valid for self-hosted services.
    Callers should load subscription data only from trusted sources.
    """

    if not isinstance(endpoint, str):
        return None

    try:
        results = urlparse(endpoint)

        # Parsing malformed IPv6 or reading an invalid port raises ValueError.
        port = results.port

    except ValueError:
        return None

    # Web Push requires HTTPS.
    if results.scheme.lower() != "https":
        return None

    # Reject URLs without a destination host.
    hostname = results.hostname
    if not hostname:
        return None

    # Reject credentials embedded in the endpoint. Compare against None so
    # that an empty "https://@example.com" is caught too.
    if results.username is not None or results.password is not None:
        return None

    # Validate the host; this covers hostnames, IPv4 and IPv6 alike. Only
    # the yes or no answer is used, because is_hostname() shortens a
    # compressed IPv6 address when it hands one back.
    if not is_hostname(hostname):
        return None

    # Restore the IPv6 brackets that the URL parser stripped off.
    host = f"[{hostname}]" if ":" in hostname else hostname

    # Exclude the default HTTPS port from the origin.
    return (
        f"https://{host}" if port in (None, 443) else f"https://{host}:{port}"
    )


class WebPushSubscription:
    """WebPush Subscription."""

    # Format:
    # {
    #     "endpoint": "https://fcm.googleapis.com/fcm/send/abc123...",
    #     "keys": {
    #         "p256dh": "BNcW4oA7zq5H9TKIrA3XfKclN2fX9P_7NR...",
    #         "auth": "k9Xzm43nBGo=",
    #     }
    # }
    def __init__(self, content: Union[str, dict, None] = None) -> None:
        """Creates a subscription from a dictionary or JSON string."""

        # Our variables
        self.__endpoint = None
        self.__origin = None
        self.__p256dh = None
        self.__auth = None
        self.__auth_secret = None
        self.__public_key = None

        if content is not None and not self.load(content):
            raise AppriseInvalidData("Could not load subscription")

    def load(self, content: Union[str, dict, None] = None) -> bool:
        """Performs the loading/validation of the object."""

        # Reset our variables
        self.__endpoint = None
        self.__origin = None
        self.__p256dh = None
        self.__auth = None
        self.__auth_secret = None
        self.__public_key = None

        if not CRYPTOGRAPHY_SUPPORT:
            logger.debug("cryptography not installed; Vapid disabled")
            return False

        if isinstance(content, str):
            try:
                content = json.loads(content)

            except (json.decoder.JSONDecodeError, TypeError) as e:
                # A string supplied here must contain valid JSON.
                logger.debug("Vapid subscription is not valid JSON: %s", e)
                return False

        if not isinstance(content, dict):
            # We could not load he result set
            logger.debug(
                "Vapid subscription is a %s, not an object",
                type(content).__name__,
            )
            return False

        # Retrieve and validate the endpoint.
        endpoint = content.get("endpoint")
        if isinstance(endpoint, str):
            # Allow surrounding whitespace in hand-edited files.
            endpoint = endpoint.strip()

        # Reject the subscription when its endpoint is unusable.
        origin = webpush_origin(endpoint)
        if not origin:
            logger.debug(
                "Vapid subscription endpoint is unusable: %s",
                loggable_file(endpoint),
            )
            return False

        try:
            p256dh = base64_urldecode(content["keys"]["p256dh"])
            if not p256dh:
                logger.debug("Vapid subscription p256dh key is not base64")
                return False

            auth_secret = base64_urldecode(content["keys"]["auth"])
            if not auth_secret:
                logger.debug("Vapid subscription auth key is not base64")
                return False

        except KeyError as e:
            logger.debug("Vapid subscription is missing a %s entry", e)
            return False

        try:
            # Store our data
            self.__public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256R1(),
                p256dh,
            )

        except ValueError as e:
            # Invalid p256dh key (Can't load Public Key)
            logger.debug("Vapid subscription p256dh key is not usable: %s", e)
            return False

        self.__endpoint = endpoint
        self.__origin = origin
        self.__p256dh = content["keys"]["p256dh"]
        self.__auth = content["keys"]["auth"]
        self.__auth_secret = auth_secret

        logger.trace("Vapid subscription loaded for %s", origin)

        return True

    def write(self, path: str, indent: int = 2) -> bool:
        """Writes this subscription to a JSON file."""
        if not self.__public_key:
            return False

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.dict, f, indent=indent)

        except (TypeError, ValueError) as e:
            # The subscription or supplied path could not be serialized.
            logger.warning("Vapid subscription could not be written")
            logger.debug("JSON Exception: %s", e)
            return False

        except OSError as e:
            logger.warning(
                "Error writing Vapid subscription file %s",
                loggable_file(path),
            )
            logger.debug("I/O Exception: %s", e)
            return False

        return True

    @property
    def auth(self) -> Optional[str]:
        return self.__auth if self.__public_key else None

    @property
    def endpoint(self) -> Optional[str]:
        return self.__endpoint if self.__public_key else None

    @property
    def origin(self) -> Optional[str]:
        """The origin our JWT must be addressed to for this endpoint."""
        return self.__origin if self.__public_key else None

    @property
    def p256dh(self) -> Optional[str]:
        return self.__p256dh if self.__public_key else None

    @property
    def auth_secret(self) -> Optional[bytes]:
        return self.__auth_secret if self.__public_key else None

    @property
    def public_key(self) -> Optional["ec.EllipticCurvePublicKey"]:
        return self.__public_key

    @property
    def dict(self) -> dict:
        return (
            {
                "endpoint": self.__endpoint,
                "keys": {
                    "p256dh": self.__p256dh,
                    "auth": self.__auth,
                },
            }
            if self.__public_key
            else {
                "endpoint": "https://fcm.googleapis.com/fcm/send/abc123...",
                "keys": {
                    "p256dh": "<place public key in base64 here>",
                    "auth": "<place auth in base64 here>",
                },
            }
        )

    def json(self, indent: int = 2) -> str:
        """Returns JSON representation of the object."""
        return json.dumps(self.dict, indent=indent)

    def __bool__(self) -> bool:
        """Handle 'if' statement."""
        return bool(self.__public_key)

    def __str__(self) -> str:
        """Returns our JSON entry as a string."""
        # Return the first 16 characters of the detected endpoint subscription
        # id
        return (
            "" if not self.__endpoint else self.__endpoint.split("/")[-1][:16]
        )


class WebPushSubscriptionManager:
    """WebPush Subscription Manager."""

    # Format:
    # {
    #     "name1": {
    #         "endpoint": "https://fcm.googleapis.com/fcm/send/abc123...",
    #         "keys": {
    #             "p256dh": "BNcW4oA7zq5H9TKIrA3XfKclN2fX9P_7NR...",
    #             "auth": "k9Xzm43nBGo=",
    #         }
    #     },
    #     "name2": {
    #         "endpoint": "https://fcm.googleapis.com/fcm/send/abc123...",
    #         "keys": {
    #             "p256dh": "BNcW4oA7zq5H9TKIrA3XfKclN2fX9P_7NR...",
    #             "auth": "k9Xzm43nBGo=",
    #         }
    #     },

    # Defines the number of failures we can accept before we abort and assume
    # the file is bad
    max_load_failure_count = 3

    def __init__(self, asset: Optional["AppriseAsset"] = None) -> None:
        """Webpush Subscription Manager."""

        # Our subscriptions
        self.__subscriptions = {}

        # Remote sources have no local file to update.
        self.__path = None

        # Prepare our Asset Object
        self.asset = (
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()
        )

    def __getitem__(self, key: str) -> WebPushSubscription:
        """Returns our indexed value if it exists."""
        return self.__subscriptions[key.lower()]

    def __setitem__(
        self, name: str, subscription: Union[WebPushSubscription, str, dict]
    ) -> None:
        """Sets a named subscription when its data is valid."""

        if not self.add(subscription, name=name.lower()):
            raise AppriseInvalidData("Invalid subscription provided")

    def add(
        self,
        subscription: Union[WebPushSubscription, str, dict],
        name: Optional[str] = None,
    ) -> bool:
        """Add a subscription into our manager."""

        if not isinstance(subscription, WebPushSubscription):
            try:
                # Support loading our object
                subscription = WebPushSubscription(subscription)

            except AppriseInvalidData:
                return False

        if name is None:
            name = str(subscription)

        self.__subscriptions[name.lower()] = subscription
        return True

    def __bool__(self) -> bool:
        """True is returned if at least one subscription has been loaded."""
        return bool(self.__subscriptions)

    def __len__(self) -> int:
        """Returns the number of loaded subscriptions."""
        return len(self.__subscriptions)

    def __iadd__(
        self, subscription: Union[WebPushSubscription, str, dict]
    ) -> "WebPushSubscriptionManager":

        if not self.add(subscription):
            raise AppriseInvalidData("Invalid subscription provided")

        return self

    def __contains__(self, key: str) -> bool:
        """Checks if the key exists."""
        return key.lower() in self.__subscriptions

    def remove(self, key: str) -> bool:
        """Removes a subscription. Returns True if one was removed."""
        if key.lower() in self.__subscriptions:
            del self.__subscriptions[key.lower()]
            return True

        return False

    def clear(self) -> None:
        """Empties our server list."""
        self.__subscriptions.clear()

    def loggable_path(self, path: Optional[str]) -> str:
        """Returns a path that is safe to log, honouring secure_logging."""
        return loggable_file(path, self.asset.secure_logging)

    @property
    def path(self) -> Optional[str]:
        """The local file we loaded from, or None if there was not one."""
        return self.__path

    @property
    def writable(self) -> bool:
        """Returns whether the loaded local file can be updated.

        Remote and read-only files cannot be changed.
        """
        if not self.__path:
            return False

        return os.access(self.__path, os.W_OK)

    def prune(self, names: "Iterable[str]", indent: int = 2) -> bool:
        """Removes named subscriptions from the current file on disk.

        Reloading preserves unnamed and invalid entries, plus changes made
        since this object loaded. Simultaneous writers still require locking.
        """
        if not self.writable:
            # Respect remote sources and read-only files.
            logger.debug(
                "Vapid subscription file not pruned, reason=%s",
                "no-local-file" if not self.__path else "read-only",
            )
            return False

        try:
            with open(self.__path, encoding="utf-8") as f:
                content = json.load(f)

        except FileNotFoundError:
            # The file disappeared after it was loaded.
            logger.debug(
                "Vapid subscription file not found: %s",
                self.loggable_path(self.__path),
            )
            return False

        except (json.decoder.JSONDecodeError, TypeError) as e:
            # Preserve content that can no longer be parsed.
            logger.warning(
                "Vapid subscription file does not hold valid JSON; not"
                " pruning: %s",
                self.loggable_path(self.__path),
            )
            logger.debug("JSON Exception: %s", e)
            return False

        except OSError as e:
            logger.warning(
                "Error accessing Vapid subscription file %s",
                self.loggable_path(self.__path),
            )
            logger.debug("I/O Exception: %s", e)
            return False

        if not isinstance(content, dict):
            logger.warning(
                "Vapid subscription file does not hold an object: %s",
                self.loggable_path(self.__path),
            )
            return False

        # A single entry file has no names in it to take out
        if "endpoint" in content and "keys" in content:
            logger.debug(
                "Vapid subscription file holds a single entry; nothing to"
                " prune: %s",
                self.loggable_path(self.__path),
            )
            return False

        # Match names case-insensitively, as they were matched when loaded.
        wanted = {name.lower() for name in names}
        remaining = {
            name: entry
            for name, entry in content.items()
            if name.lower() not in wanted
        }

        if len(remaining) == len(content):
            # The requested entries are already absent.
            logger.trace(
                "Vapid subscription file already free of %d expired "
                "entry(s): %s",
                len(wanted),
                self.loggable_path(self.__path),
            )
            return True

        if not self.__write(remaining, self.__path, indent=indent):
            return False

        logger.info(
            "Pruned %d expired Vapid subscription(s) from %s",
            len(content) - len(remaining),
            self.loggable_path(self.__path),
        )

        return True

    @property
    def dict(self) -> dict:
        """Returns a dictionary of all entries."""
        return (
            {k: v.dict for k, v in self.__subscriptions.items()}
            if self.__subscriptions
            else {}
        )

    def load(self, path: str, byte_limit=0) -> bool:
        """Loads subscriptions from a local path or remote URL.

        Remote files are temporary and read-only. A zero ``byte_limit``
        disables the size limit.
        """

        # Reset our object
        self.clear()

        # A remote or failed load must not retain an earlier local path.
        self.__path = None

        # Create our attachment object
        attach = AppriseAttachment(asset=self.asset)

        # Add our path
        if not attach.add(path):
            # We could not make sense of what we were handed
            logger.warning(
                "Vapid subscription file could not be referenced: %s",
                self.loggable_path(path),
            )
            return False

        if byte_limit > 0:
            # Enforce maximum file size
            attach[0].max_file_size = byte_limit

        if not attach.sync():
            logger.warning(
                "Vapid subscription file could not be retrieved: %s",
                self.loggable_path(path),
            )
            return False

        try:
            # Otherwise open our path
            with open(attach[0].path, encoding="utf-8") as f:
                content = json.load(f)

        except FileNotFoundError:
            # The resolved file disappeared before it could be opened.
            logger.debug(
                "Vapid subscription file not found: %s",
                self.loggable_path(path),
            )
            return False

        except (json.decoder.JSONDecodeError, TypeError) as e:
            # We read it, but there is no JSON object in there
            logger.warning(
                "Vapid subscription file does not hold valid JSON: %s",
                self.loggable_path(path),
            )
            logger.debug("JSON Exception: %s", e)
            return False

        except OSError as e:
            logger.warning(
                "Error accessing Vapid subscription file %s",
                self.loggable_path(path),
            )
            logger.debug("I/O Exception: %s", e)
            return False

        if not isinstance(content, dict):
            # Not a list of dictionaries
            logger.warning(
                "Vapid subscription file does not hold an object: %s",
                self.loggable_path(path),
            )
            return False

        # Remember only local files so expired entries can be removed later.
        if attach[0].location == ContentLocation.LOCAL:
            self.__path = attach[0].path
            logger.trace(
                "Vapid subscriptions are local: %s",
                self.loggable_path(self.__path),
            )

        else:
            logger.trace(
                "Vapid subscriptions are hosted remotely; treating as "
                "read-only"
            )

        # Verify if we're dealing with a single element:
        # {
        #     "endpoint": "https://fcm.googleapis.com/fcm/send/abc123...",
        #     "keys": {
        #         "p256dh": "BNcW4oA7zq5H9TKIrA3XfKclN2fX9P_7NR...",
        #         "auth": "k9Xzm43nBGo=",
        #     }
        # }
        #
        # or if we're dealing with a multiple set
        #
        # {
        #     "name1": {
        #         "endpoint": "https://fcm.googleapis.com/fcm/send/abc123...",
        #         "keys": {
        #             "p256dh": "BNcW4oA7zq5H9TKIrA3XfKclN2fX9P_7NR...",
        #             "auth": "k9Xzm43nBGo=",
        #         }
        #     },
        #     "name2": {
        #         "endpoint": "https://fcm.googleapis.com/fcm/send/abc123...",
        #         "keys": {
        #             "p256dh": "BNcW4oA7zq5H9TKIrA3XfKclN2fX9P_7NR...",
        #             "auth": "k9Xzm43nBGo=",
        #         }
        #     },

        error_count = 0
        if "endpoint" in content and "keys" in content:
            if not self.add(content):
                logger.warning(
                    "Vapid subscription could not be loaded from %s",
                    self.loggable_path(path),
                )
                return False

        else:
            for name, subscription in content.items():
                if not self.add(subscription, name=name.lower()):
                    error_count += 1
                    logger.warning(
                        "Vapid subscription (%s) could not be loaded from %s",
                        name,
                        self.loggable_path(path),
                    )
                    if error_count > self.max_load_failure_count:
                        logger.warning(
                            "Vapid subscription file abandoned after %d "
                            "bad entries: %s",
                            error_count,
                            self.loggable_path(path),
                        )
                        self.clear()
                        return False

        logger.debug(
            "Loaded %d Vapid subscription(s) from %s",
            len(self.__subscriptions),
            self.loggable_path(path),
        )

        return True

    def write(self, path: str, indent: int = 2) -> bool:
        """Writes subscriptions as JSON using an atomic file replacement.

        A failed write leaves the old file intact. Symlinks are followed,
        metadata is preserved when permitted, and new files use mode 0600.
        """
        return self.__write(self.dict, path, indent=indent)

    def __write(self, content: dict, path: str, indent: int = 2) -> bool:
        """Replaces a file without exposing partially written JSON.

        A temporary file is completed beside the target before being moved
        into place.
        """

        # Resolve a symlink so we replace what it points at instead of the
        # link itself.
        target = os.path.realpath(path)

        # Track the temporary file so failures can clean it up.
        tmp_path = None
        try:
            # Write beside the target so replacement stays on one filesystem.
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=os.path.dirname(target),
                prefix=f"{os.path.basename(target)}.",
                suffix=".tmp",
                delete=False,
            ) as f:
                tmp_path = f.name
                json.dump(content, f, indent=indent)

            # Preserve the existing file's permissions and ownership.
            try:
                metadata = os.stat(target)

            except FileNotFoundError:
                # New files keep the temporary file's restrictive mode.
                metadata = None

            except OSError as e:
                # Keep the restrictive mode when metadata is unavailable.
                logger.debug(
                    "Could not read the mode of %s",
                    self.loggable_path(target),
                )
                logger.debug("I/O Exception: %s", e)
                metadata = None

            if metadata:
                os.chmod(tmp_path, stat.S_IMODE(metadata.st_mode))
                logger.trace(
                    "Carried mode %o onto new Vapid subscription file",
                    stat.S_IMODE(metadata.st_mode),
                )

                # Keep current ownership when it cannot be preserved.
                with contextlib.suppress(OSError):
                    os.chown(tmp_path, metadata.st_uid, metadata.st_gid)

            # Replace the old file with the completed JSON.
            os.replace(tmp_path, target)

            # The replacement consumed the temporary path.
            tmp_path = None

        except (TypeError, ValueError) as e:
            # The content could not be turned into JSON at all
            logger.warning(
                "Vapid subscriptions could not be written to %s",
                self.loggable_path(target),
            )
            logger.debug("JSON Exception: %s", e)
            return False

        except OSError as e:
            logger.warning(
                "Error writing Vapid subscription file %s",
                self.loggable_path(target),
            )
            logger.debug("I/O Exception: %s", e)
            return False

        finally:
            # Remove any temporary file left by a failed write.
            if tmp_path:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)
                    logger.trace("Removed %s", tmp_path)

        logger.trace(
            "Wrote %d Vapid subscription(s) to %s",
            len(content),
            self.loggable_path(target),
        )

        return True

    def json(self, indent: int = 2) -> str:
        """Returns JSON representation of the object."""
        return json.dumps(self.dict, indent=indent)
