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

from base64 import urlsafe_b64encode
import hashlib
from json import loads
from os import urandom

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import validate_regex
from .base import NotifyBase

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import (
        Cipher,
        algorithms,
        modes,
    )

    # We're good to go!
    NOTIFY_SIMPLEPUSH_ENABLED = True

except ImportError:
    # cryptography is required in order for this package to work
    NOTIFY_SIMPLEPUSH_ENABLED = False


class NotifySimplePush(NotifyBase):
    """A wrapper for SimplePush Notifications."""

    # Set our global enabled flag
    enabled = NOTIFY_SIMPLEPUSH_ENABLED

    requirements = {
        # Define our required packaging in order to work
        "packages_required": "cryptography"
    }

    # The default descriptive name associated with the Notification
    service_name = "SimplePush"

    # The services URL
    service_url = "https://simplepush.io/"

    # The default secure protocol
    secure_protocol = "spush"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_simplepush"

    # SimplePush uses the http protocol with SimplePush requests
    notify_url = "https://api.simplepush.io/send"

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 10000

    # Defines the maximum allowable characters in the title
    title_maxlen = 1024

    # Define object templates
    templates = (
        "{schema}://{apikey}",
        "{schema}://{salt}:{password}@{apikey}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            # Used for encrypted logins
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
            },
            "salt": {
                "name": _("Salt"),
                "type": "string",
                "private": True,
                "map_to": "user",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "event": {
                "name": _("Event"),
                "type": "string",
            },
        },
    )

    def __init__(self, apikey, event=None, **kwargs):
        """Initialize SimplePush Object."""
        super().__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid SimplePush API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        if event:
            # Event Name (associated with project)
            self.event = validate_regex(event)
            if not self.event:
                msg = (
                    "An invalid SimplePush Event Name "
                    f"({event}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        else:
            # Default Event Name
            self.event = None

        # Used/cached in _encrypt() function
        self._iv = None
        self._iv_hex = None
        self._key = None

    def _encrypt(self, content):
        """Encrypts message for use with SimplePush."""

        if self._iv is None:
            # initialization vector and cache it
            self._iv = urandom(algorithms.AES.block_size // 8)

            # convert vector into hex string (used in payload)
            self._iv_hex = "".join([
                f"{ord(self._iv[idx:idx + 1]):02x}"
                for idx in range(len(self._iv))
            ]).upper()

            # encrypted key and cache it
            self._key = bytes(
                bytearray.fromhex(
                    hashlib.sha1(
                        f"{self.password}{self.user}".encode()
                    ).hexdigest()[0:32]
                )
            )

        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        content = padder.update(content.encode()) + padder.finalize()
        #
        # Encryption Notice
        #

        # CBC mode doesn't provide integrity guarantees. Unless the message
        # authentication for IV and the ciphertext are applied, it will be
        # vulnerable to a padding oracle attack

        # It is important to identify that both the Apprise package and team
        # recognizes this AES-CBC-128 weakness but requires that it exists due
        # to it being the SimplePush Requirement as documented on their
        # website here https://simplepush.io/features.

        # In the event the website link above does not exist/work, a screen
        # capture of the reference to the requirement for this encryption
        # can also be found on the Apprise SimplePush Wiki:
        #   https://github.com/caronc/apprise/wiki/Notify_simplepush\
        #       #lock-aes-cbc-128-encryption-weakness
        #
        encryptor = Cipher(
            algorithms.AES(self._key), modes.CBC(self._iv), default_backend()
        ).encryptor()

        return urlsafe_b64encode(
            encryptor.update(content) + encryptor.finalize()
        )

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform SimplePush Notification."""

        headers = {
            "User-Agent": self.app_id,
            "Content-type": "application/x-www-form-urlencoded",
        }

        # Prepare our payload
        payload = {
            "key": self.apikey,
        }

        if self.password and self.user:
            body = self._encrypt(body)
            title = self._encrypt(title)
            payload.update({
                "encrypted": "true",
                "iv": self._iv_hex,
            })

        # prepare SimplePush Object
        payload.update({
            "msg": body,
            "title": title,
        })

        if self.event:
            # Store Event
            payload["event"] = self.event

        self.logger.debug(
            "SimplePush POST URL:"
            f" {self.notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"SimplePush Payload: {payload!s}")

        # We need to rely on the status string returned in the SimplePush
        # response
        status_str = None
        status = None

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            # Get our SimplePush response (if it's possible)
            try:
                json_response = loads(r.content)
                status_str = json_response.get("message")
                status = json_response.get("status")

            except (TypeError, ValueError, AttributeError):
                # TypeError = r.content is not a String
                # ValueError = r.content is Unparsable
                # AttributeError = r.content is None
                pass

            if r.status_code != requests.codes.ok or status != "OK":
                # We had a problem
                status_str = (
                    status_str
                    if status_str
                    else NotifyBase.http_response_code_lookup(r.status_code)
                )

                self.logger.warning(
                    "Failed to send SimplePush notification:"
                    "{}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # Return; we're done
                return False

            else:
                self.logger.info("Sent SimplePush notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending SimplePush notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # Return; we're done
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.user, self.password, self.apikey)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.event:
            params["event"] = self.event

        # Determine Authentication
        auth = ""
        if self.user and self.password:
            auth = "{salt}:{password}@".format(
                salt=self.pprint(
                    self.user, privacy, mode=PrivacyMode.Secret, safe=""
                ),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )

        return "{schema}://{auth}{apikey}/?{params}".format(
            schema=self.secure_protocol,
            auth=auth,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            params=NotifySimplePush.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Set the API Key
        results["apikey"] = NotifySimplePush.unquote(results["host"])

        # Event
        if "event" in results["qsd"] and len(results["qsd"]["event"]):
            # Extract the account sid from an argument
            results["event"] = NotifySimplePush.unquote(
                results["qsd"]["event"]
            )

        return results
