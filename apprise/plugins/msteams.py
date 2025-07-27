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

# To use this plugin, you need to create a webhook; you can read more about
# this here:
#    https://dev.outlook.com/Connectors/\
#       GetStarted#creating-messages-through-office-365-connectors-\
#           in-microsoft-teams
#
# More details are here on API Construction:
#    https://docs.microsoft.com/en-ca/outlook/actionable-messages/\
#        message-card-reference
#
# I personally created a free account at teams.microsoft.com and then
# went to the store (bottom left hand side of slack like interface).
#
# From here you can search for 'Incoming Webhook'. Once you click on it,
# you can associate the webhook with your team. At this point, you can
# optionally also assign it a name, an avatar.  Finally you'll have to
# assign it a channel it will notify.
#
# When you've completed this, it will generate you a (webhook) URL that
# looks like:
#   https://team-name.webhook.office.com/webhookb2/ \
#       abcdefgf8-2f4b-4eca-8f61-225c83db1967@abcdefg2-5a99-4849-8efc-\
#        c9e78d28e57d/IncomingWebhook/291289f63a8abd3593e834af4d79f9fe/\
#          a2329f43-0ffb-46ab-948b-c9abdad9d643
#
# Yes... The URL is that big... But it looks like this (greatly simplified):
# https://TEAM-NAME.webhook.office.com/webhookb2/ABCD/IncomingWebhook/DEFG/HIJK
#             ^                                   ^                    ^    ^
#             |                                   |                    |    |
#  These are important <--------------------------^--------------------^----^
#

# The Legacy format didn't have the team name identified and reads 'outlook'
# While this still works, consider that Microsoft will be dropping support
# for this soon, so you may need to update your IncomingWebhook. Here is
# what a legacy URL looked like:
# https://outlook.office.com/webhook/ABCD/IncomingWebhook/DEFG/HIJK
#           ^                         ^                    ^    ^
#           |                         |                    |    |
#   legacy team reference: 'outlook'  |                    |    |
#                                     |                    |    |
#  These are important <--------------^--------------------^----^
#

# You'll notice that the first token is actually 2 separated by an @ symbol
# But lets just ignore that and assume it's one great big token instead.
#
# These 3 tokens need to be placed in the URL after the Team
#   msteams://TEAM/ABCD/DEFG/HIJK
#
import json
from json.decoder import JSONDecodeError
import re

import requests

from ..apprise_attachment import AppriseAttachment
from ..common import NotifyFormat, NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool, validate_regex
from ..utils.templates import TemplateType, apply_template
from .base import NotifyBase


class NotifyMSTeams(NotifyBase):
    """A wrapper for Microsoft Teams Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "MSTeams"

    # The services URL
    service_url = "https://teams.micrsoft.com/"

    # The default secure protocol
    secure_protocol = "msteams"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_msteams"

    # MSTeams uses the http protocol with JSON requests
    notify_url_v1 = (
        "https://outlook.office.com/webhook/"
        "{token_a}/IncomingWebhook/{token_b}/{token_c}"
    )

    # New MSTeams webhook (as of April 11th, 2021)
    notify_url_v2 = (
        "https://{team}.webhook.office.com/webhookb2/"
        "{token_a}/IncomingWebhook/{token_b}/{token_c}"
    )

    notify_url_v3 = (
        "https://{team}.webhook.office.com/webhookb2/"
        "{token_a}/IncomingWebhook/{token_b}/{token_c}/{token_d}"
    )

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    # Default Notification Format
    notify_format = NotifyFormat.MARKDOWN

    # There is no reason we should exceed 35KB when reading in a JSON file.
    # If it is more than this, then it is not accepted
    max_msteams_template_size = 35000

    # Define object templates
    templates = (
        # New required format
        "{schema}://{team}/{token_a}/{token_b}/{token_c}",
        # Deprecated
        "{schema}://{token_a}/{token_b}/{token_c}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            # The Microsoft Team Name
            "team": {
                "name": _("Team Name"),
                "type": "string",
                "required": True,
                "regex": (r"^[A-Z0-9_-]+$", "i"),
            },
            # Token required as part of the API request
            #  /AAAAAAAAA@AAAAAAAAA/........./.........
            "token_a": {
                "name": _("Token A"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[A-Z0-9-]+@[A-Z0-9-]+$", "i"),
            },
            # Token required as part of the API request
            #  /................../BBBBBBBBB/..........
            "token_b": {
                "name": _("Token B"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9]+$", "i"),
            },
            # Token required as part of the API request
            #  /........./........./CCCCCCCCCCCCCCCCCCCCCCCC
            "token_c": {
                "name": _("Token C"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9-]+$", "i"),
            },
            # Token required as part of the API request
            #  /........./........./........./DDDDDDDDDDDDDDDDD
            "token_d": {
                "name": _("Token D"),
                "type": "string",
                "private": True,
                "required": False,
                "regex": (r"^V2[a-zA-Z0-9-_]+$", "i"),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": False,
                "map_to": "include_image",
            },
            "version": {
                "name": _("Version"),
                "type": "choice:int",
                "values": (1, 2, 3),
                "default": 2,
            },
            "template": {
                "name": _("Template Path"),
                "type": "string",
                "private": True,
            },
        },
    )

    # Define our token control
    template_kwargs = {
        "tokens": {
            "name": _("Template Tokens"),
            "prefix": ":",
        },
    }

    def __init__(
        self,
        token_a,
        token_b,
        token_c,
        token_d=None,
        team=None,
        version=None,
        include_image=True,
        template=None,
        tokens=None,
        **kwargs,
    ):
        """Initialize Microsoft Teams Object.

        You can optional specify a template and identify arguments you
        wish to populate your template with when posting.  Some reserved
        template arguments that can not be over-ridden are:
           `body`, `title`, and `type`.
        """
        super().__init__(**kwargs)

        try:
            self.version = int(version)

        except TypeError:
            # None was specified... take on default
            self.version = self.template_args["version"]["default"]

        except ValueError:
            # invalid content was provided; let this get caught in the next
            # validation check for the version
            self.version = None

        if self.version not in self.template_args["version"]["values"]:
            msg = f"An invalid MSTeams Version ({version}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.team = validate_regex(team)
        if not self.team:
            NotifyBase.logger.deprecate(
                "Apprise requires you to identify your Microsoft Team name as "
                "part of the URL. e.g.: "
                "msteams://TEAM-NAME/{token_a}/{token_b}/{token_c}"
            )

            # Fallback
            self.team = "outlook"

        self.token_a = validate_regex(
            token_a, *self.template_tokens["token_a"]["regex"]
        )
        if not self.token_a:
            msg = (
                f"An invalid MSTeams (first) Token ({token_a}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        self.token_b = validate_regex(
            token_b, *self.template_tokens["token_b"]["regex"]
        )
        if not self.token_b:
            msg = (
                f"An invalid MSTeams (second) Token ({token_b}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        self.token_c = validate_regex(
            token_c, *self.template_tokens["token_c"]["regex"]
        )
        if not self.token_c:
            msg = (
                f"An invalid MSTeams (third) Token ({token_c}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        self.token_d = validate_regex(
            token_d, *self.template_tokens["token_d"]["regex"]
        )

        # Place a thumbnail image inline with the message body
        self.include_image = include_image

        # Our template object is just an AppriseAttachment object
        self.template = AppriseAttachment(asset=self.asset)
        if template:
            # Add our definition to our template
            self.template.add(template)
            # Enforce maximum file size
            self.template[0].max_file_size = self.max_msteams_template_size

        # Template functionality
        self.tokens = {}
        if isinstance(tokens, dict):
            self.tokens.update(tokens)

        elif tokens:
            msg = (
                "The specified MSTeams Template Tokens "
                f"({tokens}) are not identified as a dictionary."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        self.logger.deprecate(
            "Microsoft is deprecating their MSTeams webhooks on "
            "December 31, 2025. It is advised that you switch to "
            "Microsoft Power Automate (already supported by Apprise as "
            "workflows://. For more information visit: "
            "https://github.com/caronc/apprise/wiki/Notify_workflows"
        )

    def gen_payload(
        self, body, title="", notify_type=NotifyType.INFO, **kwargs
    ):
        """This function generates our payload whether it be the generic one
        Apprise generates by default, or one provided by a specified external
        template."""

        # Acquire our to-be footer icon if configured to do so
        image_url = (
            None if not self.include_image else self.image_url(notify_type)
        )

        if not self.template:
            # By default we use a generic working payload if there was
            # no template specified
            payload = {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "summary": self.app_desc,
                "themeColor": self.color(notify_type),
                "sections": [
                    {
                        "activityImage": None,
                        "activityTitle": title,
                        "text": body,
                    },
                ],
            }

            if image_url:
                payload["sections"][0]["activityImage"] = image_url

            return payload

        # If our code reaches here, then we generate ourselves the payload
        template = self.template[0]
        if not template:
            # We could not access the attachment
            self.logger.error(
                "Could not access MSTeam template"
                f" {template.url(privacy=True)}."
            )
            return False

        # Take a copy of our token dictionary
        tokens = self.tokens.copy()

        # Apply some defaults template values
        tokens["app_body"] = body
        tokens["app_title"] = title
        tokens["app_type"] = notify_type.value
        tokens["app_id"] = self.app_id
        tokens["app_desc"] = self.app_desc
        tokens["app_color"] = self.color(notify_type)
        tokens["app_image_url"] = image_url
        tokens["app_url"] = self.app_url

        # Enforce Application mode
        tokens["app_mode"] = TemplateType.JSON

        try:
            with open(template.path) as fp:
                content = json.loads(apply_template(fp.read(), **tokens))

        except OSError:
            self.logger.error(
                f"MSTeam template {template.url(privacy=True)} could not be"
                " read."
            )
            return None

        except JSONDecodeError as e:
            self.logger.error(
                f"MSTeam template {template.url(privacy=True)} contains"
                " invalid JSON."
            )
            self.logger.debug(f"JSONDecodeError: {e}")
            return None

        # Load our JSON data (if valid)
        has_error = False
        if "@type" not in content:
            self.logger.error(
                f"MSTeam template {template.url(privacy=True)} is missing"
                " @type kwarg."
            )
            has_error = True

        if "@context" not in content:
            self.logger.error(
                f"MSTeam template {template.url(privacy=True)} is missing"
                " @context kwarg."
            )
            has_error = True

        return content if not has_error else None

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Microsoft Teams Notification."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        if self.version == 1:
            notify_url = self.notify_url_v1.format(
                token_a=self.token_a,
                token_b=self.token_b,
                token_c=self.token_c,
            )

        if self.version == 2:
            notify_url = self.notify_url_v2.format(
                team=self.team,
                token_a=self.token_a,
                token_b=self.token_b,
                token_c=self.token_c,
            )
        if self.version == 3:
            notify_url = self.notify_url_v3.format(
                team=self.team,
                token_a=self.token_a,
                token_b=self.token_b,
                token_c=self.token_c,
                token_d=self.token_d,
            )

        # Generate our payload if it's possible
        payload = self.gen_payload(
            body=body, title=title, notify_type=notify_type, **kwargs
        )
        if not payload:
            # No need to present a reason; that will come from the
            # gen_payload() function itself
            return False

        self.logger.debug(
            "MSTeams POST URL:"
            f" {notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"MSTeams Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                notify_url,
                data=json.dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyMSTeams.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send MSTeams notification: "
                    "{}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # We failed
                return False

            else:
                self.logger.info("Sent MSTeams notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending MSTeams notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # We failed
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.team if self.version > 1 else None,
            self.token_a,
            self.token_b,
            self.token_c,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "image": "yes" if self.include_image else "no",
        }

        if self.version != self.template_args["version"]["default"]:
            params["version"] = str(self.version)

        if self.template:
            params["template"] = NotifyMSTeams.quote(
                self.template[0].url(), safe=""
            )

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))
        # Store any template entries if specified
        params.update({f":{k}": v for k, v in self.tokens.items()})

        result = None

        if self.version == 1:
            result = (
                "{schema}://{token_a}/{token_b}/{token_c}/?{params}".format(
                    schema=self.secure_protocol,
                    token_a=self.pprint(self.token_a, privacy, safe="@"),
                    token_b=self.pprint(self.token_b, privacy, safe=""),
                    token_c=self.pprint(self.token_c, privacy, safe=""),
                    params=NotifyMSTeams.urlencode(params),
                )
            )

        if self.version == 2:
            result = (
                "{schema}://{team}/{token_a}/{token_b}/{token_c}/"
                "?{params}".format(
                    schema=self.secure_protocol,
                    team=NotifyMSTeams.quote(self.team, safe=""),
                    token_a=self.pprint(self.token_a, privacy, safe=""),
                    token_b=self.pprint(self.token_b, privacy, safe=""),
                    token_c=self.pprint(self.token_c, privacy, safe=""),
                    params=NotifyMSTeams.urlencode(params),
                )
            )

        if self.version == 3:
            result = (
                "{schema}://{team}/{token_a}/{token_b}/{token_c}/"
                "{token_d}/?{params}".format(
                    schema=self.secure_protocol,
                    team=NotifyMSTeams.quote(self.team, safe=""),
                    token_a=self.pprint(self.token_a, privacy, safe=""),
                    token_b=self.pprint(self.token_b, privacy, safe=""),
                    token_c=self.pprint(self.token_c, privacy, safe=""),
                    token_d=self.pprint(self.token_d, privacy, safe=""),
                    params=NotifyMSTeams.urlencode(params),
                )
            )
        return result

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Get unquoted entries
        entries = NotifyMSTeams.split_path(results["fullpath"])

        # Deprecated mode (backwards compatibility)
        if results.get("user"):
            # If a user was found, it's because it's still part of the first
            # token, so we concatinate them
            results["token_a"] = "{}@{}".format(
                NotifyMSTeams.unquote(results["user"]),
                NotifyMSTeams.unquote(results["host"]),
            )

        else:
            # Get the Team from the hostname
            results["team"] = NotifyMSTeams.unquote(results["host"])

            # Get the token from the path
            results["token_a"] = (
                None if not entries else NotifyMSTeams.unquote(entries.pop(0))
            )

        results["token_b"] = (
            None if not entries else NotifyMSTeams.unquote(entries.pop(0))
        )
        results["token_c"] = (
            None if not entries else NotifyMSTeams.unquote(entries.pop(0))
        )
        results["token_d"] = (
            None if not entries else NotifyMSTeams.unquote(entries.pop(0))
        )

        # Get Image
        results["include_image"] = parse_bool(
            results["qsd"].get("image", True)
        )

        # Get Team name if defined
        if "team" in results["qsd"] and results["qsd"]["team"]:
            results["team"] = NotifyMSTeams.unquote(results["qsd"]["team"])

        # Template Handling
        if "template" in results["qsd"] and results["qsd"]["template"]:
            results["template"] = NotifyMSTeams.unquote(
                results["qsd"]["template"]
            )

        # Override version if defined
        if "version" in results["qsd"] and results["qsd"]["version"]:
            results["version"] = NotifyMSTeams.unquote(
                results["qsd"]["version"]
            )

        else:
            version = 1
            if results.get("team"):
                version = 2
            if results.get("token_d"):
                version = 3
            # Set our version if not otherwise set
            results["version"] = version

        # Store our tokens
        results["tokens"] = results["qsd:"]

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Legacy Support:
            https://outlook.office.com/webhook/ABCD/IncomingWebhook/DEFG/HIJK

        New Hook Support:
            https://team-name.office.com/webhook/ABCD/IncomingWebhook/DEFG/HIJK

        Newer Hook Support:
            https://team-name.office.com/webhook/ABCD/IncomingWebhook/DEFG/HIJK/V2LMNOP
        """

        # We don't need to do incredibly details token matching as the purpose
        # of this is just to detect that were dealing with an msteams url
        # token parsing will occur once we initialize the function
        result = re.match(
            r"^https?://(?P<team>[^.]+)(?P<v2a>\.webhook)?\.office\.com/"
            r"webhook(?P<v2b>b2)?/"
            r"(?P<token_a>[A-Z0-9-]+@[A-Z0-9-]+)/"
            r"IncomingWebhook/"
            r"(?P<token_b>[A-Z0-9]+)/"
            r"(?P<token_c>[A-Z0-9-]+)/"
            r"(?P<token_d>V2[A-Z0-9-_]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            # Version 3 URL
            return NotifyMSTeams.parse_url(
                "{schema}://{team}/{token_a}/{token_b}/{token_c}/{token_d}"
                "/{params}".format(
                    schema=NotifyMSTeams.secure_protocol,
                    team=result.group("team"),
                    token_a=result.group("token_a"),
                    token_b=result.group("token_b"),
                    token_c=result.group("token_c"),
                    token_d=result.group("token_d"),
                    params=(
                        ""
                        if not result.group("params")
                        else result.group("params")
                    ),
                )
            )

        result = re.match(
            r"^https?://(?P<team>[^.]+)(?P<v2a>\.webhook)?\.office\.com/"
            r"webhook(?P<v2b>b2)?/"
            r"(?P<token_a>[A-Z0-9-]+@[A-Z0-9-]+)/"
            r"IncomingWebhook/"
            r"(?P<token_b>[A-Z0-9]+)/"
            r"(?P<token_c>[A-Z0-9-]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            if result.group("v2a"):
                # Version 2 URL
                return NotifyMSTeams.parse_url(
                    "{schema}://{team}/{token_a}/{token_b}/{token_c}"
                    "/{params}".format(
                        schema=NotifyMSTeams.secure_protocol,
                        team=result.group("team"),
                        token_a=result.group("token_a"),
                        token_b=result.group("token_b"),
                        token_c=result.group("token_c"),
                        params=(
                            ""
                            if not result.group("params")
                            else result.group("params")
                        ),
                    )
                )
            else:
                # Version 1 URLs
                # team is also set to 'outlook' in this case
                return NotifyMSTeams.parse_url(
                    "{schema}://{token_a}/{token_b}/{token_c}/{params}".format(
                        schema=NotifyMSTeams.secure_protocol,
                        token_a=result.group("token_a"),
                        token_b=result.group("token_b"),
                        token_c=result.group("token_c"),
                        params=(
                            ""
                            if not result.group("params")
                            else result.group("params")
                        ),
                    )
                )
        return None
