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

# Zoho Cliq posts messages using a Webhook Token:
#  1. Sign in to Zoho Cliq and open "Bots & Tools", then "Webhook Tokens".
#  2. Complete the two-factor check and click "Generate New Token".
#  3. Copy the token; it looks like:
#     1001.2798931fdf4905dc5d37806b47d8253a.2d73063dae2ccf4a04810ddb0a1b2c3d
#
#  Messages can go to a channel (by its unique name) or to a bot.  A
#  channel's unique name is shown in its "Channel Info" page.
#
#  Your Apprise URL should be assembled as:
#     cliq://{token}/#{channel}
#     cliq://{token}/@{bot}
#
#  Accounts hosted outside of the US data center add ?region= (for
#  example ?region=eu for cliq.zoho.eu).
#
#  Webhook Tokens can only post messages; uploading files requires a
#  full OAuth login, so attachments are not supported.
#
# Resources:
# - https://www.zoho.com/cliq/help/platform/webhook-tokens.html
# - https://www.zoho.com/cliq/help/restapi/v2/messages/
# - https://www.zoho.com/cliq/help/restapi/v2/messagecards/

from __future__ import annotations

from json import dumps
import re
from typing import Any, Optional

import requests

from ..common import NotifyFormat, NotifyImageSize, NotifyType
from ..conversion import (
    commonmark_emphasis_run,
    commonmark_find_backtick_run,
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
from ..utils.parse import parse_bool, parse_list, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
# Based on: https://www.zoho.com/cliq/help/restapi/v2/
CLIQ_HTTP_ERROR_MAP = {
    400: "Bad Request - Check the channel or bot name.",
    401: "Unauthorized - Invalid Webhook Token.",
    404: "The channel or bot could not be found.",
    429: "Too many requests were made.",
}


class CliqRegion:
    """The Zoho data centers that host Cliq accounts."""

    US = "us"
    EU = "eu"
    INDIA = "in"
    AUSTRALIA = "au"
    CHINA = "cn"
    JAPAN = "jp"
    SAUDI_ARABIA = "sa"
    UNITED_KINGDOM = "uk"
    CANADA = "ca"


# Each region and the Cliq domain it is reached on
CLIQ_REGION_DOMAINS = {
    CliqRegion.US: "cliq.zoho.com",
    CliqRegion.EU: "cliq.zoho.eu",
    CliqRegion.INDIA: "cliq.zoho.in",
    CliqRegion.AUSTRALIA: "cliq.zoho.com.au",
    CliqRegion.CHINA: "cliq.zoho.com.cn",
    CliqRegion.JAPAN: "cliq.zoho.jp",
    CliqRegion.SAUDI_ARABIA: "cliq.zoho.sa",
    CliqRegion.UNITED_KINGDOM: "cliq.zoho.uk",
    CliqRegion.CANADA: "cliq.zohocloud.ca",
}

# Look up a region from the domain found in a pasted Cliq URL
CLIQ_DOMAIN_REGIONS = {v: k for k, v in CLIQ_REGION_DOMAINS.items()}

# The regions in the order they are offered to users
CLIQ_REGIONS = tuple(CLIQ_REGION_DOMAINS.keys())

# A channel is the default target, so its "#" is optional
IS_CHANNEL = re.compile(r"^#?(?P<name>[A-Z0-9_.-]+)$", re.I)

# A bot is always written with a leading "@"
IS_BOT = re.compile(r"^@(?P<name>[A-Z0-9_.-]+)$", re.I)


class NotifyCliq(NotifyBase):
    """A wrapper for Zoho Cliq Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Zoho Cliq"

    # The services URL
    service_url = "https://www.zoho.com/cliq/"

    # The default secure protocol; the extra names are accepted aliases
    secure_protocol = ("cliq", "zcliq", "zohocliq")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/cliq/"

    # Our message URL; {path} is "channelsbyname" or "bots"
    notify_url = "https://{domain}{company}/api/v2/{path}/{name}/message"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # Cliq renders its own flavour of Markdown
    notify_format = NotifyFormat.MARKDOWN

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 5000

    # The title is shown in a message card above the body
    title_maxlen = 200

    # Define object URL templates
    templates = (
        "{schema}://{token}/{targets}",
        "{schema}://{botname}@{token}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Webhook Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[A-Z0-9]+(\.[A-Z0-9]+)+$", "i"),
            },
            "botname": {
                "name": _("Bot Name"),
                "type": "string",
            },
            "target_channel": {
                "name": _("Target Channel"),
                "type": "string",
                "prefix": "#",
                "map_to": "targets",
            },
            "target_bot": {
                "name": _("Target Bot"),
                "type": "string",
                "prefix": "@",
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
                "alias_of": "token",
            },
            "botname": {
                "alias_of": "botname",
            },
            "region": {
                "name": _("Region"),
                "type": "choice:string",
                "values": CLIQ_REGIONS,
                "default": CliqRegion.US,
            },
            "company": {
                "name": _("Company ID"),
                "type": "string",
            },
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
            "broadcast": {
                "name": _("Broadcast"),
                "type": "bool",
                "default": False,
            },
        },
    )

    def __init__(
        self,
        token: str,
        targets: Optional[Any] = None,
        botname: Optional[str] = None,
        region: Optional[str] = None,
        company: Optional[str] = None,
        include_image: bool = True,
        broadcast: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize Zoho Cliq Object."""
        super().__init__(**kwargs)

        # Our Webhook Token
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = (
                f"An invalid Zoho Cliq Webhook Token ({token}) was specified."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The data center our account lives in
        self.region = (
            region.strip().lower()
            if isinstance(region, str) and region.strip()
            else CliqRegion.US
        )
        if self.region not in CLIQ_REGION_DOMAINS:
            msg = f"An invalid Zoho Cliq region ({region}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Users belonging to more than one company can pick which one
        self.company = None
        if company:
            self.company = validate_regex(company, r"^[A-Z0-9_-]+$", "i")
            if not self.company:
                msg = (
                    f"An invalid Zoho Cliq Company ID ({company}) was"
                    " specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # The display name shown as the sender of our messages
        self.botname = botname.strip() if isinstance(botname, str) else None
        if not self.botname:
            self.botname = None

        # Show the Apprise image as the sender's avatar
        self.include_image = parse_bool(include_image)

        # Send bot messages to all of the bot's subscribers
        self.broadcast = parse_bool(broadcast)

        # Our channel and bot names, stored with their prefix
        self.targets = []

        # Anything we could not make sense of; kept for url()
        self.invalid_targets = []

        for target in parse_list(targets):
            # Bots must be checked first since "#" is optional on channels
            result = IS_BOT.match(target)
            if result:
                self.targets.append("@" + result.group("name"))
                continue

            result = IS_CHANNEL.match(target)
            if result:
                self.targets.append("#" + result.group("name"))
                continue

            self.logger.warning(
                "Dropped invalid Zoho Cliq target (%s) specified.", target
            )
            self.invalid_targets.append(target)

        return

    def dialect_convert(
        self,
        body: str,
        body_format: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Translate declared CommonMark to Zoho Cliq formatting."""
        # Only Markdown has anything for us to translate
        if body_format != NotifyFormat.MARKDOWN:
            return body
        return self._commonmark_to_cliq(body)

    # Adapt HTML-derived CommonMark to the Zoho Cliq formatting.
    # Direct Cliq formatting is left unchanged.
    # Syntax: https://www.zoho.com/cliq/help/chat-window/format-messages.html

    @classmethod
    def _commonmark_to_cliq(cls, body: str) -> str:
        """Translate CommonMark to Zoho Cliq formatting.

        CommonMark          Zoho Cliq
        ------------------  -----------------
        **bold**            *bold*
        *italic*            _italic_
        [label](<url>)      [label](url)
        <url>               url
        \\*                 *
        """
        # Accumulate translated characters one item at a time.
        out = []
        # Record ``*`` markup in order, then match it after the scan.
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

            # Drop CommonMark escapes because Cliq shows them literally.
            if ch == "\\" and i + 1 < n:
                out.append(body[i + 1])
                i += 2
                continue

            # Keep code spans as they are so their content is not styled.
            if ch == "`":
                j = i
                # Measure the run length by counting consecutive backticks.
                while j < n and body[j] == "`":
                    j += 1
                run = j - i
                # Search the pre-built index for the matching close run.
                close = commonmark_find_backtick_run(backtick_runs, j, run)

                # Unmatched backticks are kept as literal text.
                end = j if close is None else close + run
                out.append(body[i:end])
                i = end
                continue

            # Record a possible CommonMark link-label opening.
            if ch == "[":
                link_stack.append(len(out))
                out.append("[")
                i += 1
                continue

            # Unwrap ``[label](<url>)`` into Cliq's ``[label](url)``.
            if body.startswith("](<", i) and link_stack:
                # Scan forward with escape awareness for the ">)" terminator.
                close = commonmark_scan_angle_dest(
                    body, i, n, budget=scan_budget
                )

                if close is not None:
                    # Protect the wrapping parenthesis from URL content.
                    url = body[i + 3 : close].replace(")", "%29")
                    link_stack.pop()
                    out.append(f"]({url})")
                    # Skip past the closing ">)" of the destination.
                    i = close + 2
                    continue

                # Let the bare-link check handle this failed angle form.

            # Copy bare destinations without scanning their URL as emphasis.
            if body.startswith("](", i) and link_stack:
                close = commonmark_scan_paren_dest(
                    body, i + 1, n, budget=scan_budget
                )

                if close is not None:
                    link_stack.pop()
                    out.append(body[i : close + 1])
                    # Skip past the closing ")".
                    i = close + 1
                    continue

                # This "](" does not finish a link, so retire its opener.
                link_stack.pop()

            # A "]" that never forms "](" cannot close a link. Retire the
            # innermost pending "[" so a later, unrelated "](" cannot
            # incorrectly reuse it as its own opener.
            if ch == "]" and link_stack and not body.startswith("](", i):
                link_stack.pop()

            # Drop autolink brackets; Cliq links the remaining URL itself.
            if ch == "<":
                close = commonmark_scan_autolink_dest(body, i, n)[0]
                if close is not None:
                    out.append(body[i + 1 : close])
                    i = close + 1
                    continue

            # Map CommonMark emphasis to Cliq's ``*``/``_`` syntax.
            if ch == "*":
                i = commonmark_emphasis_run(
                    body, i, n, delimiters, out, sentinel
                )
                continue

            # Preserve ordinary characters.
            out.append(ch)
            i += 1

        # Replace temporary markers with Cliq bold and italic markup.
        return commonmark_render_emphasis_markers(
            "".join(out), delimiters, ("*", "*"), ("_", "_"), sentinel
        )

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform Zoho Cliq Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning(
                "There are no Zoho Cliq channels or bots to notify."
            )
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json; charset=utf-8",
        }

        # Our Webhook Token is passed on the URL
        params = {"zapikey": self.token}

        # Cliq needs text, so a title on its own becomes the text
        payload = {"text": body if body else title}

        # Otherwise the title is shown in a card above the message
        if title and body:
            payload["card"] = {
                "title": title,
                "theme": "modern-inline",
            }

        # Acquire our image url if configured to do so
        image_url = (
            None if not self.include_image else self.image_url(notify_type)
        )

        # Cliq requires a name whenever the sender is changed
        if self.botname or image_url:
            payload["bot"] = {"name": self.botname or self.app_id}
            if image_url:
                payload["bot"]["image"] = image_url

        # Users in more than one company include it in the URL path
        company = f"/company/{self.company}" if self.company else ""

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            # Skip a target that already accepted this message so a retry
            # does not deliver it twice.
            if self.is_delivered(target):
                continue

            # Our prefix tells us where the message is going
            is_bot = target[0] == "@"

            # Prepare our URL
            url = self.notify_url.format(
                domain=CLIQ_REGION_DOMAINS[self.region],
                company=company,
                path="bots" if is_bot else "channelsbyname",
                name=NotifyCliq.quote(target[1:], safe=""),
            )

            # Bot messages can reach every subscriber instead of just us
            _payload = (
                dict(payload, broadcast=True)
                if is_bot and self.broadcast
                else payload
            )

            self.logger.debug(
                "Zoho Cliq POST URL: %s (cert_verify=%r)",
                url,
                self.verify_certificate,
            )
            self.logger.debug("Zoho Cliq Payload: %s", _payload)

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    url,
                    params=params,
                    data=dumps(_payload),
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
                    status_str = NotifyCliq.http_response_code_lookup(
                        r.status_code, CLIQ_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send Zoho Cliq notification to %s: "
                        "%s%serror=%s.",
                        target,
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

                self.logger.info("Sent Zoho Cliq notification to %s.", target)

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Zoho Cliq "
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
        # The region and company decide which account the token belongs to
        return (
            self.secure_protocol[0],
            self.region,
            self.company,
            self.token,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "image": "yes" if self.include_image else "no",
            "broadcast": "yes" if self.broadcast else "no",
        }

        # Only emit what differs from the defaults
        if self.region != CliqRegion.US:
            params["region"] = self.region

        if self.company:
            params["company"] = self.company

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Our bot name is placed in front of the token
        botname = (
            "{}@".format(NotifyCliq.quote(self.botname, safe=""))
            if self.botname
            else ""
        )

        return "{schema}://{botname}{token}/{targets}?{params}".format(
            schema=self.secure_protocol[0],
            botname=botname,
            token=self.pprint(self.token, privacy, safe=""),
            targets="/".join(
                NotifyCliq.quote(x, safe="@")
                for x in (self.targets + self.invalid_targets)
            ),
            params=NotifyCliq.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The token is our host unless ?token= says otherwise
        results["token"] = NotifyCliq.unquote(
            results["qsd"]["token"]
            if results["qsd"].get("token")
            else results["host"]
        )

        # Our channels and bots are in the path
        results["targets"] = NotifyCliq.split_path(results["fullpath"])

        # Support ?to= for targets
        if results["qsd"].get("to"):
            results["targets"] += NotifyCliq.parse_list(results["qsd"]["to"])

        # The bot name sits in front of the token
        if results["user"]:
            results["botname"] = NotifyCliq.unquote(results["user"])

        # Support ?botname= as an override
        if results["qsd"].get("botname"):
            results["botname"] = NotifyCliq.unquote(results["qsd"]["botname"])

        if results["qsd"].get("region"):
            results["region"] = NotifyCliq.unquote(results["qsd"]["region"])

        if results["qsd"].get("company"):
            results["company"] = NotifyCliq.unquote(results["qsd"]["company"])

        # Include our image unless told not to
        results["include_image"] = parse_bool(
            results["qsd"].get("image", True)
        )

        results["broadcast"] = parse_bool(
            results["qsd"].get("broadcast", False)
        )

        return results

    @staticmethod
    def parse_native_url(url: str) -> Optional[dict[str, Any]]:
        """
        Support:
           https://cliq.zoho.com/api/v2/channelsbyname/{channel}/message
                 ?zapikey={token}
           https://cliq.zoho.eu/company/{id}/api/v2/bots/{bot}/message
                 ?zapikey={token}
        """
        result = re.match(
            r"^https?://(?P<domain>cliq\.zoho(cloud)?(\.[a-z]+){1,2})/+"
            r"(company/(?P<company>[A-Z0-9_-]+)/+)?api/v2/+"
            r"(?P<path>channelsbyname|bots)/(?P<name>[^/?]+)/+message/*"
            r"\?(?P<params>(.*&)?zapikey=(?P<token>[^&]+).*)$",
            url,
            re.I,
        )

        if not result:
            return None

        # Map the domain back to the region it serves
        region = CLIQ_DOMAIN_REGIONS.get(result.group("domain").lower())
        if not region:
            return None

        # Rebuild our target with the prefix that describes it
        target = "{}{}".format(
            "@" if result.group("path").lower() == "bots" else "#",
            result.group("name"),
        )

        return NotifyCliq.parse_url(
            "{schema}://{token}/{target}?region={region}{company}".format(
                schema=NotifyCliq.secure_protocol[0],
                token=result.group("token"),
                target=NotifyCliq.quote(target, safe="@"),
                region=region,
                company=(
                    "&company={}".format(result.group("company"))
                    if result.group("company")
                    else ""
                ),
            )
        )
