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


# Notifly is a notification infrastructure service.  A message is sent by
# triggering a workflow that you build in the Notifly dashboard; the workflow
# decides which channels (email, SMS, push, chat, in-app) the subscriber gets.
#
# Setup steps:
#  1. Visit https://notifly.io/ and sign in or create an account.
#  2. Go to API Keys and copy the secret key for your environment
#     (Development or Production).
#  3. Create a workflow.  Note its trigger identifier; this is the
#     {workflow} used below.
#  4. Reference the values Apprise sends in your workflow's templates:
#         {{payload.title}}  the notification title
#         {{payload.body}}   the notification body
#         {{payload.type}}   info, success, warning or failure
#  5. Create a subscriber (or use an existing one) and note its subscriber
#     id.  This is the {subscriber} used below.
#
# Apprise URL format:
#   notifly://ApiKey/Workflow/Subscriber
#   notifly://ApiKey/Workflow/Subscriber1/Subscriber2/SubscriberN
#
# In the URL:
#   - ApiKey     : your Notifly secret key
#   - Workflow   : the trigger identifier of the workflow to run
#   - Subscriber : one or more subscriber ids; each one is notified with its
#                  own request
#
# Optional query-string parameters:
#   - ?to=Subscriber2,Subscriber3   additional subscriber ids
#   - :key=value                    adds "key": "value" to the payload sent
#                                   to the workflow (e.g. ?:order=1234)
#
# API Reference:
#   https://notifly.io/docs/api

from __future__ import annotations

from json import dumps, loads
import logging
from typing import Any, Optional
from uuid import uuid4

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list, validate_regex
from ..utils.sanitize import sanitize_payload
from .base import NotifyBase

# Extend HTTP Error Messages
NOTIFLY_HTTP_ERROR_MAP = {
    400: "The payload did not match what the workflow expects.",
    401: "The API key used was missing or invalid.",
    403: "The API key is not permitted to do this.",
    404: "The workflow was not found.",
    409: "The request is already being processed.",
    422: "The request was rejected or the Idempotency-Key was reused.",
    429: "The rate limit was exceeded.",
}


class NotifyNotifly(NotifyBase):
    """A wrapper for Notifly Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Notifly"

    # The services URL
    service_url = "https://notifly.io"

    # The default secure protocol
    secure_protocol = "notifly"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/notifly/"

    # The Notifly trigger endpoint
    notify_url = "https://api.notifly.io/v1/events/trigger"

    # The trigger endpoint has no way to carry attachments
    attachment_support = False

    # Define object templates
    templates = ("{schema}://{apikey}/{workflow}/{targets}",)

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
            "workflow": {
                "name": _("Workflow"),
                "type": "string",
                "required": True,
            },
            "target_subscriber": {
                "name": _("Subscriber ID"),
                "type": "string",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Subscribers"),
                "type": "list:string",
                "required": True,
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
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "payload_extras": {
            "name": _("Payload Extras"),
            "prefix": ":",
        },
    }

    def __init__(
        self,
        apikey: str,
        workflow: str,
        targets: Optional[Any] = None,
        payload_extras: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Notify Notifly Object."""
        super().__init__(**kwargs)

        # API Key
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid Notifly API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Workflow trigger identifier
        self.workflow = validate_regex(workflow)
        if not self.workflow:
            msg = f"An invalid Notifly Workflow ({workflow}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Subscribers to notify; with none, send() has nothing to do
        self.targets = parse_list(targets)

        # Extra values handed to the workflow alongside title/body/type
        self.payload_extras = {}
        if payload_extras:
            self.payload_extras.update(payload_extras)

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.apikey, self.workflow)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Payload body extras prefixed with a ':' sign
        params.update({f":{k}": v for k, v in self.payload_extras.items()})

        return "{schema}://{apikey}/{workflow}/{targets}?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            workflow=NotifyNotifly.quote(self.workflow, safe=""),
            targets="/".join(
                [NotifyNotifly.quote(x, safe="") for x in self.targets]
            ),
            params=NotifyNotifly.urlencode(params),
        )

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Always return at least 1 so the framework counts this instance
        return len(self.targets) if self.targets else 1

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform Notifly Notification."""

        if not self.targets:
            # Nothing to send to
            self.logger.warning("There are no Notifly subscribers to notify")
            return False

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"ApiKey {self.apikey}",
        }

        # What the workflow templates get to work with
        payload_ = {
            "title": title,
            "body": body,
            "type": notify_type,
        }

        # Anything the user added is applied last so they can override
        payload_.update(self.payload_extras)

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            # Skip a target that already accepted this message so
            # a retry does not deliver it twice.
            if self.is_delivered(target):
                continue

            payload = {
                "name": self.workflow,
                "to": {"subscriberId": target},
                "payload": payload_,
            }

            # Notifly honours an Idempotency-Key header.  The key is kept
            # across retries of this notification, so if a response is lost
            # after the trigger was accepted, the retry does not send it a
            # second time.
            idempotency_key = self.recall(f"idempotency:{target}")
            if idempotency_key is None:
                idempotency_key = str(uuid4())
                self.remember(f"idempotency:{target}", idempotency_key)

            target_headers = headers.copy()
            target_headers["Idempotency-Key"] = idempotency_key

            # Some Debug Logging
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(
                    "Notifly POST URL: %s (cert_verify=%r)",
                    self.notify_url,
                    self.verify_certificate,
                )
                self.logger.debug(
                    "Notifly Payload: %s", sanitize_payload(payload)
                )

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    headers=target_headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )

                # Notifly answers 201 even when the workflow could not run,
                # so the body has to be read to know it was accepted.
                reason = None
                if r.status_code not in (
                    requests.codes.ok,
                    requests.codes.created,
                ):
                    reason = NotifyNotifly.http_response_code_lookup(
                        r.status_code, NOTIFLY_HTTP_ERROR_MAP
                    )
                    reason = (
                        f"{reason}, error={r.status_code}"
                        if reason
                        else f"error={r.status_code}"
                    )

                else:
                    try:
                        data = loads(r.content).get("data")

                    except (AttributeError, TypeError, ValueError):
                        # Not json; the status code is all we have
                        data = None

                    if isinstance(data, dict) and not (
                        data.get("acknowledged") is True
                        and data.get("status") == "processed"
                    ):
                        reason = "status={}".format(data.get("status"))

                if reason:
                    self.logger.warning(
                        "Failed to send Notifly notification to %s: %s.",
                        target,
                        reason,
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

                self.logger.info("Sent Notifly notification to %s.", target)

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Notifly "
                    "notification to %s.",
                    target,
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this target.
            self.mark_delivered(target)

        return not has_error

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our URL looks like this:
        #    {schema}://{apikey}/{workflow}/{subscriber1}/{subscriber2}/etc..
        #
        # The API key occupies the hostname position
        results["apikey"] = NotifyNotifly.unquote(results["host"])

        # Everything after it is the workflow, then the subscribers
        entries = NotifyNotifly.split_path(results["fullpath"])
        results["workflow"] = entries.pop(0) if entries else None
        results["targets"] = entries

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyNotifly.parse_list(
                results["qsd"]["to"]
            )

        # Store any additional payload extra's defined
        results["payload_extras"] = {
            NotifyNotifly.unquote(x): NotifyNotifly.unquote(y)
            for x, y in results["qsd:"].items()
        }

        return results
