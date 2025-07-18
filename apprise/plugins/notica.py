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

# 1. Simply visit https://notica.us
# 2. You'll be provided a new variation of the website which will look
#    something like: https://notica.us/?abc123.
#                                         ^
#                                         |
#                                       token
#
#    Your token is actually abc123 (do not include/grab the question mark)
#    You can use that URL as is directly in Apprise, or you can follow
#    the next step which shows you how to assemble the Apprise URL:
#
# 3. With respect to the above, your apprise URL would be:
#       notica://abc123
#
import re

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import validate_regex
from .base import NotifyBase


class NoticaMode:
    """Tracks if we're accessing the notica upstream server or a locally hosted
    one."""

    # We're dealing with a self hosted service
    SELFHOSTED = "selfhosted"

    # We're dealing with the official hosted service at https://notica.us
    OFFICIAL = "official"


# Define our Notica Modes
NOTICA_MODES = (
    NoticaMode.SELFHOSTED,
    NoticaMode.OFFICIAL,
)


class NotifyNotica(NotifyBase):
    """A wrapper for Notica Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Notica"

    # The services URL
    service_url = "https://notica.us/"

    # Insecure protocol (for those self hosted requests)
    protocol = "notica"

    # The default protocol (this is secure for notica)
    secure_protocol = "noticas"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_notica"

    # Notica URL
    notify_url = "https://notica.us/?{token}"

    # Notica does not support a title
    title_maxlen = 0

    # Define object templates
    templates = (
        "{schema}://{token}",
        # Self-hosted notica servers
        "{schema}://{host}/{token}",
        "{schema}://{host}:{port}/{token}",
        "{schema}://{user}@{host}/{token}",
        "{schema}://{user}@{host}:{port}/{token}",
        "{schema}://{user}:{password}@{host}/{token}",
        "{schema}://{user}:{password}@{host}:{port}/{token}",
        # Self-hosted notica servers (with custom path)
        "{schema}://{host}{path}/{token}",
        "{schema}://{host}:{port}/{path}/{token}",
        "{schema}://{user}@{host}/{path}/{token}",
        "{schema}://{user}@{host}:{port}{path}/{token}",
        "{schema}://{user}:{password}@{host}{path}/{token}",
        "{schema}://{user}:{password}@{host}:{port}/{path}/{token}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": r"^\?*(?P<token>[^/]+)\s*$",
            },
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
            "path": {
                "name": _("Path"),
                "type": "string",
                "map_to": "fullpath",
                "default": "/",
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "headers": {
            "name": _("HTTP Header"),
            "prefix": "+",
        },
    }

    def __init__(self, token, headers=None, **kwargs):
        """Initialize Notica Object."""
        super().__init__(**kwargs)

        # Token (associated with project)
        self.token = validate_regex(token)
        if not self.token:
            msg = f"An invalid Notica Token ({token}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Setup our mode
        self.mode = NoticaMode.SELFHOSTED if self.host else NoticaMode.OFFICIAL

        # prepare our fullpath
        self.fullpath = kwargs.get("fullpath")
        if not isinstance(self.fullpath, str):
            self.fullpath = "/"

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Notica Notification."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # Prepare our payload
        payload = f"d:{body}"

        # Auth is used for SELFHOSTED queries
        auth = None

        if self.mode is NoticaMode.OFFICIAL:
            # prepare our notify url
            notify_url = self.notify_url.format(token=self.token)

        else:
            # Prepare our self hosted URL

            # Apply any/all header over-rides defined
            headers.update(self.headers)

            if self.user:
                auth = (self.user, self.password)

            # Set our schema
            schema = "https" if self.secure else "http"

            # Prepare our notify_url
            notify_url = f"{schema}://{self.host}"
            if isinstance(self.port, int):
                notify_url += f":{self.port}"

            notify_url += f"{self.fullpath}?token={self.token}"

        self.logger.debug(
            "Notica POST URL:"
            f" {notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Notica Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url.format(token=self.token),
                data=payload,
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyNotica.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Notica notification:{}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # Return; we're done
                return False

            else:
                self.logger.info("Sent Notica notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Notica notification.",
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
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.mode,
            self.token,
            self.user,
            self.password,
            self.host,
            self.port,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.mode == NoticaMode.OFFICIAL:
            # Official URLs are easy to assemble
            return "{schema}://{token}/?{params}".format(
                schema=self.protocol,
                token=self.pprint(self.token, privacy, safe=""),
                params=NotifyNotica.urlencode(params),
            )

        # If we reach here then we are assembling a self hosted URL

        # Append URL parameters from our headers
        params.update({f"+{k}": v for k, v in self.headers.items()})

        # Authorization can be used for self-hosted sollutions
        auth = ""

        # Determine Authentication
        if self.user and self.password:
            auth = "{user}:{password}@".format(
                user=NotifyNotica.quote(self.user, safe=""),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )
        elif self.user:
            auth = "{user}@".format(
                user=NotifyNotica.quote(self.user, safe=""),
            )

        default_port = 443 if self.secure else 80
        return (
            "{schema}://{auth}{hostname}{port}{fullpath}{token}/?{params}"
            .format(
                schema=self.secure_protocol if self.secure else self.protocol,
                auth=auth,
                hostname=NotifyNotica.quote(self.host, safe=""),
                port=(
                    ""
                    if self.port is None or self.port == default_port
                    else f":{self.port}"
                ),
                fullpath=NotifyNotica.quote(self.fullpath, safe="/"),
                token=self.pprint(self.token, privacy, safe=""),
                params=NotifyNotica.urlencode(params),
            )
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Get unquoted entries
        entries = NotifyNotica.split_path(results["fullpath"])
        if not entries:
            # If there are no path entries, then we're only dealing with the
            # official website
            results["mode"] = NoticaMode.OFFICIAL

            # Store our token using the host
            results["token"] = NotifyNotica.unquote(results["host"])

            # Unset our host
            results["host"] = None

        else:
            # Otherwise we're running a self hosted instance
            results["mode"] = NoticaMode.SELFHOSTED

            # The last element in the list is our token
            results["token"] = entries.pop()

            # Re-assemble our full path
            results["fullpath"] = (
                "/" if not entries else "/{}/".format("/".join(entries))
            )

            # Add our headers that the user can potentially over-ride if they
            # wish to to our returned result set and tidy entries by unquoting
            # them
            results["headers"] = {
                NotifyNotica.unquote(x): NotifyNotica.unquote(y)
                for x, y in results["qsd+"].items()
            }

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://notica.us/?abc123
        """

        result = re.match(
            r"^https?://notica\.us/?"
            r"\??(?P<token>[^&]+)([&\s]*(?P<params>.+))?$",
            url,
            re.I,
        )

        if result:
            return NotifyNotica.parse_url(
                "{schema}://{token}/{params}".format(
                    schema=NotifyNotica.protocol,
                    token=result.group("token"),
                    params=(
                        ""
                        if not result.group("params")
                        else "?{}".format(result.group("params"))
                    ),
                )
            )

        return None
