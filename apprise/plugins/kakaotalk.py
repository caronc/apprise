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

# To use this service you will need a Kakao Developers application:
#     https://developers.kakao.com/
#
#  1. Sign in to Kakao Developers and create an application.
#  2. Under App Keys, copy the REST API Key.  This is your Client ID.
#  3. Under Kakao Login, turn Kakao Login on and register a Redirect URI
#     (for example https://localhost/).
#  4. Under Kakao Login > Consent Items, enable "Send message in
#     KakaoTalk" (talk_message).
#  5. Under Kakao Login > Security, note the Client Secret if it is
#     enabled.
#  6. Open this address in a browser, sign in and agree:
#        https://kauth.kakao.com/oauth/authorize?response_type=code
#            &client_id={client_id}&redirect_uri={redirect_uri}
#            &scope=talk_message
#     The browser is sent to your Redirect URI with ?code= on the end.
#  7. Trade that code for your tokens:
#        curl -X POST https://kauth.kakao.com/oauth/token \
#           -d grant_type=authorization_code \
#           -d client_id={client_id} \
#           -d client_secret={client_secret} \
#           -d redirect_uri={redirect_uri} \
#           -d code={code}
#     Keep the refresh_token value from the response.
#
#  Your Apprise URL should be assembled as:
#     kakaotalk://{client_id}/{refresh_token}
#     kakaotalk://{client_secret}@{client_id}/{refresh_token}
#
#  With no target, the message is sent to yourself.  To reach friends,
#  add their UUIDs (from the friends list API) to the path.  Use "me"
#  to include yourself alongside them:
#     kakaotalk://{client_id}/{refresh_token}/{uuid}/{uuid}/me
#
#  You can shorten kakaotalk:// to kakao:// if you prefer.
#
#  The Message REST API only takes images by URL and has no file
#  upload, so attachments are not supported.
#
# Resources:
# - https://developers.kakao.com/docs/en/kakaotalk-message/rest-api
# - https://developers.kakao.com/docs/en/kakaologin/rest-api
# - https://developers.kakao.com/docs/en/message-template/default

from __future__ import annotations

from json import dumps, loads
from typing import Any, Optional

import requests

from ..common import NotifyFormat, NotifyType, PersistentStoreMode
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
KAKAOTALK_HTTP_ERROR_MAP = {
    400: "Bad Request - Check the Client ID, tokens and recipients.",
    401: "Unauthorized - The access token is invalid or expired.",
    403: "Forbidden - Message permission or consent is missing.",
    429: "Too many requests were made.",
}

# The target that stands for the token owner
KAKAOTALK_ME = "me"


class NotifyKakaoTalk(NotifyBase):
    """A wrapper for KakaoTalk Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "KakaoTalk"

    # The services URL
    service_url = "https://www.kakaocorp.com/"

    # The default secure protocol; kakao:// is a shorter alias
    secure_protocol = ("kakaotalk", "kakao")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/kakaotalk/"

    # Where our refresh token is traded for an access token
    token_url = "https://kauth.kakao.com/oauth/token"

    # Sends a message to the token owner
    notify_me_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

    # Sends a message to friends of the token owner
    notify_friend_url = (
        "https://kapi.kakao.com/v1/api/talk/friends/message/default/send"
    )

    # The text template holds at most 200 characters
    body_maxlen = 200

    # The text template has no title.  Setting this to zero will cause
    # any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # The text template only shows plain text
    notify_format = NotifyFormat.TEXT

    # Keep our tokens between runs when a storage path is available
    storage_mode = PersistentStoreMode.AUTO

    # Access token lifetime when one is not returned (12 hours)
    token_expiry = 43200

    # Renew our access token this many seconds before it expires
    token_expiry_edge = 60

    # The text template needs a link; this is what Kakao's own
    # examples use
    default_link = "https://developers.kakao.com"

    # Define object URL templates
    templates = (
        "{schema}://{client_id}/{refresh_token}",
        "{schema}://{client_id}/{refresh_token}/{targets}",
        "{schema}://{client_secret}@{client_id}/{refresh_token}",
        "{schema}://{client_secret}@{client_id}/{refresh_token}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "client_id": {
                "name": _("Client ID"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9]+$", "i"),
            },
            "client_secret": {
                "name": _("Client Secret"),
                "type": "string",
                "private": True,
                "regex": (r"^[a-z0-9]+$", "i"),
            },
            "refresh_token": {
                "name": _("Refresh Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9_-]+$", "i"),
            },
            "target_id": {
                "name": _("Target ID"),
                "type": "string",
                "regex": (r"^[a-z0-9_-]+$", "i"),
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
            "secret": {
                "alias_of": "client_secret",
            },
            "link": {
                "name": _("Link"),
                "type": "string",
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self,
        client_id: Optional[str] = None,
        refresh_token: Optional[str] = None,
        client_secret: Optional[str] = None,
        targets: Optional[Any] = None,
        link: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize KakaoTalk Object."""
        super().__init__(**kwargs)

        # Our Client ID (the REST API Key)
        self.client_id = validate_regex(
            client_id, *self.template_tokens["client_id"]["regex"]
        )
        if not self.client_id:
            msg = (
                f"An invalid KakaoTalk Client ID ({client_id}) was specified."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Our refresh token; it is traded for an access token at send time
        self.refresh_token = validate_regex(
            refresh_token, *self.template_tokens["refresh_token"]["regex"]
        )
        if not self.refresh_token:
            msg = (
                "An invalid KakaoTalk Refresh Token "
                f"({refresh_token}) was specified."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The Client Secret is only needed when the app has one enabled
        self.client_secret = None
        if client_secret:
            self.client_secret = validate_regex(
                client_secret, *self.template_tokens["client_secret"]["regex"]
            )
            if not self.client_secret:
                msg = (
                    "An invalid KakaoTalk Client Secret "
                    f"({client_secret}) was specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # Where a tap on the message takes the reader
        self.link = link.strip() if isinstance(link, str) else None

        # The friend UUIDs (and "me") we will notify
        self.targets = []

        # Anything we could not make sense of; kept for url()
        self.invalid_targets = []

        for target in parse_list(targets):
            # "me" is the token owner; anything else is a friend UUID
            if target.lower() == KAKAOTALK_ME:
                self.targets.append(KAKAOTALK_ME)
                continue

            result = validate_regex(
                target, *self.template_tokens["target_id"]["regex"]
            )
            if result:
                self.targets.append(result)
                continue

            self.logger.warning(
                "Dropped invalid KakaoTalk UUID (%s) specified.", target
            )
            self.invalid_targets.append(target)

        return

    def login(self) -> Optional[str]:
        """Trade our refresh token for an access token."""

        # Reset our cached access token
        self.store.clear("access_token")

        # Kakao may have handed us a newer refresh token on a past run
        refresh_token = self.store.get("refresh_token") or self.refresh_token

        # Prepare our payload
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": refresh_token,
        }

        if self.client_secret:
            payload["client_secret"] = self.client_secret

        status, response = self._fetch(
            self.token_url, payload, name="token request", throttle=False
        )

        # Go ahead and store our token if it's available
        access_token = response.get("access_token")
        if not (status and access_token):
            self.logger.warning("KakaoTalk could not obtain an access token.")
            return None

        try:
            # Renew a little early so a send never uses a stale token
            expires = int(response.get("expires_in")) - self.token_expiry_edge

        except (TypeError, ValueError):
            # expires_in was missing or not a number
            expires = self.token_expiry - self.token_expiry_edge

        self.store.set(
            "access_token",
            access_token,
            expires=max(expires, self.token_expiry_edge),
        )

        # Kakao returns a new refresh token once the old one has less than
        # a month left; the old one stops working, so keep the new one.
        if response.get("refresh_token"):
            try:
                expires = int(response.get("refresh_token_expires_in"))

            except (TypeError, ValueError):
                # No lifetime was given; keep it until it is replaced
                expires = None

            self.store.set(
                "refresh_token", response["refresh_token"], expires=expires
            )

        # We're authenticated
        return access_token

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform KakaoTalk Notification."""

        # Use our cached access token, or fetch a new one
        access_token = self.store.get("access_token") or self.login()
        if not access_token:
            return False

        # Prepare our text template; a link is required by Kakao
        link = self.link or self.default_link
        template = {
            "object_type": "text",
            "text": body,
            "link": {
                "web_url": link,
                "mobile_web_url": link,
            },
        }

        # Prepare our headers
        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        # error tracking (used for function return)
        has_error = False

        # With no targets, the message goes to the token owner
        for target in self.targets or [KAKAOTALK_ME]:
            # Skip a target that already accepted this message so a
            # retry does not deliver it twice.
            if self.is_delivered(target):
                continue

            # Prepare our payload
            payload = {"template_object": dumps(template)}

            if target == KAKAOTALK_ME:
                # Message ourselves
                url = self.notify_me_url

            else:
                # Message one friend
                url = self.notify_friend_url
                payload["receiver_uuids"] = dumps([target])

            status, _response = self._fetch(
                url, payload, headers=headers, name=f"message to {target}"
            )
            if not status:
                # Mark our failure
                has_error = True
                continue

            self.logger.info("Sent KakaoTalk notification to %s.", target)

            # Delivered; a retry can safely skip this target.
            self.mark_delivered(target)

        return not has_error

    def _fetch(
        self,
        url: str,
        payload: dict[str, str],
        headers: Optional[dict[str, str]] = None,
        name: str = "notification",
        throttle: bool = True,
    ) -> tuple[bool, dict[str, Any]]:
        """POST helper shared by the token and message calls."""

        # Merge in the minimum required headers
        headers = dict(headers or {})
        headers.update(
            {
                "User-Agent": self.app_id,
                "Accept": "application/json",
            }
        )

        self.logger.debug(
            "KakaoTalk POST URL: %s (cert_verify=%r)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("KakaoTalk Payload: %s", payload)

        if throttle:
            # Token calls skip this; message calls are rate limited
            self.throttle()

        try:
            r = requests.post(
                url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # The response was not JSON; rely on the status code
                content = {}

            if not isinstance(content, dict):
                content = {}

            if r.status_code != requests.codes.ok:
                # An expired or revoked token is fetched again next time
                if r.status_code == requests.codes.unauthorized:
                    self.store.clear("access_token")

                # Prefer Kakao's own explanation when it gave one; the
                # token server and the message server name it differently
                status_str = (
                    content.get("msg")
                    or content.get("error_description")
                    or NotifyKakaoTalk.http_response_code_lookup(
                        r.status_code, KAKAOTALK_HTTP_ERROR_MAP
                    )
                )

                self.logger.warning(
                    "Failed to send KakaoTalk %s: %s%serror=%s.",
                    name,
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )
                return (False, content)

            # We were successful
            return (True, content)

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending KakaoTalk %s.", name
            )
            self.logger.debug("Socket Exception: %s", str(e))

        return (False, {})

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Always return at least 1 so the framework counts this instance
        return len(self.targets) if self.targets else 1

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The app and the account that signed in identify the connection
        return (
            self.secure_protocol[0],
            self.client_id,
            self.client_secret,
            self.refresh_token,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = {}

        if self.link:
            params["link"] = self.link

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # The Client Secret is optional
        secret = (
            "{}@".format(self.pprint(self.client_secret, privacy, safe=""))
            if self.client_secret
            else ""
        )

        return "{schema}://{secret}{cid}/{token}/{targets}?{params}".format(
            schema=self.secure_protocol[0],
            secret=secret,
            cid=self.pprint(self.client_id, privacy, safe=""),
            token=self.pprint(self.refresh_token, privacy, safe=""),
            targets="/".join(
                NotifyKakaoTalk.quote(x, safe="")
                for x in (self.targets + self.invalid_targets)
            ),
            params=NotifyKakaoTalk.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The host is our Client ID
        results["client_id"] = NotifyKakaoTalk.unquote(results["host"])

        # The optional Client Secret sits in front of the @
        if results["user"]:
            results["client_secret"] = NotifyKakaoTalk.unquote(results["user"])

        # The first path entry is our refresh token; the rest are targets
        entries = NotifyKakaoTalk.split_path(results["fullpath"])
        results["refresh_token"] = entries.pop(0) if entries else None
        results["targets"] = entries

        # Allow the Client Secret to be given as ?secret= instead
        if results["qsd"].get("secret"):
            results["client_secret"] = NotifyKakaoTalk.unquote(
                results["qsd"]["secret"]
            )

        # Support ?link= for where a tap on the message goes
        if results["qsd"].get("link"):
            results["link"] = NotifyKakaoTalk.unquote(results["qsd"]["link"])

        # Support ?to= for targets
        if results["qsd"].get("to"):
            results["targets"] += NotifyKakaoTalk.parse_list(
                results["qsd"]["to"]
            )

        return results
