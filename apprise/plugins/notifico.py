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

# Notifico allows you to relay notifications into IRC channels.
#
# The original hosted service (https://n.tkte.ch) has gone offline.
# The project is open source and can be self-hosted:
#   https://notifico.tech/
#
# Official/hosted-instance usage (project_id takes the host position):
#   1. Visit https://n.tkte.ch and sign up for an account.
#   2. Create a project; either manually or sync with GitHub.
#   3. From within the project, create a Plain Text Message Hook.
#
# The hook URL will look something like:
#       https://n.tkte.ch/h/2144/uJmKaBW9WFk42miB146ci3Kj
#                            ^                ^
#                            |                |
#                         project id       message hook
#
# To use the official endpoint with Apprise, the two path parts above
# become the arguments:
#   notifico://{ProjectID}/{MessageHook}
#
# To point Apprise at a self-hosted instance instead:
#   notifico://{host}/{ProjectID}/{MessageHook}      (HTTP)
#   notificos://{host}/{ProjectID}/{MessageHook}     (HTTPS)
#   notifico://{host}:{port}/{ProjectID}/{MessageHook}
#   notifico://{user}:{pass}@{host}/{ProjectID}/{MessageHook}
#
# This plugin also supports taking the n.tkte.ch URL directly as input.

import re

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_bool, validate_regex
from .base import NotifyBase


class NotificoMode:
    # Tracks the mode of operation for the Notifico plugin.

    # Notifications delivered via the official n.tkte.ch endpoint
    OFFICIAL = "official"

    # Notifications delivered via a self-hosted Notifico instance
    SELFHOSTED = "selfhosted"


# Define our Notifico Modes
NOTIFICO_MODES = (
    NotificoMode.OFFICIAL,
    NotificoMode.SELFHOSTED,
)


class NotificoFormat:
    # Resets all formatting
    Reset = "\x0f"

    # Formatting
    Bold = "\x02"
    Italic = "\x1d"
    Underline = "\x1f"
    BGSwap = "\x16"


class NotificoColor:
    # Resets Color
    Reset = "\x03"

    # Colors
    White = "\x0300"
    Black = "\x0301"
    Blue = "\x0302"
    Green = "\x0303"
    Red = "\x0304"
    Brown = "\x0305"
    Purple = "\x0306"
    Orange = "\x0307"
    Yellow = ("\x0308",)
    LightGreen = "\x0309"
    Teal = "\x0310"
    LightCyan = "\x0311"
    LightBlue = "\x0312"
    Violet = "\x0313"
    Grey = "\x0314"
    LightGrey = "\x0315"


class NotifyNotifico(NotifyBase):
    """A wrapper for Notifico Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Notifico"

    # The services URL
    service_url = "https://notifico.tech/"

    # The default protocol (HTTP -- used for self-hosted instances and
    # also as the schema for official-mode URLs)
    protocol = "notifico"

    # The default secure protocol (HTTPS -- self-hosted instances only)
    secure_protocol = "notificos"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/notifico/"

    # Official Notifico webhook endpoint
    notify_url = "https://n.tkte.ch/h/{proj}/{hook}"

    # The title is not used
    title_maxlen = 0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 512

    # Define object templates
    templates = (
        # Official endpoint: project_id takes the host position
        "{schema}://{project_id}/{msghook}",
        # Self-hosted variants (HTTP or HTTPS)
        "{schema}://{host}/{project_id}/{msghook}",
        "{schema}://{host}:{port}/{project_id}/{msghook}",
        "{schema}://{user}@{host}/{project_id}/{msghook}",
        "{schema}://{user}@{host}:{port}/{project_id}/{msghook}",
        "{schema}://{user}:{password}@{host}/{project_id}/{msghook}",
        "{schema}://{user}:{password}@{host}:{port}/{project_id}/{msghook}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            # Self-hosted connection fields
            "host": {
                "name": _("Hostname"),
                "type": "string",
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
            "user": {
                "name": _("Username"),
                "type": "string",
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
            },
            # The Project ID is found as the first part of the URL
            #  /1234/........................
            "project_id": {
                "name": _("Project ID"),
                "type": "string",
                "required": True,
                "private": True,
                "regex": (r"^[0-9]+$", ""),
            },
            # The Message Hook follows the Project ID
            #  /..../AbCdEfGhIjKlMnOpQrStUvWX
            "msghook": {
                "name": _("Message Hook"),
                "type": "string",
                "required": True,
                "private": True,
                "regex": (r"^[a-z0-9]+$", "i"),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            # You can optionally pass IRC colors into the notification
            "color": {
                "name": _("IRC Colors"),
                "type": "bool",
                "default": True,
            },
            # You can optionally include a notification-type prefix
            "prefix": {
                "name": _("Prefix"),
                "type": "bool",
                "default": True,
            },
            # Backward-compatible query-string aliases
            "token": {
                "alias_of": "msghook",
            },
            "project": {
                "alias_of": "project_id",
            },
        },
    )

    def __init__(
        self,
        project_id,
        msghook,
        color=True,
        prefix=True,
        **kwargs,
    ):
        """Initialize Notifico Object."""
        super().__init__(**kwargs)

        # Assign our project id
        self.project_id = validate_regex(
            project_id,
            *self.template_tokens["project_id"]["regex"],
        )
        if not self.project_id:
            msg = (
                f"An invalid Notifico Project ID ({project_id}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Assign our message hook
        self.msghook = validate_regex(
            msghook,
            *self.template_tokens["msghook"]["regex"],
        )
        if not self.msghook:
            msg = (
                f"An invalid Notifico Message Token ({msghook}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Detect operating mode: self-hosted when a hostname is present
        self.mode = (
            NotificoMode.SELFHOSTED if self.host else NotificoMode.OFFICIAL
        )

        # Prefix messages with a [?] where ? identifies the message type
        # such as if it's an error, warning, info, or success
        self.prefix = prefix

        # Send IRC colors
        self.color = color

        return

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.mode,
            # host and port distinguish self-hosted instances;
            # both are None for the official endpoint
            self.host,
            self.port,
            self.project_id,
            self.msghook,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "color": "yes" if self.color else "no",
            "prefix": "yes" if self.prefix else "no",
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.mode == NotificoMode.OFFICIAL:
            # Official mode: project_id lives in the host position
            return "{schema}://{proj}/{hook}/?{params}".format(
                schema=self.protocol,
                proj=self.pprint(self.project_id, privacy, safe=""),
                hook=self.pprint(self.msghook, privacy, safe=""),
                params=NotifyNotifico.urlencode(params),
            )

        # Self-hosted mode: include hostname, optional port and credentials
        auth = ""

        # Determine Authentication
        if self.user and self.password:
            auth = "{user}:{password}@".format(
                user=NotifyNotifico.quote(self.user, safe=""),
                password=self.pprint(
                    self.password,
                    privacy,
                    mode=PrivacyMode.Secret,
                    safe="",
                ),
            )
        elif self.user:
            auth = "{user}@".format(
                user=NotifyNotifico.quote(self.user, safe=""),
            )

        default_port = 443 if self.secure else 80

        return "{schema}://{auth}{host}{port}/{proj}/{hook}/?{params}".format(
            schema=(self.secure_protocol if self.secure else self.protocol),
            auth=auth,
            host=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else f":{self.port}"
            ),
            proj=self.pprint(self.project_id, privacy, safe=""),
            hook=self.pprint(self.msghook, privacy, safe=""),
            params=NotifyNotifico.urlencode(params),
        )

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Notifico Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": (
                "application/x-www-form-urlencoded; charset=utf-8"
            ),
        }

        # Prepare our IRC color and type prefix token
        color = ""
        token = ""
        if notify_type == NotifyType.INFO:
            color = NotificoColor.Teal
            token = "i"

        elif notify_type == NotifyType.SUCCESS:
            color = NotificoColor.LightGreen
            token = "✔"

        elif notify_type == NotifyType.WARNING:
            color = NotificoColor.Orange
            token = "!"

        elif notify_type == NotifyType.FAILURE:
            color = NotificoColor.Red
            token = "✗"

        if self.color:
            # Colors were specified; allow IRC color codes to pass through
            # \g<1> is less ambiguous than \1
            body = re.sub(r"\\x03(\d{0,2})", r"\\x03\g<1>", body)

        else:
            # No colors; strip any IRC color codes to keep the text readable
            body = re.sub(r"\\x03(\d{1,2}(,[0-9]{1,2})?)?", r"", body)

        # Prepare our payload
        payload = {
            "payload": (
                body
                if not self.prefix
                else "{}[{}]{} {}{}{}: {}{}".format(
                    # Token [?] at the head
                    color if self.color else "",
                    token,
                    NotificoColor.Reset if self.color else "",
                    # App ID
                    NotificoFormat.Bold if self.color else "",
                    self.app_id,
                    NotificoFormat.Reset if self.color else "",
                    # Message body
                    body,
                    # Reset
                    NotificoFormat.Reset if self.color else "",
                )
            ),
        }

        # Build the notify URL
        if self.mode == NotificoMode.OFFICIAL:
            # Always use the official HTTPS endpoint
            notify_url = self.notify_url.format(
                proj=self.project_id,
                hook=self.msghook,
            )
            auth = None

        else:
            # Self-hosted: construct URL from host/port
            schema = "https" if self.secure else "http"
            notify_url = f"{schema}://{self.host}"
            if isinstance(self.port, int):
                notify_url += f":{self.port}"
            notify_url += f"/h/{self.project_id}/{self.msghook}"
            auth = (self.user, self.password or "") if self.user else None

        self.logger.debug(
            f"Notifico GET URL: {notify_url} "
            f"(cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Notifico Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.get(
                notify_url,
                auth=auth,
                params=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyNotifico.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Notifico notification: "
                    "{}{}error={}.".format(
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Return; we're done
                return False

            else:
                self.logger.info("Sent Notifico notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Notifico notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # Return; we're done
            return False

        return True

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Retrieve path entries for project_id / msghook extraction
        entries = NotifyNotifico.split_path(results["fullpath"])

        # Unquote the host field
        host = NotifyNotifico.unquote(results.get("host", "") or "")

        if re.match(r"^[0-9]+$", host):
            # Official mode: numeric host value is the project_id
            results["project_id"] = host
            # Clear all connection fields -- official mode always routes
            # to the hardcoded n.tkte.ch endpoint
            results["host"] = None
            results["port"] = None
            results["user"] = None
            results["password"] = None
            # First path segment is the message hook
            results["msghook"] = entries[0] if entries else None

        else:
            # Self-hosted mode: host is the server; path carries the IDs
            results["project_id"] = entries[0] if entries else None
            results["msghook"] = entries[1] if len(entries) > 1 else None

        # Support ?token= as an alias for msghook
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["msghook"] = NotifyNotifico.unquote(
                results["qsd"]["token"]
            )

        # Support ?project= as an alias for project_id
        if "project" in results["qsd"] and results["qsd"]["project"]:
            results["project_id"] = NotifyNotifico.unquote(
                results["qsd"]["project"]
            )

        # Include Color option
        results["color"] = parse_bool(results["qsd"].get("color", True))

        # Include Prefix option
        results["prefix"] = parse_bool(results["qsd"].get("prefix", True))

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://n.tkte.ch/h/PROJ_ID/MESSAGE_HOOK/
        """

        result = re.match(
            r"^https?://n\.tkte\.ch/h/"
            r"(?P<proj>[0-9]+)/"
            r"(?P<hook>[A-Z0-9]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifyNotifico.parse_url(
                "{schema}://{proj}/{hook}/{params}".format(
                    schema=NotifyNotifico.protocol,
                    proj=result.group("proj"),
                    hook=result.group("hook"),
                    params=(
                        ""
                        if not result.group("params")
                        else result.group("params")
                    ),
                )
            )

        return None
