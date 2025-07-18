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

import json
from typing import Optional, Union

from ...apprise_attachment import AppriseAttachment
from ...asset import AppriseAsset
from ...exception import AppriseInvalidData
from ...utils.base64 import base64_urldecode

try:
    from cryptography.hazmat.primitives.asymmetric import ec

    # Cryptography Support enabled
    CRYPTOGRAPHY_SUPPORT = True

except ImportError:
    # Cryptography Support disabled
    CRYPTOGRAPHY_SUPPORT = False


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
        """Prepares a webpush object provided with content Content can be a
        dictionary, or JSON String."""

        # Our variables
        self.__endpoint = None
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
        self.__p256dh = None
        self.__auth = None
        self.__auth_secret = None
        self.__public_key = None

        if not CRYPTOGRAPHY_SUPPORT:
            return False

        if isinstance(content, str):
            try:
                content = json.loads(content)

            except (json.decoder.JSONDecodeError, TypeError, OSError):
                # Bad data
                return False

        if not isinstance(content, dict):
            # We could not load he result set
            return False

        # Retreive our contents for validation
        endpoint = content.get("endpoint")
        if not isinstance(endpoint, str):
            return False

        try:
            p256dh = base64_urldecode(content["keys"]["p256dh"])
            if not p256dh:
                return False

            auth_secret = base64_urldecode(content["keys"]["auth"])
            if not auth_secret:
                return False

        except KeyError:
            return False

        try:
            # Store our data
            self.__public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                ec.SECP256R1(),
                p256dh,
            )

        except ValueError:
            # Invalid p256dh key (Can't load Public Key)
            return False

        self.__endpoint = endpoint
        self.__p256dh = content["keys"]["p256dh"]
        self.__auth = content["keys"]["auth"]
        self.__auth_secret = auth_secret

        return True

    def write(self, path: str, indent: int = 2) -> bool:
        """Writes content to disk based on path specified.

        Content is a JSON file, so ideally you may wish to have `.json' as it's
        extension for clarity
        """
        if not self.__public_key:
            return False

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.dict, f, indent=indent)

        except (TypeError, OSError):
            # Could not write content
            return False

        return True

    @property
    def auth(self) -> Optional[str]:
        return self.__auth if self.__public_key else None

    @property
    def endpoint(self) -> Optional[str]:
        return self.__endpoint if self.__public_key else None

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
        """Set's our object if possible."""

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
        """Returns the number of servers loaded; this includes those found
        within loaded configuration.

        This funtion nnever actually counts the Config entry themselves (if
        they exist), only what they contain.
        """
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

    def clear(self) -> None:
        """Empties our server list."""
        self.__subscriptions.clear()

    @property
    def dict(self) -> dict:
        """Returns a dictionary of all entries."""
        return (
            {k: v.dict for k, v in self.__subscriptions.items()}
            if self.__subscriptions
            else {}
        )

    def load(self, path: str, byte_limit=0) -> bool:
        """Writes content to disk based on path specified.  Content is a JSON
        file, so ideally you may wish to have `.json' as it's extension for
        clarity.

        if byte_limit is zero, then we do not limit our file size, otherwise
        set this to the bytes you want to restrict yourself by
        """

        # Reset our object
        self.clear()

        # Create our attachment object
        attach = AppriseAttachment(asset=self.asset)

        # Add our path
        attach.add(path)

        if byte_limit > 0:
            # Enforce maximum file size
            attach[0].max_file_size = byte_limit

        if not attach.sync():
            return False

        try:
            # Otherwise open our path
            with open(attach[0].path, encoding="utf-8") as f:
                content = json.load(f)

        except (json.decoder.JSONDecodeError, TypeError, OSError):
            # Could not read
            return False

        if not isinstance(content, dict):
            # Not a list of dictionaries
            return False

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
                return False

        else:
            for name, subscription in content.items():
                if not self.add(subscription, name=name.lower()):
                    error_count += 1
                    if error_count > self.max_load_failure_count:
                        self.clear()
                        return False

        return True

    def write(self, path: str, indent: int = 2) -> bool:
        """Writes content to disk based on path specified.

        Content is a JSON file, so ideally you may wish to have `.json' as it's
        extension for clarity
        """
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.dict, f, indent=indent)

        except (TypeError, OSError):
            # Could not write content
            return False

        return True

    def json(self, indent: int = 2) -> str:
        """Returns JSON representation of the object."""
        return json.dumps(self.dict, indent=indent)
