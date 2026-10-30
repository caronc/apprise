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

# Whapi.Cloud sends WhatsApp messages from your own WhatsApp number by
# linking it the same way WhatsApp Web does (by scanning a QR code).
#
#  1. Sign up at https://panel.whapi.cloud/ and open (or create) a
#     Channel.
#  2. Scan the QR code shown with WhatsApp on your phone
#     (Settings > Linked Devices > Link a Device).
#  3. Copy the API Token shown on the Channel page.
#
#  Your Apprise URL should be assembled as:
#     whapi://{token}/{phone}
#     whapi://{token}/{phone}/{group_id}
#
#  Phone numbers are given in international format.  Group IDs can be
#  found with the Whapi.Cloud "Get groups" call and may be given either as
#  the bare number or as the full ID ending in @g.us.  Any other chat ID
#  (such as one ending in @newsletter for a WhatsApp Channel) is passed
#  along as-is.
#
# Resources:
# - https://whapi.readme.io/reference/sendmessagetext
# - https://whapi.readme.io/reference/sendmediamessage

from __future__ import annotations

from json import dumps, loads
import re
from typing import Any, Optional

import requests

from ..attachment.base import AttachBase
from ..common import NotifyFormat, NotifyType
from ..conversion import (
    commonmark_decode_backslash_escapes,
    commonmark_emphasis_run,
    commonmark_find_backtick_run,
    commonmark_headings_to_bold,
    commonmark_index_backtick_runs,
    commonmark_new_scan_budget,
    commonmark_pick_emphasis_sentinel,
    commonmark_render_emphasis_markers,
    commonmark_scan_angle_dest,
    commonmark_scan_autolink_dest,
    commonmark_scan_paren_dest,
)
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import (
    is_phone_no,
    parse_bool,
    parse_phone_no,
    validate_regex,
)
from .base import NotifyBase

# Extend HTTP Error Messages
# Based on: https://whapi.readme.io/reference/sendmessagetext
WHAPI_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid Token or Channel not linked.",
    402: "Trial limit exceeded.",
    403: "Sending to this recipient is forbidden.",
    413: "Request too large.",
    429: "Too many requests were made.",
}

# A group ID is 16 or more digits, well past the 15 digit phone number
# maximum.  Older groups use the form {creator_phone}-{timestamp}.
IS_GROUP_ID = re.compile(r"^(?P<id>[0-9]{16,}|[0-9]{10,}-[0-9]{10,})$")

# Any full chat ID such as 120363...@g.us or 120363...@newsletter
IS_CHAT_ID = re.compile(r"^[^\s@/]+@[a-z0-9.]+$", re.I)

# The media types Whapi.Cloud can show inline; anything else is a document
WHAPI_MEDIA_TYPES = {
    "image/jpeg": "image",
    "image/png": "image",
    "video/mp4": "video",
    "video/3gpp": "video",
}


class NotifyWhapi(NotifyBase):
    """A wrapper for Whapi.Cloud (WhatsApp) Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Whapi.Cloud"

    # The services URL
    service_url = "https://whapi.cloud/"

    # The default secure protocol
    secure_protocol = "whapi"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/whapi/"

    # Text message URL
    notify_url = "https://gate.whapi.cloud/messages/text"

    # Media message URL; the media type is filled in at send time
    media_url = "https://gate.whapi.cloud/messages/media/{kind}"

    # Files can be sent along with our message
    attachment_support = True

    # The maximum length of a WhatsApp text message
    body_maxlen = 4096

    # WhatsApp messages have no title field.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # WhatsApp has its own Markdown-like formatting
    notify_format = NotifyFormat.MARKDOWN

    # Define object URL templates
    templates = ("{schema}://{token}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Access Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9_-]+$", "i"),
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
                "map_to": "targets",
            },
            "target_group": {
                "name": _("Target Group ID"),
                "type": "string",
                "regex": (r"^[0-9-]+(@g\.us)?$", "i"),
                "map_to": "targets",
            },
            "target_chat": {
                "name": _("Target Chat ID"),
                "type": "string",
                "regex": (r"^[^\s@/]+@[a-z0-9.]+$", "i"),
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
            "token": {
                "alias_of": "token",
            },
            "preview": {
                "name": _("Web Page Preview"),
                "type": "bool",
                "default": True,
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self,
        token: Optional[str] = None,
        targets: Optional[Any] = None,
        preview: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Whapi.Cloud Object."""
        super().__init__(**kwargs)

        # Our Channel API Token
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"An invalid Whapi.Cloud Token ({token}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Show a preview of the first link in our message
        self.preview = (
            self.template_args["preview"]["default"]
            if preview is None
            else parse_bool(preview)
        )

        # The chat IDs we will notify
        self.targets = []

        # Anything we could not make sense of; kept for url()
        self.invalid_targets = []

        for target in parse_phone_no(targets):
            # A full chat ID is passed along as-is
            if IS_CHAT_ID.match(target):
                self.targets.append(target)
                continue

            # A bare group ID needs its @g.us suffix
            result = IS_GROUP_ID.match(target)
            if result:
                self.targets.append(f"{result.group('id')}@g.us")
                continue

            # Otherwise we expect a phone number
            result = is_phone_no(target)
            if result:
                # Whapi.Cloud wants the digits only
                self.targets.append(result["full"])
                continue

            self.logger.warning(
                "Dropped invalid Whapi.Cloud target (%s) specified.", target
            )
            self.invalid_targets.append(target)

        return

    # Adapt HTML-derived CommonMark to WhatsApp formatting.
    # Direct WhatsApp Markdown is left unchanged.
    # Syntax: https://faq.whatsapp.com/539178204879377/
    @staticmethod
    def _append_whatsapp_link(
        out: list[str], open_index: int, raw_url: str
    ) -> None:
        """Replace a buffered link with WhatsApp's ``label (url)`` form.

        CommonMark escapes are decoded and closing parentheses are protected.
        """
        url = commonmark_decode_backslash_escapes(raw_url)

        # Recover the buffered label and remove its opening ``[``.
        text = "".join(out[open_index + 1 :])
        del out[open_index:]

        # Protect wrapper parentheses from URL content.
        safe_url = url.replace(")", "%29")

        # Omit the label when only a bare URL is available.
        out.append(f"{text} ({safe_url})" if text else safe_url)

    def dialect_convert(
        self,
        body: str,
        body_format: Optional[NotifyFormat] = None,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Translate repaired CommonMark to WhatsApp formatting."""
        if body_format != NotifyFormat.MARKDOWN:
            return body
        return self._commonmark_to_whatsapp(body)

    @classmethod
    def _commonmark_to_whatsapp(cls, body: str) -> str:
        """Translate CommonMark to WhatsApp formatting.

        CommonMark          WhatsApp
        ------------------  ---------------------------
        # heading           *heading* (WhatsApp has no heading syntax)
        **bold**            *bold*
        *italic*            _italic_
        `code`              ```code``` (triple backticks)
        [label](<url>)      label (url)
        \\*                 *

        WhatsApp auto-links bare URLs but has no custom-label link syntax.
        Backslash escapes are removed because WhatsApp does not use them.
        """
        # WhatsApp represents headings as bold while preserving code.
        body = commonmark_headings_to_bold(body)

        # Accumulate translated characters one item at a time.
        out = []
        # Record ``*`` and ``_`` markup in order, then match it after the scan.
        delimiters = []
        # Track possible link-label openings in LIFO order.
        link_stack = []

        # Initialize the single-pass scanner.
        i = 0
        n = len(body)

        # Record backtick positions so matching code spans is quick.
        backtick_runs = commonmark_index_backtick_runs(body)
        # Pick a temporary marker that does not occur in the message.
        sentinel = commonmark_pick_emphasis_sentinel(body)
        # Bound the total work spent scanning labeled-link destinations.
        scan_budget = commonmark_new_scan_budget(body)

        while i < n:
            ch = body[i]

            # Drop CommonMark escapes because WhatsApp does not use them.
            if ch == "\\" and i + 1 < n:
                out.append(body[i + 1])
                i += 2
                continue

            # Normalize matched CommonMark code spans to triple backticks.
            if ch == "`":
                j = i
                # Measure the run length by counting consecutive backticks.
                while j < n and body[j] == "`":
                    j += 1
                run = j - i
                # Search the pre-built index for the next matching close run.
                close = commonmark_find_backtick_run(backtick_runs, j, run)

                if close is not None:
                    # WhatsApp uses triple backticks for monospace text.
                    # Collapse runs of three or more backticks to two so
                    # embedded content cannot close the WhatsApp span early.
                    content = re.sub(r"`{3,}", "``", body[j:close])
                    out.append("```" + content + "```")
                    # Skip past the closing backtick run.
                    i = close + run
                    continue

                # Preserve unmatched backticks as literal text.
                out.append(body[i:j])
                i = j
                continue

            # Record a possible CommonMark link-label opening.
            if ch == "[":
                link_stack.append(len(out))
                out.append("[")
                i += 1
                continue

            # Convert a complete CommonMark link to ``label (url)``.
            if body.startswith("](<", i) and link_stack:
                # Scan forward with escape awareness for the ">)" terminator.
                close = commonmark_scan_angle_dest(
                    body, i, n, budget=scan_budget
                )

                if close is not None:
                    raw_url = body[i + 3 : close]
                    open_index = link_stack.pop()
                    cls._append_whatsapp_link(out, open_index, raw_url)
                    # Skip past the closing ">)" of the destination.
                    i = close + 2
                    continue

                # Let the bare-link check handle this failed angle form.

            # Convert bare destinations without scanning their URL as emphasis.
            if body.startswith("](", i) and link_stack:
                close = commonmark_scan_paren_dest(
                    body, i + 1, n, budget=scan_budget
                )

                if close is not None:
                    raw_url = body[i + 2 : close]
                    open_index = link_stack.pop()
                    cls._append_whatsapp_link(out, open_index, raw_url)
                    # Skip past the closing ")" of the destination.
                    i = close + 1
                    continue

                # Same reasoning as the angle-dest case above.
                link_stack.pop()

            # A "]" that never forms "](" cannot close a link. Retire the
            # innermost pending "[" so a later, unrelated "](" cannot
            # incorrectly reuse it as its own opener.
            if ch == "]" and link_stack and not body.startswith("](", i):
                link_stack.pop()

            # Drop autolink brackets; WhatsApp recognizes the remaining URL.
            if ch == "<":
                close, still_valid = commonmark_scan_autolink_dest(body, i, n)
                if close is not None:
                    out.append(body[i + 1 : close])
                    i = close + 1
                    continue
                if not still_valid:
                    # Not an autolink -- fall through as a literal "<".
                    out.append(ch)
                    i += 1
                    continue
                # Ignore markup characters inside an unfinished autolink.
                out.append(body[i:])
                i = n
                continue

            # Map CommonMark emphasis to WhatsApp's ``*``/``_`` syntax.
            if ch == "*":
                i = commonmark_emphasis_run(
                    body, i, n, delimiters, out, sentinel
                )
                continue

            # Preserve ordinary characters.
            out.append(ch)
            i += 1

        # Replace temporary markers with WhatsApp bold and italic markup.
        return commonmark_render_emphasis_markers(
            "".join(out), delimiters, ("*", "*"), ("_", "_"), sentinel
        )

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        attach: Optional[list[AttachBase]] = None,
        **kwargs: Any,
    ) -> bool:
        """Perform Whapi.Cloud Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning("There are no Whapi.Cloud targets to notify.")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            # A message made of attachments alone has no text to send.
            # Skip a target that already accepted this message so a retry
            # does not deliver it twice.
            if body and not self.is_delivered(target):
                # Prepare our payload
                payload = {"to": target, "body": body}
                if not self.preview:
                    payload["no_link_preview"] = True

                if not self._send(
                    self.notify_url,
                    target,
                    headers=dict(
                        headers, **{"Content-Type": "application/json"}
                    ),
                    data=dumps(payload),
                ):
                    # Mark our failure; no files follow a failed message
                    has_error = True
                    continue

                # Delivered; a retry can safely skip this text.
                self.mark_delivered(target)

            for no, attachment in enumerate(attach or []):
                # Each file is tracked on its own so a retry only sends
                # the ones that did not make it.
                key = (target, no)
                if self.is_delivered(key):
                    continue

                # Verify our attachment is accessible before opening it
                if not attachment:
                    self.logger.warning(
                        "Could not access Whapi.Cloud attachment %s.",
                        attachment.url(privacy=True),
                    )

                    # Mark our failure
                    has_error = True
                    break

                # Pick how WhatsApp should present this file
                kind = WHAPI_MEDIA_TYPES.get(
                    attachment.mimetype,
                    "audio"
                    if attachment.mimetype.startswith("audio/")
                    else "document",
                )

                # Who it goes to, and the name shown for a document
                params = {"to": target}
                if kind == "document":
                    params["filename"] = attachment.name or "attachment.dat"

                handle = None
                try:
                    # The raw file is posted as our request body
                    handle = attachment.open()
                    delivered = self._send(
                        self.media_url.format(kind=kind),
                        target,
                        headers=dict(
                            headers, **{"Content-Type": attachment.mimetype}
                        ),
                        data=handle,
                        params=params,
                    )

                except OSError as e:
                    self.logger.warning(
                        "An I/O error occurred while reading %s.",
                        attachment.name or "attachment",
                    )
                    self.logger.debug("I/O Exception: %s", str(e))
                    delivered = False

                finally:
                    # Close our file whether we succeeded or failed
                    if handle:
                        handle.close()

                if not delivered:
                    # Mark our failure; later files wait for a retry
                    has_error = True
                    break

                # Delivered; a retry can safely skip this file.
                self.mark_delivered(key)

        return not has_error

    def _send(
        self,
        url: str,
        target: str,
        headers: dict[str, str],
        data: Any,
        params: Optional[dict[str, str]] = None,
    ) -> bool:
        """Post one message to Whapi.Cloud and return whether it was sent."""

        self.logger.debug(
            "Whapi.Cloud POST URL: %s (cert_verify=%r)",
            url,
            self.verify_certificate,
        )
        self.logger.debug(
            "Whapi.Cloud Payload: %s",
            data if isinstance(data, str) else params,
        )

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=data,
                params=params,
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

            # A successful response looks like:
            # {"sent": true, "message": {"id": "...", ...}}
            #
            # An error response looks like:
            # {"error": {"code": 401, "message": "..."}}
            if not isinstance(content, dict):
                content = {}

            if not 200 <= r.status_code < 300 or content.get("sent") is False:
                # Prefer Whapi.Cloud's own explanation when it gave one
                error = content.get("error")
                status_str = (
                    error.get("message") if isinstance(error, dict) else None
                ) or NotifyWhapi.http_response_code_lookup(
                    r.status_code, WHAPI_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Whapi.Cloud notification to %s: "
                    "%s%serror=%s.",
                    target,
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )
                return False

            self.logger.info("Sent Whapi.Cloud notification to %s.", target)

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Whapi.Cloud "
                "notification to %s.",
                target,
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        return True

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
        # The Channel token alone identifies the linked WhatsApp number
        return (self.secure_protocol, self.token)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = {}

        if self.preview != self.template_args["preview"]["default"]:
            params["preview"] = "yes" if self.preview else "no"

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{token}/{targets}?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            targets="/".join(
                NotifyWhapi.quote(x, safe="@+")
                for x in (self.targets + self.invalid_targets)
            ),
            params=NotifyWhapi.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The host is our Channel token
        results["token"] = NotifyWhapi.unquote(results["host"])

        # Our chat IDs are in the path
        results["targets"] = NotifyWhapi.split_path(results["fullpath"])

        # Allow the token to be given as ?token= instead
        if results["qsd"].get("token"):
            results["token"] = NotifyWhapi.unquote(results["qsd"]["token"])

        # Link preview toggle
        if "preview" in results["qsd"]:
            results["preview"] = parse_bool(results["qsd"]["preview"])

        # Support ?to= for targets
        if results["qsd"].get("to"):
            results["targets"] += NotifyWhapi.parse_phone_no(
                results["qsd"]["to"]
            )

        return results
