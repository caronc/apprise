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

import contextlib
from itertools import chain
from json import dumps
import os
import time

import requests

from ...common import NotifyImageSize, NotifyType, PersistentStoreMode
from ...locale import gettext_lazy as _
from ...utils import pem as _pem
from ...utils.base64 import base64_urlencode
from ...utils.parse import is_email, parse_bool, parse_list
from ..base import NotifyBase
from . import subscription


class VapidPushMode:
    """Supported Vapid Push Services."""

    CHROME = "chrome"
    FIREFOX = "firefox"
    EDGE = "edge"
    OPERA = "opera"
    APPLE = "apple"
    SAMSUNG = "samsung"
    BRAVE = "brave"
    GENERIC = "generic"


VAPID_API_LOOKUP = {
    VapidPushMode.CHROME: "https://fcm.googleapis.com/fcm/send",
    VapidPushMode.FIREFOX: (
        "https://updates.push.services.mozilla.com/wpush/v1"
    ),
    VapidPushMode.EDGE: (
        "https://fcm.googleapis.com/fcm/send"
    ),  # Edge uses FCM too
    VapidPushMode.OPERA: (
        "https://fcm.googleapis.com/fcm/send"
    ),  # Opera is Chromium-based
    VapidPushMode.APPLE: (
        "https://web.push.apple.com"
    ),  # Apple Web Push base endpoint
    VapidPushMode.BRAVE: "https://fcm.googleapis.com/fcm/send",
    VapidPushMode.SAMSUNG: "https://fcm.googleapis.com/fcm/send",
    VapidPushMode.GENERIC: "https://fcm.googleapis.com/fcm/send",
}

VAPID_PUSH_MODES = (
    VapidPushMode.CHROME,
    VapidPushMode.FIREFOX,
    VapidPushMode.EDGE,
    VapidPushMode.OPERA,
    VapidPushMode.APPLE,
)


class NotifyVapid(NotifyBase):
    """A wrapper for WebPush/Vapid notifications."""

    # Set our global enabled flag
    enabled = subscription.CRYPTOGRAPHY_SUPPORT and _pem.PEM_SUPPORT

    requirements = {
        # Define our required packaging in order to work
        "packages_required": "cryptography"
    }

    # The default descriptive name associated with the Notification
    service_name = "Vapid Web Push Notifications"

    # The services URL
    service_url = (
        "https://datatracker.ietf.org/doc/html/draft-thomson-webpush-vapid"
    )

    # The default protocol
    secure_protocol = "vapid"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_vapid"

    # There is no reason we should exceed 5KB when reading in a PEM file.
    # If it is more than this, then it is not accepted.
    max_vapid_keyfile_size = 5000

    # There is no reason we should exceed 5MB when reading in a JSON file.
    # If it is more than this, then it is not accepted.
    max_vapid_subfile_size = 5242880

    # The maximum length of the messge can be 4096
    # just choosing a safe number below this to allow for padding and
    # encryption
    body_maxlen = 4000

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Our default is to no not use persistent storage beyond in-memory
    # reference; this allows us to auto-generate our config if needed
    storage_mode = PersistentStoreMode.AUTO

    # 43200 = 12 hours
    vapid_jwt_expiration_sec = 43200

    # Subscription file
    vapid_subscription_file = "subscriptions.json"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # Define object templates
    templates = (
        "{schema}://{subscriber}",
        "{schema}://{subscriber}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "subscriber": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
            },
        },
    )

    # Define our template args
    template_args = dict(
        NotifyBase.template_tokens,
        **{
            "mode": {
                "name": _("Mode"),
                "type": "choice:string",
                "values": VAPID_PUSH_MODES,
                "default": VAPID_PUSH_MODES[0],
                "map_to": "mode",
            },
            # Default Time To Live (defined in seconds)
            # 0 (Zero) - message will be delivered only if the device is
            # reacheable
            "ttl": {
                "name": _("ttl"),
                "type": "int",
                "default": 0,
                "min": 0,
                "max": 60,
            },
            "to": {
                "alias_of": "targets",
            },
            "from": {
                "alias_of": "subscriber",
            },
            "keyfile": {
                # A Private Keyfile is required to sign header
                "name": _("PEM Private KeyFile"),
                "type": "string",
                "private": True,
            },
            "subfile": {
                # A Subscripion File is required to sign header
                "name": _("Subscripion File"),
                "type": "string",
                "private": True,
            },
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
        },
    )

    def __init__(
        self,
        subscriber,
        mode=None,
        targets=None,
        keyfile=None,
        subfile=None,
        include_image=None,
        ttl=None,
        **kwargs,
    ):
        """Initialize Vapid Messaging."""
        super().__init__(**kwargs)

        # Path to our Private Key file
        self.keyfile = None

        # Path to our subscription.json file
        self.subfile = None

        #
        # Our Targets
        #
        self.targets = []
        self._invalid_targets = []

        # default subscriptions
        self.subscriptions = {}
        self.subscriptions_loaded = False
        self.private_key_loaded = False

        # Set our Time to Live Flag
        self.ttl = self.template_args["ttl"]["default"]
        if ttl is not None:
            with contextlib.suppress(ValueError, TypeError):
                # Store our TTL (Time To live) if it is a valid integer
                self.ttl = int(ttl)

            if (
                self.ttl < self.template_args["ttl"]["min"]
                or self.ttl > self.template_args["ttl"]["max"]
            ):
                msg = f"The Vapid TTL specified ({self.ttl}) is out of range."
                self.logger.warning(msg)
                raise TypeError(msg)

        # Place a thumbnail image inline with the message body
        self.include_image = (
            self.template_args["image"]["default"]
            if include_image is None
            else include_image
        )

        result = is_email(subscriber)
        if not result:
            msg = f"An invalid Vapid Subscriber({subscriber}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)
        self.subscriber = result["full_email"]

        # Store our Mode/service
        try:
            self.mode = (
                NotifyVapid.template_args["mode"]["default"]
                if mode is None
                else mode.lower()
            )

            if self.mode not in VAPID_PUSH_MODES:
                # allow the outer except to handle this common response
                raise IndexError()

        except (AttributeError, IndexError, TypeError):
            # Invalid region specified
            msg = f"The Vapid mode specified ({mode}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg) from None

        # Our Private keyfile
        self.keyfile = keyfile

        # Our Subscription file
        self.subfile = subfile

        # Prepare our PEM Object
        self.pem = _pem.ApprisePEMController(self.store.path, asset=self.asset)

        # Create our subscription object
        self.subscriptions = subscription.WebPushSubscriptionManager(
            asset=self.asset
        )

        if (
            self.subfile is None
            and self.store.mode != PersistentStoreMode.MEMORY
            and self.asset.pem_autogen
        ):

            self.subfile = os.path.join(
                self.store.path, self.vapid_subscription_file
            )
            if not os.path.exists(self.subfile) and self.subscriptions.write(
                self.subfile
            ):
                self.logger.info(
                    "Vapid auto-generated %s/%s",
                    os.path.basename(self.store.path),
                    self.vapid_subscription_file,
                )

        # Acquire our targets for parsing
        self.targets = parse_list(targets)
        if not self.targets:
            # Add ourselves
            self.targets.append(self.subscriber)

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Vapid Notification."""
        if not self.private_key_loaded and (
            (
                self.keyfile
                and not self.pem.private_key(autogen=False, autodetect=False)
                and not self.pem.load_private_key(self.keyfile)
            )
            or (not self.keyfile and not self.pem)
        ):
            self.logger.warning(
                "Provided Vapid/WebPush (PEM) Private Key file could "
                "not be loaded."
            )
            self.private_key_loaded = True
            return False
        else:
            self.private_key_loaded = True

        if not self.targets:
            # There is no one to notify; we're done
            self.logger.warning("There are no Vapid targets to notify")
            return False

        if not self.subscriptions_loaded and self.subfile:
            # Toggle our loaded flag to prevent trying again later
            self.subscriptions_loaded = True
            if not self.subscriptions.load(
                self.subfile, byte_limit=self.max_vapid_subfile_size
            ):
                self.logger.warning(
                    "Provided Vapid/WebPush subscriptions file could not be "
                    "loaded."
                )
                return False

        if not self.subscriptions:
            self.logger.warning("Vapid could not load subscriptions")
            return False

        if not self.pem.private_key(autogen=False, autodetect=False):
            self.logger.warning(
                "No Vapid/WebPush (PEM) Private Key file could be loaded."
            )
            return False

        # Prepare our notify URL (based on our mode)
        notify_url = VAPID_API_LOOKUP[self.mode]
        headers = {
            "User-Agent": self.app_id,
            "TTL": str(self.ttl),
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "Authorization": f"vapid t={self.jwt_token}, k={self.public_key}",
        }

        has_error = False

        # Create a copy of the targets list
        targets = list(self.targets)
        while len(targets):
            target = targets.pop(0)
            if target not in self.subscriptions:
                self.logger.warning(
                    "Dropped Vapid user "
                    f"({target}) specified - not found in subscriptions.json.",
                )
                # Save ourselves from doing this again
                self._invalid_targets.append(target)
                self.targets.remove(target)
                has_error = True
                continue

            # Encrypt our payload
            encrypted_payload = self.pem.encrypt_webpush(
                body,
                public_key=self.subscriptions[target].public_key,
                auth_secret=self.subscriptions[target].auth_secret,
            )

            self.logger.debug(
                "Vapid %s POST URL: %s (cert_verify=%r)",
                self.mode,
                notify_url,
                self.verify_certificate,
            )
            self.logger.debug(
                "Vapid %s Encrypted Payload: %d byte(s)", self.mode, len(body)
            )

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    notify_url,
                    data=encrypted_payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code not in (
                    requests.codes.ok,
                    requests.codes.no_content,
                ):
                    # We had a problem
                    status_str = NotifyBase.http_response_code_lookup(
                        r.status_code
                    )

                    self.logger.warning(
                        "Failed to send {} Vapid notification: "
                        "{}{}error={}.".format(
                            self.mode,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug("Response Details:\r\n%s", r.content)

                    has_error = True

                else:
                    self.logger.info("Sent %s Vapid notification.", self.mode)

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Vapid notification."
                )
                self.logger.debug("Socket Exception: %s", str(e))

                has_error = True

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.mode, self.subscriber)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "mode": self.mode,
            "ttl": str(self.ttl),
        }

        if self.keyfile:
            # Include our keyfile if specified
            params["keyfile"] = self.keyfile

        if self.subfile:
            # Include our subfile if specified
            params["subfile"] = self.subfile

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        targets = (
            self.targets
            if not (
                self.targets == 1
                and self.targets[0].lower() == self.subscriber.lower()
            )
            else []
        )
        return "{schema}://{subscriber}/{targets}?{params}".format(
            schema=self.secure_protocol,
            subscriber=NotifyVapid.quote(self.subscriber, safe="@"),
            targets="/".join(
                chain(
                    [str(t) for t in targets],
                    [
                        NotifyVapid.quote(x, safe="@")
                        for x in self._invalid_targets
                    ],
                )
            ),
            params=NotifyVapid.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        targets = len(self.targets)
        return targets if targets else 1

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Prepare our targets
        results["targets"] = []
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["subscriber"] = NotifyVapid.unquote(results["qsd"]["from"])

            if results["user"] and results["host"]:
                # whatever is left on the URL goes
                results["targets"].append(
                    "{}@{}".format(
                        NotifyVapid.unquote(results["user"]),
                        NotifyVapid.unquote(results["host"]),
                    )
                )

            elif results["host"]:
                results["targets"].append(NotifyVapid.unquote(results["host"]))

        else:
            # Acquire our subscriber information
            results["subscriber"] = "{}@{}".format(
                NotifyVapid.unquote(results["user"]),
                NotifyVapid.unquote(results["host"]),
            )

        results["targets"].extend(NotifyVapid.split_path(results["fullpath"]))

        # Get our mode
        results["mode"] = results["qsd"].get("mode")

        # Get Image Flag
        results["include_image"] = parse_bool(
            results["qsd"].get(
                "image", NotifyVapid.template_args["image"]["default"]
            )
        )

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyVapid.parse_list(results["qsd"]["to"])

        # Our Private Keyfile (PEM)
        if "keyfile" in results["qsd"] and results["qsd"]["keyfile"]:
            results["keyfile"] = NotifyVapid.unquote(results["qsd"]["keyfile"])

        # Our Subscription File (JSON)
        if "subfile" in results["qsd"] and results["qsd"]["subfile"]:
            results["subfile"] = NotifyVapid.unquote(results["qsd"]["subfile"])

        # Support the 'ttl' variable
        if "ttl" in results["qsd"] and len(results["qsd"]["ttl"]):
            results["ttl"] = NotifyVapid.unquote(results["qsd"]["ttl"])

        return results

    @property
    def jwt_token(self):
        """Returns our VAPID Token based on class details."""
        # JWT header
        header = {"alg": "ES256", "typ": "JWT"}

        # JWT payload
        payload = {
            "aud": VAPID_API_LOOKUP[self.mode],
            "exp": int(time.time()) + self.vapid_jwt_expiration_sec,
            "sub": f"mailto:{self.subscriber}",
        }

        # Base64 URL encode header and payload
        header_b64 = base64_urlencode(
            dumps(header, separators=(",", ":")).encode("utf-8")
        )
        payload_b64 = base64_urlencode(
            dumps(payload, separators=(",", ":")).encode("utf-8")
        )
        signing_input = f"{header_b64}.{payload_b64}".encode()
        signature_b64 = base64_urlencode(self.pem.sign(signing_input))

        # Return final token
        return f"{header_b64}.{payload_b64}.{signature_b64}"

    @property
    def public_key(self):
        """Returns our public key representation."""
        return self.pem.x962_str
