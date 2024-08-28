# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

# Simple API Reference:
#  - https://sendpulse.com/integrations/api/smtp

import base64
from email.utils import formataddr
from json import dumps

import requests

from .. import exception
from ..common import NotifyFormat, NotifyType
from ..conversion import convert_between
from ..locale import gettext_lazy as _
from ..utils.parse import is_email, parse_emails, parse_list, validate_regex
from .base import NotifyBase


class NotifySendPulse(NotifyBase):
    """
    A wrapper for Notify SendPulse Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = "SendPulse"

    # The services URL
    service_url = "https://sendpulse.com"

    # The default secure protocol
    secure_protocol = "sendpulse"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_sendpulse"

    # Default to markdown
    notify_format = NotifyFormat.HTML

    # The default Email API URL to use
    notify_email_url = "https://api.sendpulse.com/smtp/emails"

    # Support attachments
    attachment_support = True

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.2

    # Support attachments
    attachment_support = True

    # The default subject to use if one isn't specified.
    default_empty_subject = "<no subject>"

    # Define object templates
    templates = (
        "{schema}://{from_email}/{client_id}/{client_secret}/",
        "{schema}://{from_email}/{client_id}/{client_secret}/{targets}",
    )

    # Define our template arguments
    template_tokens = dict(NotifyBase.template_tokens, **{
        "from_email": {
            "name": _("Source Email"),
            "type": "string",
            "required": True,
        },
        "client_id": {
            "name": _("Client ID"),
            "type": "string",
            "required": True,
            "private": True,
            "regex": (r"^[A-Z0-9._-]+$", "i"),
        },
        "client_secret": {
            "name": _("Client Secret"),
            "type": "string",
            "required": True,
            "private": True,
            "regex": (r"^[A-Z0-9._-]+$", "i"),
        },
        "target_email": {
            "name": _("Target Email"),
            "type": "string",
            "map_to": "targets",
        },
        "targets": {
            "name": _("Targets"),
            "type": "list:string",
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        "to": {
            "alias_of": "targets",
        },
        "from": {
            "name": _("From Email"),
            "type": "string",
            "map_to": "from_email",
        },
        "cc": {
            "name": _("Carbon Copy"),
            "type": "list:string",
        },
        "bcc": {
            "name": _("Blind Carbon Copy"),
            "type": "list:string",
        },
        "template": {
            # The template ID is an integer
            "name": _("Template ID"),
            "type": "int",
        },
        "id": {
            "alias_of": "client_id",
        },
        "secret": {
            "alias_of": "client_secret",
        }
    })

    # Support Template Dynamic Variables (Substitutions)
    template_kwargs = {
        "template_data": {
            "name": _("Template Data"),
            "prefix": "+",
        },
    }

    def __init__(self, from_email, client_id, client_secret, targets=None,
                 cc=None, bcc=None, template=None,
                 template_data=None, **kwargs):
        """
        Initialize Notify SendPulse Object
        """
        super().__init__(**kwargs)

        # Client ID
        self.client_id = validate_regex(
            client_id, *self.template_tokens["client_id"]["regex"])
        if not self.client_id:
            msg = "An invalid SendPulse Client ID " \
                  "({}) was specified.".format(client_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Client Secret
        self.client_secret = validate_regex(
            client_secret, *self.template_tokens["client_secret"]["regex"])
        if not self.client_secret:
            msg = "An invalid SendPulse Client Secret " \
                  "({}) was specified.".format(client_secret)
            self.logger.warning(msg)
            raise TypeError(msg)

        result = is_email(from_email)
        if not result:
            msg = "Invalid ~From~ email specified: {}".format(from_email)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Tracks emails to name lookups (if they exist)
        self.__email_map = {}

        # Store from email address
        self.from_email = result["full_email"]
        self.__email_map[self.from_email] = result["name"] \
            if result["name"] else self.app_id

        # Acquire Targets (To Emails)
        self.targets = []

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        if template:
            try:
                # Store our template
                self.template = int(template)

            except (TypeError, ValueError):
                # Not a valid integer; ignore entry
                err = "The SendPulse Template ID specified ({}) is invalid."\
                    .format(template)
                self.logger.warning(err)
                raise TypeError(err) from None

        # Now our dynamic template data (if defined)
        self.template_data = template_data \
            if isinstance(template_data, dict) else {}

        if targets:
            # Validate recipients (to:) and drop bad ones:
            for recipient in parse_emails(targets):
                result = is_email(recipient)
                if result:
                    self.targets.append(
                        (result["name"] if result["name"] else False,
                            result["full_email"]))
                    continue

                self.logger.warning(
                    "Dropped invalid To email "
                    "({}) specified.".format(recipient),
                )

        else:
            # If our target email list is empty we want to add ourselves to it
            self.targets.append(self.from_email)

        # Validate recipients (cc:) and drop bad ones:
        for recipient in parse_list(cc):

            result = is_email(recipient)
            if result:
                self.cc.add(result["full_email"])
                if result["name"]:
                    self.__email_lookup[result["full_email"]] = result["name"]
                continue

            self.logger.warning(
                "Dropped invalid Carbon Copy email "
                "({}) specified.".format(recipient),
            )

        # Validate recipients (bcc:) and drop bad ones:
        for recipient in parse_list(bcc):

            result = is_email(recipient)
            if result:
                self.bcc.add(result["full_email"])
                if result["name"]:
                    self.__email_lookup[result["full_email"]] = result["name"]
                continue

            self.logger.warning(
                "Dropped invalid Blind Carbon Copy email "
                "({}) specified.".format(recipient),
            )

        if len(self.targets) == 0:
            # Notify ourselves
            self.targets.append(self.from_email)

        return

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.client_id, self.client_secret)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if len(self.cc) > 0:
            # Handle our Carbon Copy Addresses
            params["cc"] = ",".join([
                formataddr(
                    (self.__email_lookup.get(e, False), e),
                    # Swap comma for it's escaped url code (if detected) since
                    # we're using that as a delimiter
                    charset="utf-8").replace(",", "%2C")
                for e in self.cc])

        if len(self.bcc) > 0:
            # Handle our Blind Carbon Copy Addresses
            params["bcc"] = ",".join([
                formataddr(
                    (self.__email_lookup.get(e, False), e),
                    # Swap comma for it's escaped url code (if detected) since
                    # we're using that as a delimiter
                    charset="utf-8").replace(",", "%2C")
                for e in self.bcc])

        if self.template:
            # Handle our Template ID if if was specified
            params["template"] = self.template

        # Append our template_data into our parameter list
        params.update(
            {"+{}".format(k): v for k, v in self.template_data.items()})

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = \
            not (len(self.targets) == 1 and self.targets[0] == self.from_email)

        return "{schema}://{source}/{cid}/{secret}/{targets}?{params}".format(
            schema=self.secure_protocol,
            source=self.from_email,
            cid=self.pprint(self.client_id, privacy, safe=""),
            secret=self.pprint(self.client_secret, privacy, safe=""),
            targets="" if not has_targets else "/".join(
                [NotifySendPulse.quote(x, safe="") for x in self.targets]),
            params=NotifySendPulse.urlencode(params),
        )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        return len(self.targets)

    def send(self, body, title="", notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform SendPulse Notification
        """

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(self.apikey),
        }

        # error tracking (used for function return)
        has_error = False

        # A Simple Email Payload Template
        _payload = {
            "email": {
                "from": {
                    "name": self.from_email[0],
                    "email": self.from_email[1],
                },
                # To is populated further on
                "to": [],
                # A subject is a requirement, so if none is specified we must
                # set a default with at least 1 character or SendPulse will
                # deny our request
                "subject": title if title else self.default_empty_subject,
            }
        }

        # Prepare Email Message
        if self.notify_format == NotifyFormat.HTML:
            # HTML
            _payload["email"].update({
                "text": convert_between(
                    NotifyFormat.HTML, NotifyFormat.TEXT, body),
                "html": base64.b64encode(body.encode("utf-8")).decode("ascii"),
            })

        else:  # Text
            _payload["email"]["text"] = body

        if attach and self.attachment_support:
            attachments = {}

            # Send our attachments
            for no, attachment in enumerate(attach, start=1):
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access SendPulse attachment {}.".format(
                            attachment.url(privacy=True)))
                    return False

                try:
                    attachments[
                        attachment.name if attachment.name
                        else f"file{no:03}.dat"] = attachment.base64()

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access SendPulse attachment {}.".format(
                            attachment.url(privacy=True)))
                    return False

                self.logger.debug(
                    "Appending SendPulse attachment {}".format(
                        attachment.url(privacy=True)))

            # Append our attachments to the payload
            _payload["email"].update({
                "attachments_binary": attachments,
            })

        if self.template:
            _payload["email"].update({
                "template": {
                    "id": self.template,
                    "variables": self.template_data,
                }})

        targets = list(self.targets)
        while len(targets) > 0:
            target = targets.pop(0)

            # Create a copy of our template
            payload = _payload.copy()

            # the cc, bcc, to field must be unique or SendMail will fail, the
            # below code prepares this by ensuring the target isn't in the cc
            # list or bcc list. It also makes sure the cc list does not contain
            # any of the bcc entries
            cc = (self.cc - self.bcc - {target})
            bcc = (self.bcc - {target})

            #
            # prepare our 'to'
            #
            to = {
                "email": target
            }
            if target in self.__email_lookup:
                to["name"] = self.__email_lookup[target]

            # Set our target
            payload["email"]["to"] = [to]

            if len(cc):
                payload["email"]["cc"] = []
                for email in cc:
                    item = {
                        "email": email,
                    }
                if email in self.__email_lookup:
                    item["name"] = self.__email_lookup[email]

                payload["email"]["cc"].append(item)

            if len(bcc):
                payload["email"]["bcc"] = []
                for email in bcc:
                    item = {
                        "email": email,
                    }
                if email in self.__email_lookup:
                    item["name"] = self.__email_lookup[email]

                payload["email"]["bcc"].append(item)

            self.logger.debug("SendPulse POST URL: %s (cert_verify=%r)",
                self.notify_email_url, self.verify_certificate,
            )
            self.logger.debug("SendPulse Payload: %s",  str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_email_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code not in (
                        requests.codes.ok, requests.codes.accepted):
                    # We had a problem
                    status_str = \
                        NotifySendPulse.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        "Failed to send SendPulse notification to {}: "
                        "{}{}error={}.".format(
                            target,
                            status_str,
                            ", " if status_str else "",
                            r.status_code))

                    self.logger.debug(
                        "Response Details:\r\n{}".format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        "Sent SendPulse notification to {}.".format(target))

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending SendPulse "
                    "notification to {}.".format(target))
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our URL looks like this:
        #    {schema}://{from_email}:{client_id}/{client_secret}/{targets}
        #
        # which actually equates to:
        #    {schema}://{user}@{host}/{client_id}/{client_secret}
        #                                  /{email1}/{email2}/etc..
        #                 ^       ^
        #                 |       |
        #                -from addr-

        # Get our potential email targets
        # First 2 elements are the client_id and client_secret
        results["targets"] = NotifySendPulse.split_path(results["fullpath"])
        # check for our client id
        if "id" in results["qsd"] and len(results["qsd"]["id"]):
            # Store our Client ID
            results["client_id"] = \
                NotifySendPulse.unquote(results["qsd"]["id"])

        elif results["targets"]:
            # Store our Client ID
            results["client_id"] = results["targets"].pop(0)

        else:  # Not defined
            results["client_id"] = None

        if "secret" in results["qsd"] and len(results["qsd"]["secret"]):
            # Store our Client Secret
            results["client_secret"] = \
                NotifySendPulse.unquote(results["qsd"]["secret"])

        elif results["targets"]:
            # Store our Client Secret
            results["client_secret"] = results["targets"].pop(0)

        else:  # Not defined
            results["client_secret"] = None

        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["from_email"] = \
                NotifySendPulse.unquote(results["qsd"]["from_email"])

            # This means any user@host is the To Address if defined
            if results.get("user") and results.get("host"):
                results["targets"] += "{}@{}".format(
                    NotifySendPulse.unquote(
                        results["password"]
                        if results["password"] else results["user"]),
                    NotifySendPulse.unquote(results["host"]),
                )

        elif results.get("user") and results.get("host"):
            results["from_email"] = "{}@{}".format(
                NotifySendPulse.unquote(
                    results["password"]
                    if results["password"] else results["user"]),
                NotifySendPulse.unquote(results["host"]),
            )

        else:  # Not defined
            results["from_email"] = None

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += \
                NotifySendPulse.parse_list(results["qsd"]["to"])

        # Handle Carbon Copy Addresses
        if "cc" in results["qsd"] and len(results["qsd"]["cc"]):
            results["cc"] = \
                NotifySendPulse.parse_list(results["qsd"]["cc"])

        # Handle Blind Carbon Copy Addresses
        if "bcc" in results["qsd"] and len(results["qsd"]["bcc"]):
            results["bcc"] = \
                NotifySendPulse.parse_list(results["qsd"]["bcc"])

        # Handle Blind Carbon Copy Addresses
        if "template" in results["qsd"] and len(results["qsd"]["template"]):
            results["template"] = \
                NotifySendPulse.unquote(results["qsd"]["template"])

        # Add any template substitutions
        results["template_data"] = results["qsd+"]

        return results
