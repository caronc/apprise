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

# To use this plugin, you need to create a MS Teams Azure Webhook Workflow:
#  https://support.microsoft.com/en-us/office/browse-and-add-workflows-\
#       in-microsoft-teams-4998095c-8b72-4b0e-984c-f2ad39e6ba9a

# Your webhook will look somthing like this:
# https://prod-161.westeurope.logic.azure.com:443/\
#       workflows/643e69f83c8944438d68119179a10a64/triggers/manual/\
#       paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&\
#       sv=1.0&sig=KODuebWbDGYFr0z0eu-6Rj8aUKz7108W3wrNJZxFE5A
#
# Yes... The URL is that big... But it looks like this (greatly simplified):
# https://HOST:PORT/workflows/ABCD/triggers/manual/path/...sig=DEFG
#          ^    ^                ^                              ^
#          |    |                |                              |
#  These are important <---------^------------------------------^
#
#
# Apprise can support this webhook as is (directly passed into it)
# Alternatively it can be shortend to:

# These 3 tokens need to be placed in the URL after the Team
#   workflows://HOST:PORT/ABCD/DEFG/
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


class NotifyWorkflows(NotifyBase):
    """A wrapper for Microsoft Workflows (MS Teams) Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Power Automate / Workflows (for MSTeams)"

    # The services URL
    service_url = (
        "https://www.microsoft.com/power-platform/products/power-automate"
    )

    # The default secure protocol
    secure_protocol = ("workflow", "workflows")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_workflows"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_32

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    # Default Notification Format
    notify_format = NotifyFormat.MARKDOWN

    # There is no reason we should exceed 35KB when reading in a JSON file.
    # If it is more than this, then it is not accepted
    max_workflows_template_size = 35000

    # Adaptive Card Version
    adaptive_card_version = "1.4"

    # Define object templates
    templates = (
        "{schema}://{host}/{workflow}/{signature}",
        "{schema}://{host}:{port}/{workflow}/{signature}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "host": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
            # workflow identifier
            "workflow": {
                "name": _("Workflow ID"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[A-Z0-9_-]+$", "i"),
            },
            # Signature
            "signature": {
                "name": _("Signature"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9_-]+$", "i"),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "id": {
                "alias_of": "workflow",
            },
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
            "wrap": {
                "name": _("Wrap Text"),
                "type": "bool",
                "default": True,
                "map_to": "wrap",
            },
            "template": {
                "name": _("Template Path"),
                "type": "string",
                "private": True,
            },
            # Below variable shortforms are taken from the Workflows webhook
            # for consistency
            "sig": {
                "alias_of": "signature",
            },
            "ver": {
                "name": _("API Version"),
                "type": "string",
                "default": "2016-06-01",
                "map_to": "version",
            },
            "api-version": {"alias_of": "ver"},
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
        workflow,
        signature,
        include_image=None,
        version=None,
        template=None,
        tokens=None,
        wrap=None,
        **kwargs,
    ):
        """Initialize Microsoft Workflows Object."""
        super().__init__(**kwargs)

        self.workflow = validate_regex(
            workflow, *self.template_tokens["workflow"]["regex"]
        )
        if not self.workflow:
            msg = f"An invalid Workflows ID ({workflow}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.signature = validate_regex(
            signature, *self.template_tokens["signature"]["regex"]
        )
        if not self.signature:
            msg = f"An invalid Signature ({signature}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Place a thumbnail image inline with the message body
        self.include_image = bool(
            include_image
            if include_image is not None
            else self.template_args["image"]["default"]
        )

        # Wrap Text
        self.wrap = bool(
            wrap if wrap is not None else self.template_args["wrap"]["default"]
        )

        # Our template object is just an AppriseAttachment object
        self.template = AppriseAttachment(asset=self.asset)
        if template:
            # Add our definition to our template
            self.template.add(template)
            # Enforce maximum file size
            self.template[0].max_file_size = self.max_workflows_template_size

        # Prepare Version
        self.api_version = (
            version
            if version is not None
            else self.template_args["ver"]["default"]
        )

        # Template functionality
        self.tokens = {}
        if isinstance(tokens, dict):
            self.tokens.update(tokens)

        elif tokens:
            msg = (
                "The specified Workflows Template Tokens "
                f"({tokens}) are not identified as a dictionary."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # else:  NoneType - this is okay
        return

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

        body_content = []
        if image_url:
            body_content.append({
                "type": "Image",
                "url": image_url,
                "height": "32px",
                "altText": notify_type,
            })

        if title:
            body_content.append({
                "type": "TextBlock",
                "text": f"{title}",
                "style": "heading",
                "weight": "Bolder",
                "size": "Large",
                "id": "title",
            })

        body_content.append({
            "type": "TextBlock",
            "text": body,
            "style": "default",
            "wrap": self.wrap,
            "id": "body",
        })

        if not self.template:
            # By default we use a generic working payload if there was
            # no template specified
            schema = "http://adaptivecards.io/schemas/adaptive-card.json"
            payload = {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": {
                        "$schema": schema,
                        "type": "AdaptiveCard",
                        "version": self.adaptive_card_version,
                        "body": body_content,
                        # Additionally
                        "msteams": {"width": "full"},
                    },
                }],
            }

            return payload

        # If our code reaches here, then we generate ourselves the payload
        template = self.template[0]
        if not template:
            # We could not access the attachment
            self.logger.error(
                "Could not access Workflow template"
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

        return content

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Microsoft Teams Notification."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        params = {
            "api-version": self.api_version,
            "sp": "/triggers/manual/run",
            "sv": "1.0",
            "sig": self.signature,
        }

        notify_url = (
            "https://{host}{port}/workflows/{workflow}/"
            "triggers/manual/paths/invoke".format(
                host=self.host,
                port="" if not self.port else f":{self.port}",
                workflow=self.workflow,
            )
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
            "Workflows POST URL:"
            f" {notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Workflows Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                notify_url,
                params=params,
                data=json.dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code not in (
                requests.codes.ok,
                requests.codes.accepted,
            ):
                # We had a problem
                status_str = NotifyWorkflows.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Workflows notification: "
                    "{}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # We failed
                return False

            else:
                self.logger.info("Sent Workflows notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Workflows notification."
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
            self.secure_protocol[0],
            self.host,
            self.port,
            self.workflow,
            self.signature,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "image": "yes" if self.include_image else "no",
            "wrap": "yes" if self.wrap else "no",
        }

        if self.template:
            params["template"] = NotifyWorkflows.quote(
                self.template[0].url(), safe=""
            )

        # Store our version if it differs from default
        if self.api_version != self.template_args["ver"]["default"]:
            params["ver"] = self.api_version

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))
        # Store any template entries if specified
        params.update({f":{k}": v for k, v in self.tokens.items()})

        return (
            "{schema}://{host}{port}/{workflow}/{signature}/?{params}".format(
                schema=self.secure_protocol[0],
                host=self.host,
                port="" if not self.port else f":{self.port}",
                workflow=self.pprint(self.workflow, privacy, safe=""),
                signature=self.pprint(self.signature, privacy, safe=""),
                params=NotifyWorkflows.urlencode(params),
            )
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # store values if provided
        entries = NotifyWorkflows.split_path(results["fullpath"])

        # Display image?
        results["include_image"] = parse_bool(
            results["qsd"].get(
                "image", NotifyWorkflows.template_args["image"]["default"]
            )
        )

        # Wrap Text?
        results["wrap"] = parse_bool(
            results["qsd"].get(
                "wrap", NotifyWorkflows.template_args["wrap"]["default"]
            )
        )

        # Template Handling
        if "template" in results["qsd"] and results["qsd"]["template"]:
            results["template"] = NotifyWorkflows.unquote(
                results["qsd"]["template"]
            )

        if "workflow" in results["qsd"] and results["qsd"]["workflow"]:
            results["workflow"] = NotifyWorkflows.unquote(
                results["qsd"]["workflow"]
            )

        elif "id" in results["qsd"] and results["qsd"]["id"]:
            results["workflow"] = NotifyWorkflows.unquote(results["qsd"]["id"])

        else:
            results["workflow"] = (
                None
                if not entries
                else NotifyWorkflows.unquote(entries.pop(0))
            )

        # Signature
        if "signature" in results["qsd"] and results["qsd"]["signature"]:
            results["signature"] = NotifyWorkflows.unquote(
                results["qsd"]["signature"]
            )

        elif "sig" in results["qsd"] and results["qsd"]["sig"]:
            results["signature"] = NotifyWorkflows.unquote(
                results["qsd"]["sig"]
            )

        else:
            # Read information from path
            results["signature"] = (
                None
                if not entries
                else NotifyWorkflows.unquote(entries.pop(0))
            )

        # Version
        if "api-version" in results["qsd"] and results["qsd"]["api-version"]:
            results["version"] = NotifyWorkflows.unquote(
                results["qsd"]["api-version"]
            )

        elif "ver" in results["qsd"] and results["qsd"]["ver"]:
            results["version"] = NotifyWorkflows.unquote(results["qsd"]["ver"])

        # Store our tokens
        results["tokens"] = results["qsd:"]

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support parsing the webhook straight out of workflows
            https://HOST:443/workflows/WORKFLOWID/triggers/manual/paths/invoke
        """

        # Match our workflows webhook URL and re-assemble
        result = re.match(
            r"^https?://(?P<host>[A-Z0-9_.-]+)"
            r"(?P<port>:[1-9][0-9]{0,5})?"
            r"/workflows/"
            r"(?P<workflow>[A-Z0-9_-]+)"
            r"/triggers/manual/paths/invoke/?"
            r"(?P<params>\?.+)$",
            url,
            re.I,
        )

        if result:
            # Construct our URL
            return NotifyWorkflows.parse_url(
                "{schema}://{host}{port}/{workflow}/{params}".format(
                    schema=NotifyWorkflows.secure_protocol[0],
                    host=result.group("host"),
                    port=(
                        ""
                        if not result.group("port")
                        else result.group("port")
                    ),
                    workflow=result.group("workflow"),
                    params=result.group("params"),
                )
            )
        return None
