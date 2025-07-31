# -*- coding: utf-8 -*-
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

# API Refererence:
#   - https://docs.signl4.com/integrations/webhook/webhook.html
#

from json import dumps

import requests

from .base import NotifyBase
from ..url import PrivacyMode
from ..common import NotifyType
from ..utils.parse import validate_regex
from ..locale import gettext_lazy as _

class NotifySIGNL4(NotifyBase):
    """
    A wrapper for SIGNL4 Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = "SIGNL4"

    # The services URL
    service_url = "https://connect.signl4.com/webhook/"

    # Secure Protocol
    secure_protocol = "signl4"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_signl4"

    # Our event action type
    event_action = "trigger"

    # Define object templates
    templates = (
        "{schema}://{secret}",
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        # SIGNL4 team or integration secret
        "secret": {
            "name": _("Secret"),
            "type": "string",
            "private": True,
            "required": True
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        "service": {
            "name": _("service"),
            "type": "string",
        },
        "location": {
            "name": _("location"),
            "type": "string",
        },
        "alerting_scenario": {
            "name": _("alerting_scenario"),
            "type": "string",
        },
        "filtering": {
            "name": _("filtering"),
            "type": "bool",
        },
        "external_id": {
            "name": _("external_id"),
            "type": "string",
        },
        "status": {
            "name": _("status"),
            "type": "string",
        },
    })

    def __init__(self,
                 secret,
                 service=None,
                 location=None,
                 alerting_scenario=None,
                 filtering=None,
                 external_id=None,
                 status=None,
                 **kwargs):
        """
        Initialize SIGNL4 Object
        """
        super().__init__(**kwargs)

        # SIGNL4 team or integration secret
        self.secret = validate_regex(secret)
        if not self.secret:
            msg = "An invalid SIGNL4 team or integration secret " \
                  "({}) was specified.".format(secret)
            self.logger.warning(msg)
            raise TypeError(msg)

        # A service option for notifications
        self.service = service

        # A location option for notifications
        self.location = location

        # A alerting_scenario option for notifications
        self.alerting_scenario = alerting_scenario

        # A filtering option for notifications
        self.filtering = bool(filtering)

        # A external_id option for notifications
        self.external_id = external_id

        # A location option for notifications
        self.status = status

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """
        Send our SIGNL4 Notification
        """

        # Prepare our headers
        headers = {
            "Content-Type": "application/json",
        }

        # Prepare our persistent_notification.create payload
        payload = {
            "title": title if title else self.app_desc,
            "body": body,
            "X-S4-SourceSystem": "Apprise",
        }

        if self.service:
            payload["X-S4-Service"] = self.service

        if self.alerting_scenario:
            payload["X-S4-AlertingScenario"] = self.alerting_scenario

        if self.location:
            payload["X-S4-Location"] = self.location

        if self.filtering:
            payload["X-S4-Filtering"] = self.filtering

        if self.external_id:
            payload["X-S4-ExternalID"] = self.external_id

        if self.status:
            payload["X-S4-Status"] = self.status

        # Prepare our URL
        notify_url = self.service_url + self.secret

        self.logger.debug("SIGNL4 POST URL: {notify_url} \
                          (cert_verify={self.verify_certificate}")
        self.logger.debug("SIGNL4 Payload: {payload}")

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code not in (
                    requests.codes.ok, requests.codes.created,
                    requests.codes.accepted):
                # We had a problem
                status_str = \
                    NotifySIGNL4.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    "Failed to send SIGNL4 notification: "
                    "{}{}error={}.".format(
                        status_str,
                        ", " if status_str else "",
                        r.status_code))

                self.logger.debug("Response Details:\r\n{}".format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info("Sent SIGNL4 notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending SIGNL4 "
                "notification to {self.host}.")
            self.logger.debug("Socket Exception: " + str(e))

            # Return; we're done
            return False

        return True

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol, self.secret,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {}

        if self.service is not None:
            params["service"] = self.service

        if self.location is not None:
            params["location"] = self.location

        if self.alerting_scenario is not None:
            params["alerting_scenario"] = self.alerting_scenario

        if self.filtering is not None:
            params["filtering"] = self.filtering

        if self.external_id is not None:
            params["external_id"] = self.external_id

        if self.status is not None:
            params["status"] = self.status

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        url = "{schema}://{secret}"

        return url.format(
            schema=self.secure_protocol,
            # never encode hostname since we're expecting it to be a valid one
            secret=self.pprint(
                self.secret, privacy, mode=PrivacyMode.Secret, safe=""),
            params=NotifySIGNL4.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.
        """

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn"t load the results
            return results

        # The "secret" makes it easier to use yaml configuration
        if "secret" in results["qsd"] and \
                len(results["qsd"]["secret"]):
            results["secret"] = \
                NotifySIGNL4.unquote(results["qsd"]["secret"])
        else:
            results["secret"] = \
                NotifySIGNL4.unquote(results["host"])

        if "service" in results["qsd"] and len(results["qsd"]["service"]):
            results["service"] = \
                NotifySIGNL4.unquote(results["qsd"]["service"])

        if "location" in results["qsd"] and len(results["qsd"]["location"]):
            results["location"] = \
                NotifySIGNL4.unquote(results["qsd"]["location"])

        if "alerting_scenario" in results["qsd"] and \
            len(results["qsd"]["alerting_scenario"]):
            results["alerting_scenario"] = \
                NotifySIGNL4.unquote(results["qsd"]["alerting_scenario"])

        if "filtering" in results["qsd"] and len(results["qsd"]["filtering"]):
            results["filtering"] = \
                NotifySIGNL4.unquote(results["qsd"]["filtering"])

        if "external_id" in results["qsd"] and \
            len(results["qsd"]["external_id"]):
            results["external_id"] = \
                NotifySIGNL4.unquote(results["qsd"]["external_id"])

        if "status" in results["qsd"] and len(results["qsd"]["status"]):
            results["status"] = \
                NotifySIGNL4.unquote(results["qsd"]["status"])

        return results
