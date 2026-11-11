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

# API Source:
#   https://docs.aws.amazon.com/social-messaging/latest/APIReference/
#
# WhatsApp through AWS End User Messaging Social.  AWS relays the same
# message Meta's WhatsApp Cloud API accepts (see whatsapp.py).
#
# 1. In the AWS End User Messaging Social console, link your WhatsApp
#    Business Account and register a sender phone number.
# 2. Copy the sender's phone number ID; it looks like:
#       phone-number-id-01234567890123456789012345678901
#    This is NOT your actual phone number.
# 3. Create an Access Key ID and Secret Access Key for an IAM user that is
#    allowed to call social-messaging:SendWhatsAppMessage.
# 4. To send attachments, provide a private S3 bucket (in the same account
#    and region) with ?bucket=.  Files are staged under apprise/ in it
#    while WhatsApp imports them, then removed.  This also requires the
#    social-messaging:PostWhatsAppMessageMedia permission along with
#    s3:PutObject, s3:GetObject and s3:DeleteObject on apprise/*.
#
# Your Apprise URL should be assembled as:
#   awswhatsapp://{access_key_id}/{secret_access_key}/{region}/
#       {from_phone_id}/{to_phone}

from base64 import b64encode
from datetime import datetime, timezone
from hashlib import sha256
import hmac
from json import dumps, loads
import re
from typing import Any, Optional
from urllib.parse import quote
from uuid import uuid4

import requests

from ..attachment.base import AttachBase
from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from .base import NotifyBase

# Our Region Identifier
# support us-gov-west-1 syntax as well
IS_REGION = re.compile(
    r"^\s*(?P<country>[a-z]{2})-(?P<area>[a-z-]+?)-(?P<no>[0-9]+)\s*$", re.I
)

# Extend HTTP Error Messages
AWS_HTTP_ERROR_MAP = {
    403: "Unauthorized - Invalid Access/Secret Key Combination.",
}


class NotifyAWSWhatsApp(NotifyBase):
    """A wrapper for AWS End User Messaging Social (WhatsApp)"""

    # The default descriptive name associated with the Notification
    service_name = "AWS End User Messaging Social (WhatsApp)"

    # The services URL
    service_url = "https://aws.amazon.com/end-user-messaging/"

    # The default secure protocol
    secure_protocol = "awswhatsapp"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/awswhatsapp/"

    # Support attachments (staged in the S3 ?bucket=)
    attachment_support = True

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # The Meta API version AWS relays our messages with; bump this when Meta
    # deprecates the current one.
    meta_api_version = "v23.0"

    # The maximum length of the body
    body_maxlen = 1024

    # A title can not be used for WhatsApp Messages.  Setting this to zero
    # will cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        # With session token (for temporary/IAM credentials)
        "{schema}://{token}@{access_key_id}/{secret_access_key}"
        "/{region}/{from_phone_id}/{targets}",
        # Without session token (standard long-term credentials)
        "{schema}://{access_key_id}/{secret_access_key}"
        "/{region}/{from_phone_id}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                # Session token for temporary/IAM credentials (optional)
                "name": _("Session Token"),
                "type": "string",
                "private": True,
                "map_to": "session_token",
            },
            "access_key_id": {
                "name": _("Access Key ID"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "secret_access_key": {
                "name": _("Secret Access Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "region": {
                "name": _("Region"),
                "type": "string",
                "regex": (r"^[a-z]{2}-[a-z-]+?-[0-9]+$", "i"),
                "required": True,
                "map_to": "region_name",
            },
            "from_phone_id": {
                "name": _("From Phone ID"),
                "type": "string",
                "regex": (r"^phone-number-id-[a-z0-9]+$", "i"),
                "required": True,
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
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
            "token": {
                # ?token= kwarg mirrors the {token} URL path entry
                "alias_of": "token",
            },
            "access": {
                "alias_of": "access_key_id",
            },
            "key": {
                # Intuitive alias for access_key_id
                "alias_of": "access_key_id",
            },
            "secret": {
                "alias_of": "secret_access_key",
            },
            "region": {
                "alias_of": "region",
            },
            "template": {
                "name": _("Template Name"),
                "type": "string",
                "regex": (r"^[^\s]+$", "i"),
            },
            "lang": {
                "name": _("Language"),
                "type": "string",
                "default": "en_US",
                "regex": (r"^[^0-9\s]+$", "i"),
                "map_to": "language",
            },
            "bucket": {
                "name": _("S3 Bucket"),
                "type": "string",
                "regex": (r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", "i"),
            },
        },
    )

    # A template component is either a position (1, 2, ...) or a name
    component_key_re = re.compile(r"[1-9][0-9]*|[a-z_][a-z0-9_]*")

    # Define any kwargs we're using
    template_kwargs = {
        "template_mapping": {
            "name": _("Template Mapping"),
            "prefix": ":",
        },
    }

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        region_name: str,
        from_phone_id: str,
        targets: Optional[Any] = None,
        session_token: Optional[str] = None,
        template: Optional[str] = None,
        language: Optional[str] = None,
        template_mapping: Optional[dict[str, str]] = None,
        bucket: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Notify AWS WhatsApp Object."""
        super().__init__(**kwargs)

        # Store optional session token for temporary/IAM credentials
        self.aws_session_token = session_token if session_token else None

        # Store our AWS API Access Key
        self.aws_access_key_id = validate_regex(access_key_id)
        if not self.aws_access_key_id:
            msg = "An invalid AWS Access Key ID was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Store our AWS API Secret Access key
        self.aws_secret_access_key = validate_regex(secret_access_key)
        if not self.aws_secret_access_key:
            msg = "An invalid AWS Secret Access Key was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Acquire our AWS Region Name:
        # eg. us-east-1, cn-north-1, us-west-2, ...
        self.aws_region_name = validate_regex(
            region_name, *self.template_tokens["region"]["regex"]
        )
        if not self.aws_region_name:
            msg = f"An invalid AWS Region ({region_name}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Acquire our sender (phone number) ID
        self.from_phone_id = validate_regex(
            from_phone_id, *self.template_tokens["from_phone_id"]["regex"]
        )
        if not self.from_phone_id:
            msg = (
                "An invalid AWS WhatsApp From Phone ID "
                f"({from_phone_id}) was specified."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The template to associate with the message
        self.template = None
        if template:
            self.template = validate_regex(
                template, *self.template_args["template"]["regex"]
            )
            if not self.template:
                msg = (
                    "An invalid AWS WhatsApp Template Name "
                    f"({template}) was specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # The Template language Code to use
        self.language = self.template_args["lang"]["default"]
        if language:
            self.language = validate_regex(
                language, *self.template_args["lang"]["regex"]
            )
            if not self.language:
                msg = (
                    "An invalid AWS WhatsApp Template Language Code "
                    f"({language}) was specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # The private S3 bucket attachments are staged in
        self.bucket = None
        if bucket:
            self.bucket = validate_regex(
                bucket, *self.template_args["bucket"]["regex"]
            )
            if not self.bucket:
                msg = f"An invalid AWS S3 Bucket ({bucket}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        self.template_mapping = {}
        if template_mapping:
            # Store our extra payload entries
            self.template_mapping.update(template_mapping)

        # Validate Mapping and prepare Components
        self.components = {}
        for key, val in self.template_mapping.items():
            if key.lower() in ("body", "type"):
                # The message body (or type) fills the component named
                # by our value
                index = val
                map_to = key.lower()

            else:
                # Manual Component Assignment (by position or name)
                index = key
                map_to = {"type": "text", "text": val}

            if not self.component_key_re.fullmatch(index):
                msg = (
                    "An invalid AWS WhatsApp Template Component ID "
                    f"({index}) was specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            if index in self.components:
                msg = (
                    "The AWS WhatsApp Template Component index "
                    f"({index}) was already assigned."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            self.components[index] = map_to

        # A template uses either named or positional parameters, never both
        positional = sum(index.isdigit() for index in self.components)
        if 0 < positional < len(self.components):
            msg = (
                "Named and positional AWS WhatsApp Template Components "
                "cannot be mixed."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Named templates must identify every value by its name
        self.named_components = bool(self.components) and not positional

        # Our API hosts
        self.notify_host = (
            f"social-messaging.{self.aws_region_name}.amazonaws.com"
        )
        self.s3_host = f"{self.bucket}.s3.{self.aws_region_name}.amazonaws.com"

        # AWS Authentication Details
        self.aws_auth_version = "AWS4"
        self.aws_auth_algorithm = "AWS4-HMAC-SHA256"
        self.aws_auth_request = "aws4_request"

        # Parse our targets
        self.targets = []
        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    "Dropped invalid AWS WhatsApp target (%s) specified.",
                    target,
                )
                continue

            # AWS keeps the leading plus (E.164) on phone numbers
            self.targets.append("+{}".format(result["full"]))

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        attach: Optional[Any] = None,
        **kwargs: Any,
    ) -> bool:
        """Perform AWS WhatsApp Notification."""

        if not self.targets:
            # There were no services to notify
            self.logger.warning(
                "There were no AWS WhatsApp targets to notify."
            )
            return False

        # Prepare the messages every target receives
        messages = []
        if self.template:
            #
            # Send Template
            #
            template = {
                "name": self.template,
                "language": {"code": self.language},
            }

            if self.components:
                # Template parameters are placed in index order
                values = {"body": body, "type": notify_type.value}
                parameters = []
                for key in sorted(
                    self.components,
                    key=None if self.named_components else int,
                ):
                    # A literal value, or our message body (or type)
                    component = self.components[key]
                    parameter = (
                        dict(component)
                        if isinstance(component, dict)
                        else {"type": "text", "text": values[component]}
                    )

                    if self.named_components:
                        # Named templates identify each value by its name
                        parameter["parameter_name"] = key

                    parameters.append(parameter)

                template["components"] = [
                    {"type": "body", "parameters": parameters}
                ]

            messages.append({"type": "template", "template": template})

        elif body:
            #
            # Send Message
            #
            messages.append({"type": "text", "text": {"body": body}})

        if attach and self.attachment_support:
            if not self.bucket:
                self.logger.warning(
                    "AWS WhatsApp attachments require a ?bucket= to be "
                    "staged in."
                )
                return False

            for attachment in attach:
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.warning(
                        "Could not access AWS WhatsApp attachment %s.",
                        attachment.url(privacy=True),
                    )
                    return False

                media_id = self._upload(attachment)
                if not media_id:
                    # The failure was already logged
                    return False

                # Images, audio and video are sent as such; anything else
                # is sent as a document (which keeps its file name)
                kind = attachment.mimetype.split("/")[0]
                content = {"id": media_id}
                if kind not in ("image", "audio", "video"):
                    kind = "document"
                    content["filename"] = attachment.name or "attachment.dat"

                # Each attachment is sent as its own message
                messages.append({"type": kind, kind: content})

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            for no, message in enumerate(messages):
                # Skip a message this target already accepted so a retry
                # does not deliver it twice.
                if self.is_delivered((target, no)):
                    continue

                # AWS takes the WhatsApp message as base64 encoded JSON
                content = dumps(
                    {"messaging_product": "whatsapp", "to": target, **message}
                )
                payload = {
                    "originationPhoneNumberId": self.from_phone_id,
                    "metaApiVersion": self.meta_api_version,
                    "message": b64encode(content.encode("utf-8")).decode(),
                }

                status, _ = self._post("/v1/whatsapp/send", payload, target)
                if not status:
                    # Mark our failure
                    has_error = True
                    continue

                self.logger.info(
                    "Sent AWS WhatsApp notification to %s.", target
                )

                # Delivered; a retry can safely skip this message.
                self.mark_delivered((target, no))

        return not has_error

    def _upload(self, attachment: AttachBase) -> Optional[str]:
        """Stage an attachment in S3, have WhatsApp import it, then remove
        it from S3 again.

        Returns the WhatsApp media ID, or None if the upload failed.
        """

        # Every upload is given its own name
        key = f"apprise/{uuid4().hex}"

        if not self._s3(key, attachment):
            # The failure was already logged
            return None

        try:
            # Have WhatsApp import the file we just staged
            status, response = self._post(
                "/v1/whatsapp/media",
                {
                    "originationPhoneNumberId": self.from_phone_id,
                    "sourceS3File": {"bucketName": self.bucket, "key": key},
                },
                attachment.name,
            )

            media_id = response.get("mediaId") if status else None
            if status and not media_id:
                self.logger.warning(
                    "AWS WhatsApp did not return a media ID for %s.",
                    attachment.name,
                )

            return media_id

        finally:
            # WhatsApp keeps its own copy; remove the one we staged
            self._s3(key)

    def _s3(self, key: str, attachment: Optional[AttachBase] = None) -> bool:
        """Upload an attachment to our S3 bucket, or delete the object when
        no attachment is provided."""

        # Prepare our URL
        uri = "/{}".format(quote(key))
        url = f"https://{self.s3_host}{uri}"

        headers = {
            "User-Agent": self.app_id,
            # Our file is streamed, so it is not hashed into the signature
            # (S3 allows this over https)
            "X-Amz-Content-Sha256": "UNSIGNED-PAYLOAD",
        }

        handle = None
        try:
            if attachment:
                # Open our attachment
                handle = attachment.open()
                headers["Content-Type"] = attachment.mimetype

            # Prepare our AWS Headers
            headers = self.aws_prepare_request(
                "PUT" if attachment else "DELETE",
                self.s3_host,
                uri,
                "s3",
                "UNSIGNED-PAYLOAD",
                headers,
            )

            self.logger.debug(
                "AWS S3 URL: %s (cert_verify=%r)",
                url,
                self.verify_certificate,
            )

            r = (requests.put if attachment else requests.delete)(
                url,
                data=handle,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code not in (
                requests.codes.ok,
                requests.codes.no_content,
            ):
                # We had a problem
                status_str = NotifyAWSWhatsApp.http_response_code_lookup(
                    r.status_code, AWS_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to %s AWS S3 object %s: %s%serror=%d.",
                    "upload" if attachment else "remove",
                    key,
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )
                return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred with AWS S3 object %s.", key
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        except OSError as e:
            self.logger.warning(
                "An I/O error occurred while reading %s.", attachment.name
            )
            self.logger.debug("I/O Exception: %s", str(e))
            return False

        finally:
            # Close our file handle (if one was opened)
            if handle:
                handle.close()

        return True

    def _post(
        self, uri: str, payload: dict[str, Any], to: str
    ) -> tuple[bool, dict[str, Any]]:
        """Wrapper to request.post() to manage it's response better and make
        the send() function cleaner and easier to maintain.

        This function returns a (status, response) tuple.
        """

        # Always call throttle before any remote server i/o is made; for AWS
        # time plays a huge factor in the headers being sent with the payload.
        # So for AWS requests we must throttle before they're generated and
        # not directly before the i/o call like other notification services
        # do.
        self.throttle()

        # Prepare our payload and URL
        payload = dumps(payload)
        url = f"https://{self.notify_host}{uri}"

        # Prepare our AWS Headers based on our payload
        headers = self.aws_prepare_request(
            "POST",
            self.notify_host,
            uri,
            "social-messaging",
            sha256(payload.encode("utf-8")).hexdigest(),
            {
                "User-Agent": self.app_id,
                "Content-Type": "application/json",
            },
        )

        self.logger.debug(
            "AWS WhatsApp POST URL: %s (cert_verify=%r)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("AWS WhatsApp Payload (%d bytes)", len(payload))

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
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyAWSWhatsApp.http_response_code_lookup(
                    r.status_code, AWS_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send AWS WhatsApp notification to %s: "
                    "%s%serror=%d.",
                    to,
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )
                return (False, {})

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending AWS WhatsApp "
                "notification to %s.",
                to,
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return (False, {})

        return (True, content if isinstance(content, dict) else {})

    def aws_prepare_request(
        self,
        method: str,
        host: str,
        uri: str,
        service: str,
        payload_hash: str,
        headers: dict[str, str],
    ) -> dict[str, str]:
        """Takes the headers we intend to send and returns them signed using
        AWS Signature Version 4.

        The payload_hash is the sha256 hex digest of the payload being sent.
        """

        # Get a reference time (used for header construction)
        reference = datetime.now(timezone.utc)

        # Amazon Date Format
        amzdate = reference.strftime("%Y%m%dT%H%M%SZ")
        headers["X-Amz-Date"] = amzdate

        # Include our session token for temporary credentials
        if self.aws_session_token:
            headers["X-Amz-Security-Token"] = self.aws_session_token

        # Credential Scope
        scope = "{date}/{region}/{service}/{request}".format(
            date=reference.strftime("%Y%m%d"),
            region=self.aws_region_name,
            service=service,
            request=self.aws_auth_request,
        )

        # Similar to headers; but a subset.  keys must be lowercase and
        # sorted alphabetically
        signed_headers = dict(
            sorted(
                [("host", host)]
                + [
                    (k.lower(), v)
                    for k, v in headers.items()
                    if k.lower() == "content-type"
                    or k.lower().startswith("x-amz-")
                ]
            )
        )

        #
        # Build Canonical Request Object
        #
        canonical_request = "\n".join(
            [
                # Method
                method,
                # URL
                uri,
                # Query String (none set)
                "",
                # Header Content (must include \n at end!)
                # All entries except characters in amazon date must be
                # lowercase
                "\n".join([f"{k}:{v}" for k, v in signed_headers.items()])
                + "\n",
                # Header Entries (in same order identified above)
                ";".join(signed_headers.keys()),
                # Payload
                payload_hash,
            ]
        )

        # Prepare Unsigned Signature
        to_sign = "\n".join(
            [
                self.aws_auth_algorithm,
                amzdate,
                scope,
                sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )

        # Our Authorization header
        headers["Authorization"] = ", ".join(
            [
                (
                    f"{self.aws_auth_algorithm} "
                    f"Credential={self.aws_access_key_id}/{scope}"
                ),
                "SignedHeaders={signed_headers}".format(
                    signed_headers=";".join(signed_headers.keys()),
                ),
                "Signature={}".format(
                    self.aws_auth_signature(to_sign, reference, service)
                ),
            ]
        )

        return headers

    def aws_auth_signature(
        self, to_sign: str, reference: datetime, service: str
    ) -> str:
        """Generates a AWS v4 signature based on provided payload which should
        be in the form of a string."""

        def _sign(key: bytes, msg: str, to_hex: bool = False) -> Any:
            """Perform AWS Signing."""
            if to_hex:
                return hmac.new(key, msg.encode("utf-8"), sha256).hexdigest()
            return hmac.new(key, msg.encode("utf-8"), sha256).digest()

        date = _sign(
            (self.aws_auth_version + self.aws_secret_access_key).encode(
                "utf-8"
            ),
            reference.strftime("%Y%m%d"),
        )

        region = _sign(date, self.aws_region_name)
        signed_service = _sign(region, service)
        signed = _sign(signed_service, self.aws_auth_request)
        return _sign(signed, to_sign, to_hex=True)

    @property
    def url_identifier(self) -> tuple[str, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.aws_access_key_id,
            self.aws_secret_access_key,
            self.aws_region_name,
            self.from_phone_id,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.template:
            # Add our template and its language to our URL
            params["template"] = self.template
            params["lang"] = self.language

        if self.bucket:
            # Our attachment staging bucket
            params["bucket"] = self.bucket

        # Payload body extras prefixed with a ':' sign
        # Append our payload extras into our parameters
        params.update({f":{k}": v for k, v in self.template_mapping.items()})

        # Prepare session token prefix when using temporary credentials;
        # + and = are RFC 3986 sub-delimiters safe in the userinfo position
        # and look nicer unencoded; / must stay encoded (%2F) because an
        # unencoded slash terminates the URL authority and breaks parsing
        token_prefix = (
            "{token}@".format(
                token=self.pprint(self.aws_session_token, privacy, safe="+="),
            )
            if self.aws_session_token
            else ""
        )

        return (
            "{schema}://{token_prefix}{key_id}/{key_secret}/{region}"
            "/{from_id}/{targets}/?{params}".format(
                schema=self.secure_protocol,
                token_prefix=token_prefix,
                key_id=self.pprint(self.aws_access_key_id, privacy, safe=""),
                key_secret=self.pprint(
                    self.aws_secret_access_key,
                    privacy,
                    mode=PrivacyMode.Secret,
                    safe="",
                ),
                region=NotifyAWSWhatsApp.quote(self.aws_region_name, safe=""),
                from_id=NotifyAWSWhatsApp.quote(self.from_phone_id, safe=""),
                targets="/".join(
                    [NotifyAWSWhatsApp.quote(x) for x in self.targets]
                ),
                params=NotifyAWSWhatsApp.urlencode(params),
            )
        )

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        targets = len(self.targets)
        return targets if targets > 0 else 1

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The AWS Access Key ID is stored in the hostname
        access_key_id = NotifyAWSWhatsApp.unquote(results["host"])

        # Our AWS Access Key Secret contains slashes in it which unfortunately
        # means it is of variable length after the hostname.  Since we require
        # that the user provides the region code, we intentionally use this
        # as our delimiter to detect where our Secret is.
        secret_access_key = None
        region_name = None

        # We need to iterate over each entry in the fullpath and find our
        # region. Once we get there we stop and build our secret from our
        # accumulated data.
        secret_access_key_parts = []

        # Start with a list of entries to work with
        entries = NotifyAWSWhatsApp.split_path(results["fullpath"])

        # Section 1: Get Region and Access Secret
        index = 0
        for i, entry in enumerate(entries):
            # Are we at the region yet?
            result = IS_REGION.match(entry)
            if result:
                # We found our Region; Rebuild our access key secret based on
                # all entries we found prior to this:
                secret_access_key = "/".join(secret_access_key_parts)

                # Ensure region is nicely formatted
                region_name = "{country}-{area}-{no}".format(
                    country=result.group("country").lower(),
                    area=result.group("area").lower(),
                    no=result.group("no"),
                )

                # Track our index as we'll use this to grab the remaining
                # content in the next Section
                index = i + 1

                # We're done with Section 1
                break

            # Store our secret parts
            secret_access_key_parts.append(entry)

        # Section 2: Our From Phone ID directly follows our region and our
        # Recipients are basically all remaining entries
        results["from_phone_id"] = None
        results["targets"] = []
        if index:
            results["from_phone_id"] = (
                entries[index] if index < len(entries) else None
            )
            results["targets"] = entries[index + 1 :]

        # Support the 'to' variable so that we can support targets this way
        # too. The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyAWSWhatsApp.parse_phone_no(
                results["qsd"]["to"]
            )

        # Handle secret_access_key over-ride
        if "secret" in results["qsd"] and len(results["qsd"]["secret"]):
            results["secret_access_key"] = NotifyAWSWhatsApp.unquote(
                results["qsd"]["secret"]
            )
        else:
            results["secret_access_key"] = secret_access_key

        # Handle access key id override; ?key= is the preferred alias,
        # ?access= is also supported
        if "key" in results["qsd"] and len(results["qsd"]["key"]):
            results["access_key_id"] = NotifyAWSWhatsApp.unquote(
                results["qsd"]["key"]
            )
        elif "access" in results["qsd"] and len(results["qsd"]["access"]):
            results["access_key_id"] = NotifyAWSWhatsApp.unquote(
                results["qsd"]["access"]
            )
        else:
            results["access_key_id"] = access_key_id

        # Handle region name id over-ride
        if "region" in results["qsd"] and len(results["qsd"]["region"]):
            results["region_name"] = NotifyAWSWhatsApp.unquote(
                results["qsd"]["region"]
            )
        else:
            results["region_name"] = region_name

        # Session token: userinfo position ({token}@{host}) takes first pass;
        # ?token= kwarg overrides it when both appear
        results["session_token"] = None
        if results.get("user"):
            results["session_token"] = NotifyAWSWhatsApp.unquote(
                results["user"]
            )
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            results["session_token"] = NotifyAWSWhatsApp.unquote(
                results["qsd"]["token"]
            )

        # Template
        if "template" in results["qsd"] and len(results["qsd"]["template"]):
            results["template"] = NotifyAWSWhatsApp.unquote(
                results["qsd"]["template"]
            )

        # Template Language
        if "lang" in results["qsd"] and len(results["qsd"]["lang"]):
            results["language"] = NotifyAWSWhatsApp.unquote(
                results["qsd"]["lang"]
            )

        # Attachment staging bucket
        if "bucket" in results["qsd"] and len(results["qsd"]["bucket"]):
            results["bucket"] = NotifyAWSWhatsApp.unquote(
                results["qsd"]["bucket"]
            )

        # Store our template mapping
        results["template_mapping"] = results["qsd:"]

        return results
