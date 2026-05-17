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

# Sign-up at https://ringcentral.com
#
# Create a server/bot app in the developer portal:
#  https://developers.ringcentral.com/
#
# Steps:
#  1. Log in and click "Create App".
#  2. Choose "REST API App" -> "Server/Bot (No UI)".
#  3. Under permissions enable "SMS" and "MMS" (MMS is needed for
#     attachment support -- Apprise selects MMS automatically when
#     attachments are present).
#  4. Copy the Client ID and Client Secret from the app credentials tab.
#
# Two authentication modes are supported:
#
# BASIC (password) mode -- use a RingCentral user password:
#   ringc://SourcePhoneNo:Password@ClientID/ClientSecret
#   ringc://SourcePhoneNo:Password@ClientID/ClientSecret/ToPhoneNo
#   ringc://SourcePhoneNo:Password@ClientID/ClientSecret/To1/To2/ToN
#
# JWT mode -- use a JWT token generated in the developer portal:
#   ringc://SourcePhoneNo:JWTToken@ClientID/ClientSecret
#   ringc://SourcePhoneNo:JWTToken@ClientID/ClientSecret/ToPhoneNo
#
# Alternatively, supply credentials as query parameters:
#   ringc://_?token=JWT&secret=ClientSecret&from=SourcePhoneNo
#
# When attachments are provided, Apprise automatically uses the MMS
# endpoint; otherwise SMS is used.
#
# API references:
# - https://developers.ringcentral.com/api-reference/SMS/createSMSMessage
# - https://developers.ringcentral.com/api-reference/MMS/createMMSMessage
# - https://developers.ringcentral.com/api-reference/OAuth-2.0/getToken

import base64
import contextlib
from json import dumps, loads
from time import time

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from .base import NotifyBase


class RingCentralAuthMode:
    """Authentication modes supported by RingCentral."""

    # Username + password credential flow
    BASIC = "basic"

    # JWT bearer token credential flow
    JWT = "jwt"


# Valid auth mode choices
RINGCENTRAL_AUTH_MODES = (
    RingCentralAuthMode.BASIC,
    RingCentralAuthMode.JWT,
)


class RingCentralEnvironment:
    """RingCentral API environment targets."""

    # Live production environment
    PRODUCTION = "prod"

    # Sandbox / devtest environment
    SANDBOX = "sandbox"


# Valid environment choices
RINGCENTRAL_ENVIRONMENTS = (
    RingCentralEnvironment.PRODUCTION,
    RingCentralEnvironment.SANDBOX,
)

# Maps environment choice to the URL infix used by the API
RINGCENTRAL_ENV_URL_SUFFIX = {
    RingCentralEnvironment.PRODUCTION: "",
    RingCentralEnvironment.SANDBOX: ".devtest",
}


class NotifyRingCentral(NotifyBase):
    """A wrapper for RingCentral Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "RingCentral"

    # The services URL
    service_url = "https://ringcentral.com/"

    # The default protocol
    secure_protocol = "ringc"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/ringcentral/"

    # Attachments are supported; MMS is selected automatically when present
    attachment_support = True

    # SMS endpoint (environment is substituted at send time)
    notify_url_sms = (
        "https://platform{environment}.ringcentral.com/"
        "restapi/v1.0/account/~/extension/~/sms"
    )

    # MMS endpoint (used automatically when attachments are present)
    notify_url_mms = (
        "https://platform{environment}.ringcentral.com/"
        "restapi/v1.0/account/~/extension/~/mms"
    )

    # OAuth token endpoint
    access_token_url = (
        "https://platform{environment}.ringcentral.com/restapi/oauth/token"
    )

    # Token revocation endpoint
    revoke_token_url = (
        "https://platform{environment}.ringcentral.com/restapi/oauth/revoke"
    )

    # Access token lifetime in seconds (60 minutes)
    access_token_ttl = 3600

    # Refresh token lifetime in seconds (1 week)
    refresh_token_ttl = 604800

    # SMS body length limit
    body_maxlen = 160

    # Titles are not supported; prepend to body instead
    title_maxlen = 0

    # Define object URL templates
    templates = (
        # source:token@client_id/secret (no targets -- loopback to source)
        "{schema}://{from_phone}:{token}@{client_id}/{secret}/",
        # source:token@client_id/secret/target[/target...]
        "{schema}://{from_phone}:{token}@{client_id}/{secret}/{targets}",
        # token@client_id/secret/source (source in path, JWT/password first)
        "{schema}://{token}@{client_id}/{secret}/{from_phone}",
        # token@client_id/secret/source/target[/target...]
        "{schema}://{token}@{client_id}/{secret}/{from_phone}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Token / Password"),
                "type": "string",
                "required": True,
                "private": True,
            },
            "client_id": {
                "name": _("Client ID"),
                "type": "string",
                "required": True,
                "regex": (r"^[a-z0-9_-]+$", "i"),
                "private": True,
            },
            "secret": {
                "name": _("Client Secret"),
                "type": "string",
                "required": True,
                "regex": (r"^[a-z0-9_-]+$", "i"),
                "private": True,
                "map_to": "client_secret",
            },
            "from_phone": {
                "name": _("From Phone No"),
                "type": "string",
                "required": True,
                "map_to": "source",
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
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
            "to": {
                "alias_of": "targets",
            },
            "from": {
                "alias_of": "from_phone",
            },
            "source": {
                "alias_of": "from_phone",
            },
            "env": {
                "name": _("Environment"),
                "type": "choice:string",
                "values": RINGCENTRAL_ENVIRONMENTS,
                "default": RingCentralEnvironment.PRODUCTION,
                "map_to": "environment",
            },
            "token": {
                "alias_of": "token",
            },
            "secret": {
                "alias_of": "secret",
            },
            "mode": {
                "name": _("Authentication Mode"),
                "type": "choice:string",
                "values": RINGCENTRAL_AUTH_MODES,
                "map_to": "mode",
            },
        },
    )

    def __init__(
        self,
        source,
        targets=None,
        environment=None,
        token=None,
        client_id=None,
        client_secret=None,
        mode=None,
        **kwargs,
    ):
        """Initialize RingCentral Object."""
        super().__init__(**kwargs)

        # Internal OAuth state
        self._access_token = None
        self._expire_time = 0.0
        self._scope = None
        self._owner = None
        self._endpoint_id = None

        # Resolve authentication mode
        if isinstance(mode, str):
            _mode = mode.lower().strip()
            match = (
                next(
                    (m for m in RINGCENTRAL_AUTH_MODES if m.startswith(_mode)),
                    None,
                )
                if _mode
                else None
            )

            if not match:
                msg = (
                    "An invalid RingCentral Authentication Mode "
                    "({}) was specified.".format(mode)
                )
                self.logger.warning(msg)
                raise TypeError(msg)

            # Store resolved mode
            self.mode = match

        else:
            # Default to BASIC (password) auth
            self.mode = RingCentralAuthMode.BASIC

        # Validate Client ID
        self.client_id = validate_regex(
            client_id, *self.template_tokens["client_id"]["regex"]
        )
        if not self.client_id:
            msg = (
                "An invalid RingCentral Client ID ({}) was specified.".format(
                    client_id
                )
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate Client Secret
        self.client_secret = validate_regex(
            client_secret, *self.template_tokens["secret"]["regex"]
        )
        if not self.client_secret:
            msg = (
                "An invalid RingCentral Client Secret "
                "({}) was specified.".format(client_secret)
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate JWT token (only strict regex check in JWT mode)
        if self.mode == RingCentralAuthMode.JWT:
            self.token = validate_regex(token, r"^[a-z0-9._-]+$", "i")
            if not self.token:
                msg = (
                    "An invalid RingCentral JWT Token "
                    "({}) was specified.".format(token)
                )
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            # BASIC mode -- token holds the user password (not validated)
            self.token = token

        # Validate source (sender) phone number
        result = is_phone_no(source)
        if not result:
            msg = (
                "The RingCentral source (From) phone # "
                "({}) is invalid.".format(source)
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store normalised source digits only
        self.source = result["full"]

        # Resolve environment
        _environment = (
            environment.lower().strip()
            if isinstance(environment, str)
            else RingCentralEnvironment.PRODUCTION
        )
        match = (
            next(
                (
                    e
                    for e in RINGCENTRAL_ENVIRONMENTS
                    if e.startswith(_environment)
                ),
                None,
            )
            if _environment
            else None
        )
        if not match:
            msg = (
                "An invalid RingCentral environment "
                "({}) was specified.".format(environment)
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store resolved environment
        self.environment = match

        # Parse target phone numbers, dropping invalid ones
        self.targets = []
        for target in parse_phone_no(targets):
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    "Dropped invalid RingCentral phone # (%s) specified.",
                    target,
                )
                continue

            # Store normalised digits
            self.targets.append(result["full"])

        return

    def login(self):
        """Authenticate with the RingCentral OAuth token endpoint."""

        if self._expire_time >= time():
            # Already authenticated
            return True

        # Build the token request URL
        url = self.access_token_url.format(
            environment=RINGCENTRAL_ENV_URL_SUFFIX[self.environment],
        )

        # Encode client credentials for Basic auth header
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic {}".format(
                str(
                    base64.b64encode(
                        bytes(
                            self.client_id + ":" + self.client_secret,
                            "utf8",
                        )
                    ),
                    "utf8",
                )
            ),
        }

        # Clear any stale token state
        self._access_token = None
        self._scope = None
        self._owner = None
        self._endpoint_id = None

        # Build grant payload for the selected auth mode
        if self.mode == RingCentralAuthMode.JWT:
            payload = {
                "grant_type": ("urn:ietf:params:oauth:grant-type:jwt-bearer"),
                "assertion": self.token,
            }
        else:
            # BASIC password grant
            payload = {
                "grant_type": "password",
                "username": "+" + self.source,
                "password": self.token,
                "access_token_ttl": self.access_token_ttl,
                "refresh_token_ttl": self.refresh_token_ttl,
            }

        # Send authentication request (no throttle for auth calls)
        status, response = self._send(
            url,
            payload,
            headers,
            name="auth.login",
            throttle=False,
        )

        if status:
            # Store token and expiry
            self._access_token = response.get("access_token")
            self._expire_time = time() + response.get("expires_in", 0)
            self._scope = response.get("scope")
            self._owner = response.get("owner_id")
            self._endpoint_id = response.get("endpoint_id")

        # A 200 OK without an access_token is not a usable login
        return bool(self._access_token)

    def logout(self):
        """Revoke the current access token."""

        if not self._access_token or self._expire_time < time():
            # Nothing to revoke
            return

        # Build the revocation URL
        url = self.revoke_token_url.format(
            environment=RINGCENTRAL_ENV_URL_SUFFIX[self.environment],
        )

        # Encode client credentials
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic {}".format(
                str(
                    base64.b64encode(
                        bytes(
                            self.client_id + ":" + self.client_secret,
                            "utf8",
                        )
                    ),
                    "utf8",
                )
            ),
        }

        # Revocation payload
        payload = {"token": self._access_token}

        # Send revocation request (no throttle for auth calls)
        self._send(
            url,
            payload,
            headers,
            name="auth.logout",
            throttle=False,
        )

        # Clear token state
        self._access_token = None
        self._expire_time = 0.0
        self._scope = None
        self._owner = None
        self._endpoint_id = None

        return

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform RingCentral Notification."""

        # Error tracking across multiple targets
        has_error = False

        # Authenticate before sending
        if not self.login():
            self.logger.warning(
                "RingCentral %s authentication failed.", self.mode
            )
            return False

        # Bearer auth header token (reused across send calls)
        auth_header = "Bearer {}".format(self._access_token)

        # Auto-select MMS when attachments are present, SMS otherwise
        use_mms = bool(attach and self.attachment_support and len(attach))

        # Build the endpoint URL for the selected message type
        if use_mms:
            notify_url = self.notify_url_mms.format(
                environment=RINGCENTRAL_ENV_URL_SUFFIX[self.environment],
            )
        else:
            notify_url = self.notify_url_sms.format(
                environment=RINGCENTRAL_ENV_URL_SUFFIX[self.environment],
            )

        # If no targets specified, send to own number (loopback test)
        targets = list(self.targets) if self.targets else [self.source]

        for target in targets:
            # Message metadata for this recipient
            metadata = {
                "from": {"phoneNumber": "+" + self.source},
                "to": [{"phoneNumber": "+" + target}],
                "text": body,
            }

            if use_mms:
                # MMS: multipart/form-data -- JSON metadata + attachments
                # Content-Type is set automatically by requests for multipart
                headers = {
                    "Authorization": auth_header,
                }
                files = [
                    (
                        "json",
                        (None, dumps(metadata), "application/json"),
                    ),
                ]

                # Track opened handles for guaranteed cleanup
                handles = []
                attach_ok = True

                try:
                    # Build attachment parts; abort target on first failure
                    for attachment in attach:
                        # Verify the attachment is accessible
                        if not attachment:
                            self.logger.warning(
                                "Could not access RingCentral attachment %s.",
                                attachment.url(privacy=True),
                            )
                            attach_ok = False
                            break

                        # Open handle; guard against I/O errors
                        try:
                            handle = attachment.open()
                        except OSError as exc:
                            self.logger.warning(
                                "An I/O error occurred reading "
                                "RingCentral attachment %s.",
                                attachment.name,
                            )
                            self.logger.debug("I/O Exception: %s", str(exc))
                            attach_ok = False
                            break

                        # Register handle for cleanup
                        handles.append(handle)
                        # Append the attachment part
                        files.append(
                            (
                                "attachment",
                                (
                                    attachment.name,
                                    handle,
                                    attachment.mimetype,
                                ),
                            )
                        )

                    if not attach_ok:
                        # Skip this target; mark overall failure
                        has_error = True
                        continue

                    # Send MMS notification (multipart)
                    status, _ = self._send(
                        notify_url, None, headers, files=files
                    )

                finally:
                    # Close all handles whether we succeeded or failed
                    for handle in handles:
                        handle.close()

            else:
                # SMS: plain JSON payload
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": auth_header,
                }
                status, _ = self._send(notify_url, dumps(metadata), headers)

            if status:
                self.logger.info(
                    "Sent RingCentral notification to %s.", target
                )
            else:
                # Mark failure and continue to remaining targets
                has_error = True

        return not has_error

    def _send(
        self,
        url,
        payload,
        headers,
        name="notification",
        throttle=True,
        files=None,
    ):
        """POST helper shared by login, logout, and send calls."""

        headers.update(
            {
                # Minimum required headers
                "User-Agent": self.app_id,
                "Accept": "application/json",
            }
        )

        self.logger.debug(
            "RingCentral POST URL: %s (cert_verify=%s)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("RingCentral Payload: %s", payload)

        if throttle:
            # Throttle notification calls; auth calls skip this
            self.throttle()

        content = None
        try:
            r = requests.post(
                url,
                data=payload,
                headers=headers,
                files=files,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            self.logger.trace("RingCentral Response: %s", r.content)

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

            if r.status_code != requests.codes.ok:
                # We had a failure
                status_str = NotifyRingCentral.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send RingCentral %s: %s%serror=%s.",
                    name,
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )
                self.logger.debug("Response Details:\r\n%s", r.content)

            else:
                # We were successful
                return (True, content)

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending RingCentral %s.",
                name,
            )
            self.logger.debug("Socket Exception: %s", str(e))

        return (False, content)

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.client_id,
            self.client_secret,
            self.token,
            self.source,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "env": str(self.environment),
            "mode": str(self.mode),
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return (
            "{schema}://{source}:{token}@{client_id}"
            "/{client_secret}/{targets}/?{params}".format(
                schema=self.secure_protocol,
                source=NotifyRingCentral.quote(self.source, safe=""),
                token=self.pprint(
                    self.token,
                    privacy,
                    mode=(
                        PrivacyMode.Secret
                        if self.mode == RingCentralAuthMode.BASIC
                        else PrivacyMode.Outer
                    ),
                    safe="",
                ),
                client_id=self.pprint(self.client_id, privacy, safe=""),
                client_secret=self.pprint(
                    self.client_secret,
                    privacy,
                    mode=PrivacyMode.Secret,
                    safe="",
                ),
                targets="/".join(
                    NotifyRingCentral.quote(x, safe="") for x in self.targets
                ),
                params=NotifyRingCentral.urlencode(params),
            )
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return len(self.targets) if self.targets else 1

    def __del__(self):
        """Destructor -- revoke the auth token on cleanup."""
        with contextlib.suppress(Exception):
            self.logout()

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Path elements: first segment is client_secret, rest are targets
        results["targets"] = NotifyRingCentral.split_path(results["fullpath"])

        # Host is the client_id
        results["client_id"] = NotifyRingCentral.unquote(results["host"])

        # First path segment is the client_secret
        results["client_secret"] = (
            results["targets"].pop(0) if results["targets"] else None
        )

        # Determine source phone and token from URL user[:password] form
        if not results.get("password"):
            # ringc://token@client_id/secret/source_phone[/targets]
            results["source"] = (
                results["targets"].pop(0) if results["targets"] else None
            )
            results["token"] = NotifyRingCentral.unquote(results["user"])
        else:
            # ringc://source_phone:token@client_id/secret[/targets]
            results["source"] = NotifyRingCentral.unquote(results["user"])
            results["token"] = NotifyRingCentral.unquote(results["password"])

        # Environment (from ?env= query parameter)
        if "env" in results["qsd"] and results["qsd"]["env"]:
            results["environment"] = NotifyRingCentral.unquote(
                results["qsd"]["env"]
            )

        # ?token= overrides the token extracted from the URL path;
        # must be applied before mode auto-detection so that a JWT
        # supplied via query parameter is detected correctly
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyRingCentral.unquote(
                results["qsd"]["token"]
            )

        # Auth mode: ?mode= wins; otherwise auto-detect from token length
        if "mode" in results["qsd"] and results["qsd"]["mode"]:
            results["mode"] = NotifyRingCentral.unquote(results["qsd"]["mode"])
        elif results.get("token") and len(results["token"]) > 60:
            # JWT tokens are significantly longer than passwords
            results["mode"] = RingCentralAuthMode.JWT
        else:
            results["mode"] = RingCentralAuthMode.BASIC

        # ?secret= overrides the client secret extracted from the path
        if "secret" in results["qsd"] and results["qsd"]["secret"]:
            results["client_secret"] = NotifyRingCentral.unquote(
                results["qsd"]["secret"]
            )

        # ?from= / ?source= override source phone number
        if "from" in results["qsd"] and results["qsd"]["from"]:
            results["source"] = NotifyRingCentral.unquote(
                results["qsd"]["from"]
            )
        if "source" in results["qsd"] and results["qsd"]["source"]:
            results["source"] = NotifyRingCentral.unquote(
                results["qsd"]["source"]
            )

        # ?to= appends additional target phone numbers
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifyRingCentral.parse_phone_no(
                results["qsd"]["to"]
            )

        return results
