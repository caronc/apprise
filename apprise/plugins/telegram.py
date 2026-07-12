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

# To use this plugin, you need to first access https://api.telegram.org
# You need to create a bot and acquire it's Token Identifier (bot_token)
#
# Basically you need to create a chat with a user called the 'BotFather'
# and type: /newbot
#
# Then follow through the wizard, it will provide you an api key
# that looks like this:123456789:alphanumeri_characters
#
# For each chat_id a bot joins will have a chat_id associated with it.
# You will need this value as well to send the notification.
#
# Log into the webpage version of the site if you like by accessing:
#    https://web.telegram.org
#
# You can't check out to see if your entry is working using:
#    https://api.telegram.org/botAPI_KEY/getMe
#
#    Pay attention to the word 'bot' that must be present infront of your
#    api key that the BotFather gave you.
#
#  For example, a url might look like this:
#    https://api.telegram.org/bot123456789:alphanumeric_characters/getMe
#
# Development API Reference::
#  - https://core.telegram.org/bots/api
from json import dumps, loads
import os
import re

import requests

from ..attachment.base import AttachBase
from ..common import (
    NotifyFormat,
    NotifyImageSize,
    NotifyType,
    PersistentStoreMode,
)
from ..conversion import (
    commonmark_emphasis_run,
    commonmark_find_backtick_run,
    commonmark_index_backtick_runs,
    commonmark_match_emphasis,
    commonmark_new_scan_budget,
    commonmark_pick_emphasis_sentinel,
    commonmark_scan_angle_dest,
    commonmark_scan_autolink_dest,
)
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool, parse_list, validate_regex
from .base import NotifyBase

TELEGRAM_IMAGE_XY = NotifyImageSize.XY_256

# Chat ID is required
# If the Chat ID is positive, then it's addressed to a single person
# If the Chat ID is negative, then it's targeting a group
# We can support :topic (an integer) if specified as well
IS_CHAT_ID_RE = re.compile(
    r"^((?P<idno>-?[0-9]{1,32})|(@|%40)?(?P<name>[a-z_-][a-z0-9_-]+))"
    r"((:|%3A)(?P<topic>[0-9]+))?$",
    re.IGNORECASE,
)


class TelegramMarkdownVersion:
    """Telegram Markdown Version."""

    # Classic (Original Telegram Markdown)
    ONE = "MARKDOWN"

    # Supports strikethrough and many other items
    TWO = "MarkdownV2"


TELEGRAM_MARKDOWN_VERSION_MAP = {
    # v1
    "v1": TelegramMarkdownVersion.ONE,
    "1": TelegramMarkdownVersion.ONE,
    # v2
    "v2": TelegramMarkdownVersion.TWO,
    "2": TelegramMarkdownVersion.TWO,
    "default": TelegramMarkdownVersion.TWO,
}

TELEGRAM_MARKDOWN_VERSIONS = {
    # Note: This also acts as a reverse lookup mapping
    TelegramMarkdownVersion.ONE: "v1",
    TelegramMarkdownVersion.TWO: "v2",
}


class TelegramContentPlacement:
    """The Telegram Content Placement."""

    # Before Attachments
    BEFORE = "before"
    # After Attachments
    AFTER = "after"


# Identify Placement Categories
TELEGRAM_CONTENT_PLACEMENT = (
    TelegramContentPlacement.BEFORE,
    TelegramContentPlacement.AFTER,
)


class NotifyTelegram(NotifyBase):
    """A wrapper for Telegram Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Telegram"

    # The services URL
    service_url = "https://telegram.org/"

    # The default secure protocol
    secure_protocol = "tgram"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/telegram/"

    # Telegram supports HTML and Markdown. HTML remains the default.
    notify_format = (NotifyFormat.HTML, NotifyFormat.MARKDOWN)

    # Telegram uses the http protocol with JSON requests
    notify_url = "https://api.telegram.org/bot"

    # Support attachments
    attachment_support = True

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 4096

    # The maximum number of characters a telegram attachment caption can be
    # If an attachment is provided and the body is within the caption limit
    # then it is captioned with the attachment instead.
    telegram_caption_maxlen = 1024

    # Title is to be part of body
    title_maxlen = 0

    # Telegram is limited to sending a maximum of 100 requests per second.
    request_rate_per_sec = 0.001

    # Our default is to no not use persistent storage beyond in-memory
    # reference
    storage_mode = PersistentStoreMode.AUTO

    # Define object templates
    templates = (
        "{schema}://{bot_token}",
        "{schema}://{bot_token}/{targets}",
    )

    # Telegram Attachment Support
    mime_lookup = (
        # This list is intentionally ordered so that it can be scanned
        # from top to bottom.  The last entry is a catch-all
        # Animations are documented to only support gif or H.264/MPEG-4
        # Source: https://core.telegram.org/bots/api#sendanimation
        {
            "regex": re.compile(r"^(image/gif|video/H264)", re.I),
            "function_name": "sendAnimation",
            "key": "animation",
        },
        # This entry is intentially placed below the sendAnimiation allowing
        # it to catch gif files.  This then becomes a catch all to remaining
        # image types.
        # Source: https://core.telegram.org/bots/api#sendphoto
        {
            "regex": re.compile(r"^image/.*", re.I),
            "function_name": "sendPhoto",
            "key": "photo",
        },
        # Video is documented to only support .mp4
        # Source: https://core.telegram.org/bots/api#sendvideo
        {
            "regex": re.compile(r"^video/mp4", re.I),
            "function_name": "sendVideo",
            "key": "video",
        },
        # Voice supports ogg
        # Source: https://core.telegram.org/bots/api#sendvoice
        {
            "regex": re.compile(r"^(application|audio)/ogg", re.I),
            "function_name": "sendVoice",
            "key": "voice",
        },
        # Audio supports mp3 and m4a only
        # Source: https://core.telegram.org/bots/api#sendaudio
        {
            "regex": re.compile(r"^audio/(mpeg|mp4a-latm)", re.I),
            "function_name": "sendAudio",
            "key": "audio",
        },
        # Catch All (all other types)
        # Source: https://core.telegram.org/bots/api#senddocument
        {
            "regex": re.compile(r".*", re.I),
            "function_name": "sendDocument",
            "key": "document",
        },
    )

    # Telegram's HTML support doesn't like having HTML escaped
    # characters passed into it.  to handle this situation, we need to
    # search the body for these sequences and convert them to the
    # output the user expected
    __telegram_escape_html_entries = (
        # Comments
        (re.compile(r"\s*<!.+?-->\s*", (re.I | re.M | re.S)), "", {}),
        # the following tags are not supported
        (
            re.compile(
                r"\s*<\s*(!?DOCTYPE|p|div|span|body|script|link|"
                r"meta|html|font|head|label|form|input|textarea|select|iframe|"
                r"source|script)([^a-z0-9>][^>]*)?>\s*",
                (re.I | re.M | re.S),
            ),
            "",
            {},
        ),
        # All closing tags to be removed are put here
        (
            re.compile(
                r"\s*<\s*/(span|body|script|meta|html|font|head|"
                r"label|form|input|textarea|select|ol|ul|link|"
                r"iframe|source|script)([^a-z0-9>][^>]*)?>\s*",
                (re.I | re.M | re.S),
            ),
            "",
            {},
        ),
        # Bold
        (
            re.compile(
                r"<\s*(strong)([^a-z0-9>][^>]*)?>", (re.I | re.M | re.S)
            ),
            "<b>",
            {},
        ),
        (
            re.compile(
                r"<\s*/\s*(strong)([^a-z0-9>][^>]*)?>", (re.I | re.M | re.S)
            ),
            "</b>",
            {},
        ),
        (
            re.compile(
                r"\s*<\s*(h[1-6]|title)([^a-z0-9>][^>]*)?>\s*",
                (re.I | re.M | re.S),
            ),
            "{}<b>",
            {"html": "\r\n"},
        ),
        (
            re.compile(
                r"\s*<\s*/\s*(h[1-6]|title)([^a-z0-9>][^>]*)?>\s*",
                (re.I | re.M | re.S),
            ),
            "</b>{}",
            {"html": "<br/>"},
        ),
        # Italic
        (
            re.compile(
                r"<\s*(caption|em)([^a-z0-9>][^>]*)?>", (re.I | re.M | re.S)
            ),
            "<i>",
            {},
        ),
        (
            re.compile(
                r"<\s*/\s*(caption|em)([^a-z0-9>][^>]*)?>",
                (re.I | re.M | re.S),
            ),
            "</i>",
            {},
        ),
        # Bullet Lists
        (
            re.compile(r"<\s*li([^a-z0-9>][^>]*)?>\s*", (re.I | re.M | re.S)),
            " -",
            {},
        ),
        # New Lines
        (
            re.compile(
                r"\s*<\s*/?\s*(ol|ul|br|hr)\s*/?>\s*", (re.I | re.M | re.S)
            ),
            "\r\n",
            {},
        ),
        (
            re.compile(
                r"\s*<\s*/\s*(br|p|hr|li|div)([^a-z0-9>][^>]*)?>\s*",
                (re.I | re.M | re.S),
            ),
            "\r\n",
            {},
        ),
        # HTML Spaces (&nbsp;) and tabs (&emsp;) aren't supported
        # See https://core.telegram.org/bots/api#html-style
        (re.compile(r"\&nbsp;?", re.I), " ", {}),
        # Tabs become 3 spaces
        (re.compile(r"\&emsp;?", re.I), "   ", {}),
        # Some characters get re-escaped by the Telegram upstream
        # service so we need to convert these back,
        (re.compile(r"\&apos;?", re.I), "'", {}),
        (re.compile(r"\&quot;?", re.I), '"', {}),
        # New line cleanup
        (re.compile(r"\r*\n[\r\n]+", re.I), "\r\n", {}),
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "bot_token": {
                "name": _("Bot Token"),
                "type": "string",
                "private": True,
                "required": True,
                # Token required as part of the API request, allow the word
                # 'bot' infront of it
                "regex": (r"^(bot)?(?P<key>[0-9]+:[a-z0-9_-]+)$", "i"),
            },
            "target_user": {
                "name": _("Target Chat ID"),
                "type": "string",
                "map_to": "targets",
                "regex": (r"^((-?[0-9]{1,32})|([a-z_-][a-z0-9_-]+))$", "i"),
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
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
            "detect": {
                "name": _("Detect Bot Owner"),
                "type": "bool",
                "default": True,
                "map_to": "detect_owner",
            },
            "silent": {
                "name": _("Silent Notification"),
                "type": "bool",
                "default": False,
            },
            "preview": {
                "name": _("Web Page Preview"),
                "type": "bool",
                "default": False,
            },
            "topic": {
                "name": _("Topic Thread ID"),
                "type": "int",
            },
            "thread": {
                "alias_of": "topic",
            },
            "mdv": {
                "name": _("Markdown Version"),
                "type": "choice:string",
                "values": ("v1", "v2"),
                "default": "v1",
            },
            "to": {
                "alias_of": "targets",
            },
            "content": {
                "name": _("Content Placement"),
                "type": "choice:string",
                "values": TELEGRAM_CONTENT_PLACEMENT,
                "default": TelegramContentPlacement.BEFORE,
            },
        },
    )

    def __init__(
        self,
        bot_token,
        targets,
        detect_owner=True,
        include_image=False,
        silent=None,
        preview=None,
        topic=None,
        content=None,
        mdv=None,
        **kwargs,
    ):
        """Initialize Telegram Object."""
        super().__init__(**kwargs)

        self.bot_token = validate_regex(
            bot_token, *self.template_tokens["bot_token"]["regex"], fmt="{key}"
        )
        if not self.bot_token:
            err = f"The Telegram Bot Token specified ({bot_token}) is invalid."
            self.logger.warning(err)
            raise TypeError(err)

        # Get our Markdown Version
        self.markdown_ver = (
            TELEGRAM_MARKDOWN_VERSION_MAP[
                NotifyTelegram.template_args["mdv"]["default"]
            ]
            if mdv is None
            else next(
                (
                    v
                    for k, v in TELEGRAM_MARKDOWN_VERSION_MAP.items()
                    if str(mdv).lower().startswith(k)
                ),
                TELEGRAM_MARKDOWN_VERSION_MAP[
                    NotifyTelegram.template_args["mdv"]["default"]
                ],
            )
        )

        # Define whether or not we should make audible alarms
        self.silent = (
            self.template_args["silent"]["default"]
            if silent is None
            else bool(silent)
        )

        # Define whether or not we should display a web page preview
        self.preview = (
            self.template_args["preview"]["default"]
            if preview is None
            else bool(preview)
        )

        # Setup our content placement
        self.content = (
            self.template_args["content"]["default"]
            if not isinstance(content, str)
            else content.lower()
        )
        if self.content and self.content not in TELEGRAM_CONTENT_PLACEMENT:
            msg = f"The content placement specified ({content}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        if topic:
            try:
                self.topic = int(topic)

            except (TypeError, ValueError) as exc:
                # Not a valid integer; ignore entry
                err = f"The Telegram Topic ID specified ({topic}) is invalid."
                self.logger.warning(err)
                raise TypeError(err) from exc
        else:
            # No Topic Thread
            self.topic = None

        # if detect_owner is set to True, we will attempt to determine who
        # the bot owner is based on the first person who messaged it.  This
        # is not a fool proof way of doing things as over time Telegram removes
        # the message history for the bot.  So what appears (later on) to be
        # the first message to it, maybe another user who sent it a message
        # much later.  Users who set this flag should update their Apprise
        # URL later to directly include the user that we should message.
        self.detect_owner = detect_owner

        # Parse our list
        self.targets = []
        for target in parse_list(targets):
            results = IS_CHAT_ID_RE.match(target)
            if not results:
                self.logger.warning(
                    f"Dropped invalid Telegram chat/group ({target}) "
                    "specified.",
                )

                # Ensure we don't fall back to owner detection
                self.detect_owner = False
                continue

            if results.group("topic"):
                topic = int(
                    results.group("topic")
                    if results.group("topic")
                    else self.topic
                )
            else:
                # Default (if one set)
                topic = self.topic

            if results.group("name") is not None:
                # Name
                self.targets.append(
                    ("@{}".format(results.group("name")), topic)
                )

            else:  # ID
                self.targets.append((int(results.group("idno")), topic))

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

    def send_media(self, target, notify_type, payload=None, attach=None):
        """Sends a sticker based on the specified notify type."""

        # Prepare our Headers
        if payload is None:
            payload = {}
        headers = {
            "User-Agent": self.app_id,
        }

        # Our function name and payload are determined on the path
        function_name = "SendPhoto"
        key = "photo"
        path = None

        if isinstance(attach, AttachBase):
            if not attach:
                # We could not access the attachment
                self.logger.error(
                    f"Could not access attachment {attach.url(privacy=True)}."
                )
                return False

            self.logger.debug(
                f"Posting Telegram attachment {attach.url(privacy=True)}"
            )

            # Store our path to our file
            path = attach.path
            file_name = attach.name
            mimetype = attach.mimetype

            # Process our attachment
            function_name, key = next(
                (x["function_name"], x["key"])
                for x in self.mime_lookup
                if x["regex"].match(mimetype)
            )  # pragma: no cover

        else:
            attach = self.image_path(notify_type) if attach is None else attach
            if attach is None:
                # Nothing specified to send
                return True

            # Take on specified attachent as path
            path = attach
            file_name = os.path.basename(path)

        url = f"{self.notify_url}{self.bot_token}/{function_name}"

        # Always call throttle before any remote server i/o is made;
        # Telegram throttles to occur before sending the image so that
        # content can arrive together.
        self.throttle()

        # Extract our target
        chat_id, topic = target

        payload["chat_id"] = chat_id
        if topic:
            payload["message_thread_id"] = topic

        try:
            with (
                attach if isinstance(attach, AttachBase) else open(path, "rb")
            ) as f:
                # Configure file payload (for upload)
                files = {key: (file_name, f)}

                self.logger.debug(
                    f"Telegram attachment POST URL: {url} "
                    f"(cert_verify={self.verify_certificate!r})"
                )

                r = requests.post(
                    url,
                    headers=headers,
                    files=files,
                    data=payload,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = NotifyTelegram.http_response_code_lookup(
                        r.status_code
                    )

                    self.logger.warning(
                        "Failed to send Telegram attachment: "
                        "{}{}error={}.".format(
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    return False

                # Content was sent successfully if we got here
                return True

        except requests.RequestException as e:
            self.logger.warning(
                "A connection error occurred posting Telegram attachment."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

        except OSError:
            # IOError is present for backwards compatibility with Python
            # versions older then 3.3.  >= 3.3 throw OSError now.

            # Could not open and/or read the file; this is not a problem since
            # we scan a lot of default paths.
            self.logger.error(f"File can not be opened for read: {path}")

        return False

    def detect_bot_owner(self):
        """Takes a bot and attempts to detect it's chat id from that."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        url = "{}{}/{}".format(self.notify_url, self.bot_token, "getUpdates")

        self.logger.debug(
            f"Telegram User Detection POST URL: {url} "
            f"(cert_verify={self.verify_certificate!r})"
        )

        # Track our response object
        response = None

        try:
            r = requests.post(
                url,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyTelegram.http_response_code_lookup(
                    r.status_code
                )

                try:
                    # Try to get the error message if we can:
                    error_msg = loads(r.content).get("description", "unknown")

                except (AttributeError, TypeError, ValueError):
                    # ValueError = r.content is Unparsable
                    # TypeError = r.content is None
                    # AttributeError = r is None
                    error_msg = None
                    self.logger.debug(
                        "Failed to parse Telegram JSON response; body: %r",
                        (r.content or b"")[:2000],
                    )

                if error_msg:
                    self.logger.warning(
                        "Failed to detect the Telegram user: "
                        f"({r.status_code}) {error_msg}."
                    )

                else:
                    self.logger.warning(
                        "Failed to detect the Telegram user: "
                        "{}{}error={}.".format(
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                return 0

            # Load our response and attempt to fetch our userid
            response = loads(r.content)

        except (AttributeError, TypeError, ValueError):
            # Our response was not the JSON type we had expected it to be
            # - ValueError = r.content is Unparsable
            # - TypeError = r.content is None
            # - AttributeError = r is None
            self.logger.warning(
                "A communication error occurred detecting the Telegram User."
            )
            return 0

        except requests.RequestException as e:
            self.logger.warning(
                "A connection error occurred detecting the Telegram User."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return 0

        # A Response might look something like this:
        # {
        #    "ok":true,
        #    "result":[{
        #      "update_id":645421321,
        #      "message":{
        #        "message_id":1,
        #        "from":{
        #          "id":532389719,
        #          "is_bot":false,
        #          "first_name":"Chris",
        #          "language_code":"en-US"
        #        },
        #      "chat":{
        #        "id":532389719,
        #        "first_name":"Chris",
        #        "type":"private"
        #      },
        #      "date":1519694394,
        #      "text":"/start",
        #      "entities":[{"offset":0,"length":6,"type":"bot_command"}]}}]

        if response.get("ok", False):
            for entry in response.get("result", []):
                if "message" in entry and "from" in entry["message"]:
                    id_ = entry["message"]["from"].get("id", 0)
                    user = entry["message"]["from"].get("first_name")
                    self.logger.info(
                        "Detected Telegram user %s (userid=%d)", user, id_
                    )
                    # Return our detected userid
                    self.store.set("bot_owner", id_)
                    return id_

        self.logger.warning(
            "Failed to detect a Telegram user; "
            "try sending your bot a message first."
        )
        return 0

    # Convert CommonMark into independently valid Telegram Markdown chunks.
    _TELEGRAM_STRICT_CHARS = "~#+=|{}.!<>-"

    # Legacy Markdown recognizes escapes only for these characters.
    _TELEGRAM_V1_ESCAPABLE = "`*_[]"

    def dialect_convert(self, body, body_format=None, *args, **kwargs):
        """Translate CommonMark to the configured Telegram Markdown."""
        if body_format != NotifyFormat.MARKDOWN:
            # Telegram's other declared format (HTML) needs no dialect
            # completion of its own -- only Markdown does.
            return body
        strict = self.markdown_ver == TelegramMarkdownVersion.TWO
        return self._commonmark_to_telegram(body, strict=strict)

    @classmethod
    def _commonmark_to_telegram(cls, body, strict=False):
        """Translate CommonMark to Telegram Markdown v1 or v2.

        CommonMark     Markdown v1     MarkdownV2
        -------------  --------------  --------------------
        **bold**       *bold*          *bold*
        *italic*       _italic_        _italic_
        `code`         `code`          `code`
        [l](<u>)       [l](u)          [l](u)
        \\*            known escapes   all reserved escapes

        Both versions normalize links. MarkdownV2 also applies its stricter
        reserved-character escaping pass.
        """

        # Accumulate output fragments; joined once at the end.
        out = []
        # Record ``*`` and ``_`` markup, then match it after the full scan.
        delimiters = []
        # Track possible link-label openings in LIFO order.
        link_stack = []

        # Initialize the single-pass scanner.
        i = 0
        n = len(body)

        # Pre-compute backtick run positions once; reused for every "`" hit.
        backtick_runs = commonmark_index_backtick_runs(body)
        # Pick a temporary marker that does not occur in the message.
        sentinel = commonmark_pick_emphasis_sentinel(body)
        # Share one budget across link scans to preserve long valid links while
        # bounding the total work spent on malformed destinations.
        scan_budget = commonmark_new_scan_budget(body)

        while i < n:
            ch = body[i]

            # Preserve escapes required by v2 or recognized by legacy v1.
            if ch == "\\" and i + 1 < n:
                nxt = body[i + 1]
                if strict or nxt in cls._TELEGRAM_V1_ESCAPABLE:
                    # Preserve the entire two-character escape sequence.
                    out.append(body[i : i + 2])
                else:
                    # V1 does not escape this char; emit just the literal.
                    out.append(nxt)
                i += 2
                continue

            # Convert matched CommonMark code spans to Telegram backticks.
            if ch == "`":
                j = i
                # Count consecutive backticks to get the run length.
                while j < n and body[j] == "`":
                    j += 1
                run = j - i
                # Find the next unescaped run of the same length.
                close = commonmark_find_backtick_run(backtick_runs, j, run)

                if close is not None:
                    # Extract the code span content between the delimiters.
                    content = body[j:close]
                    # Escape Telegram control characters inside code.
                    content = content.replace("\\", "\\\\").replace("`", "\\`")

                    # Use fences for multiline or wide CommonMark spans.
                    delim = "```" if run >= 3 or "\n" in content else "`"
                    out.append(delim + content + delim)
                    # Skip past the closing backtick run.
                    i = close + run
                    continue

                # Preserve unmatched backticks, escaping them only in v2.
                out.append(("\\`" if strict else "`") * run)
                i = j
                continue

            # Record a possible CommonMark link-label opening.
            if ch == "[":
                link_stack.append(len(out))
                out.append(ch)
                i += 1
                continue

            # Normalize angle-bracket destinations produced by conversion.
            # Scan only when a pending label can use the destination.
            if body.startswith("](<", i) and link_stack:
                # Charge this attempt against the shared destination budget.
                close = commonmark_scan_angle_dest(
                    body, i, n, budget=scan_budget
                )

                if close is not None:
                    # Extract the URL content between "(" and ">".
                    url = body[i + 3 : close]
                    # Escape Telegram URL delimiters.
                    url = url.replace("\\", "\\\\").replace(")", "\\)")
                    # A matching "[" from earlier confirms a real link.
                    link_stack.pop()
                    # Emit the Telegram-style destination and skip past ">)".
                    out.append("](" + url + ")")
                    i = close + 2
                    continue

                # Retire the unmatched label so later text cannot reuse it.
                link_stack.pop()

            # Preserve a complete plain Markdown link using Telegram escaping.
            # Bare destinations also require a pending label.
            if body.startswith("](", i) and link_stack and scan_budget[0] > 0:
                close = None
                # Track balanced parentheses until the link terminator.
                depth = 0
                start = i + 2
                k = start
                while k < n:
                    if body[k] == "\\" and k + 1 < n:
                        # Skip escape sequences -- not the terminator.
                        k += 2
                        continue
                    if body[k] == "(":
                        depth += 1
                    elif body[k] == ")":
                        if depth == 0:
                            close = k
                            break
                        depth -= 1
                    k += 1

                # Charge the scanned distance against the shared budget.
                scan_budget[0] -= (close if close is not None else k) - start

                if close is not None:
                    link_stack.pop()
                    # Escape balanced parentheses and other reserved content.
                    dest = []
                    k = i + 2
                    while k < close:
                        if body[k] == "\\" and k + 1 < close:
                            dest.append(body[k : k + 2])
                            k += 2
                            continue
                        if body[k] in "()" or (
                            strict and body[k] in cls._TELEGRAM_STRICT_CHARS
                        ):
                            dest.append("\\" + body[k])
                        else:
                            dest.append(body[k])
                        k += 1
                    out.append("](" + "".join(dest) + ")")
                    i = close + 1
                    continue

                # Same reasoning as the angle-dest case above.
                link_stack.pop()

            # Drop autolink brackets and escape its URL for the selected mode.
            if ch == "<":
                close, _ = commonmark_scan_autolink_dest(body, i, n)
                if close is not None:
                    for c2 in body[i + 1 : close]:
                        if strict and c2 in cls._TELEGRAM_STRICT_CHARS:
                            out.append("\\" + c2)
                        else:
                            out.append(c2)
                    i = close + 1
                    continue

            # Escape non-link punctuation required by strict MarkdownV2.
            if strict and ch in "]()":
                if ch == "]" and link_stack:
                    # Escape the orphaned "[" so it cannot match a later link.
                    idx = link_stack.pop()
                    out[idx] = "\\" + out[idx]
                out.append("\\" + ch)
                i += 1
                continue

            # Record asterisk and underscore runs for later resolution.
            if ch in "*_":
                i = commonmark_emphasis_run(
                    body, i, n, delimiters, out, sentinel
                )
                continue

            # Escape remaining MarkdownV2-reserved characters.
            if strict and ch in cls._TELEGRAM_STRICT_CHARS:
                out.append("\\" + ch)
                i += 1
                continue

            # Preserve ordinary characters.
            out.append(ch)
            i += 1

        # Escape dangling "[" markers before span cleanup changes indexes.
        if strict:
            for idx in link_stack:
                out[idx] = "\\" + out[idx]

        # Resolve all recorded runs using CommonMark matching rules.
        commonmark_match_emphasis(delimiters)

        # MarkdownV2 keeps nesting; legacy v1 suppresses nested markers while
        # retaining their text. Source-order depth identifies visible spans.
        depth = 0
        for descriptor in delimiters:
            closes = [e for e in descriptor["events"] if e[0] == "close"]
            # Decide open visibility from outermost to innermost.
            opens = [e for e in descriptor["events"] if e[0] == "open"]
            tagged = []
            for kind, is_strong in closes:
                tagged.append((kind, is_strong, strict or depth == 1))
                depth -= 1
            for kind, is_strong in reversed(opens):
                tagged.append((kind, is_strong, strict or depth == 0))
                depth += 1
            descriptor["events"] = tagged

        def _substitute(match):
            descriptor = delimiters[int(match.group(1))]
            char = descriptor["char"]
            close_part = "".join(
                "*" if is_strong else "_"
                for kind, is_strong, visible in descriptor["events"]
                if kind == "close" and visible
            )
            open_part = "".join(
                "*" if is_strong else "_"
                for kind, is_strong, visible in descriptor["events"]
                if kind == "open" and visible
            )
            # Escape unmatched literal markers only in MarkdownV2.
            marker = ("\\" + char) if strict else char
            leftover = marker * descriptor["numdelims"]
            return close_part + leftover + open_part

        marker_re = re.compile(
            re.escape(sentinel) + r"(\d+)" + re.escape(sentinel)
        )
        text = marker_re.sub(_substitute, "".join(out))

        return text

    def _attachment_send_index(self, total: int) -> int:
        """Place the attachment on the last call for content=before.

        This lets split text arrive before an attachment that should visually
        precede its caption; other placements use the first call.
        """
        return (
            total - 1 if self.content == TelegramContentPlacement.BEFORE else 0
        )

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        body_format=None,
        body_passthrough=None,
        **kwargs,
    ):
        """Perform Telegram Notification."""

        if len(self.targets) == 0 and self.detect_owner:
            id_ = self.store.get("bot_owner") or self.detect_bot_owner()
            if id_:
                # Permanently store our id in our target list for next time
                self.targets.append((str(id_), self.topic))
                self.logger.info(
                    "Update your Telegram Apprise URL to read: "
                    f"{self.url(privacy=True)}"
                )

        if len(self.targets) == 0:
            self.logger.warning("There were not Telegram chat_ids to notify.")
            return False

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # error tracking (used for function return)
        has_error = False

        url = "{}{}/{}".format(self.notify_url, self.bot_token, "sendMessage")

        payload_ = {
            # Notification Audible Control
            "disable_notification": self.silent,
            # Display Web Page Preview (if possible)
            "disable_web_page_preview": not self.preview,
        }

        # Prepare Message Body
        if body_format == NotifyFormat.MARKDOWN:
            # The framework already converted and resized this Markdown body.
            bodies = [body]
            payload_["parse_mode"] = self.markdown_ver

        else:  # HTML
            # Use Telegram's HTML mode
            payload_["parse_mode"] = "HTML"
            for r, v, m in self.__telegram_escape_html_entries:
                if "html" in m:
                    # Add heading padding only for declared HTML sources.
                    v = v.format(m["html"] if not body_passthrough else "")

                body = r.sub(v, body)

            # Prepare our payload based on HTML or TEXT
            bodies = [body]

        # Use the first piece for caption and attachment placement.
        payload_["text"] = bodies[0]
        has_body = bool(bodies[0])

        # Prepare our caption payload
        caption_payload = (
            {
                "caption": payload_["text"],
                "show_caption_above_media": (
                    self.content == TelegramContentPlacement.BEFORE
                ),
                "parse_mode": payload_["parse_mode"],
            }
            if attach
            and has_body
            and len(payload_.get("text", "")) < self.telegram_caption_maxlen
            else {}
        )

        # Handle payloads without a body specified (but an attachment present)
        attach_content = (
            TelegramContentPlacement.AFTER
            if not has_body or caption_payload
            else self.content
        )

        # Create a copy of the chat_ids list
        targets = list(self.targets)
        while len(targets):
            target = targets.pop(0)
            chat_id, topic = target

            # Printable chat_id details
            pchat_id = f"{chat_id}" if not topic else f"{chat_id}:{topic}"

            base_payload = payload_.copy()
            base_payload["chat_id"] = chat_id
            if topic:
                base_payload["message_thread_id"] = topic

            if self.include_image is True and not self.send_media(
                target, notify_type
            ):
                # We failed to send the image associated with our
                # notify_type
                self.logger.warning(
                    "Failed to send Telegram attachment to {}.", pchat_id
                )

            if (
                attach
                and self.attachment_support
                and attach_content == TelegramContentPlacement.AFTER
            ):
                # Send our attachments now (if specified and if it exists)
                if not self._send_attachments(
                    target,
                    notify_type=notify_type,
                    payload=caption_payload,
                    attach=attach,
                ):
                    has_error = True
                    continue

                if not has_body:
                    # Nothing more to do; move along to the next attachment
                    continue

            if caption_payload:
                # nothing further to do; move along to the next attachment
                continue

            # Send every expanded piece so overflow splitting loses no content.
            target_failed = False
            for piece in bodies:
                payload = base_payload.copy()
                payload["text"] = piece

                # Always call throttle before any remote server i/o is
                # made; Telegram throttles to occur before sending the
                # image so that content can arrive together.
                self.throttle()

                self.logger.debug(
                    f"Telegram POST URL: {url} "
                    f"(cert_verify={self.verify_certificate!r})"
                )
                self.logger.debug(f"Telegram Payload: {payload!s}")

                try:
                    r = requests.post(
                        url,
                        data=dumps(payload),
                        headers=headers,
                        verify=self.verify_certificate,
                        timeout=self.request_timeout,
                        allow_redirects=self.redirects,
                    )

                    if r.status_code != requests.codes.ok:
                        # We had a problem
                        status_str = NotifyTelegram.http_response_code_lookup(
                            r.status_code
                        )

                        try:
                            # Try to get the error message if we can:
                            error_msg = loads(r.content).get(
                                "description", "unknown"
                            )

                        except (AttributeError, TypeError, ValueError):
                            # ValueError = r.content is Unparsable
                            # TypeError = r.content is None
                            # AttributeError = r is None
                            error_msg = None

                        self.logger.warning(
                            "Failed to send Telegram notification to "
                            f"{pchat_id}: "
                            f"{error_msg if error_msg else status_str}, "
                            f"error={r.status_code}."
                        )

                        self.logger.debug(f"Response Details:\r\n{r.content}")

                        # Flag our error
                        has_error = True
                        target_failed = True
                        continue

                except requests.RequestException as e:
                    self.logger.warning(
                        "A connection error occurred sending "
                        f"Telegram:{pchat_id} notification."
                    )
                    self.logger.debug(f"Socket Exception: {e!s}")

                    # Flag our error
                    has_error = True
                    target_failed = True
                    continue

                self.logger.info("Sent Telegram notification.")

            if target_failed:
                continue

            if (
                attach
                and self.attachment_support
                and attach_content == TelegramContentPlacement.BEFORE
                and not self._send_attachments(
                    target=target, notify_type=notify_type, attach=attach
                )
            ):
                # Send our attachments now (if specified and if it exists) as
                # it was identified to send the content before the attachments
                # which is now done.

                has_error = True
                continue

        return not has_error

    def _send_attachments(self, target, notify_type, attach, payload=None):
        """Sends our attachments."""
        if payload is None:
            payload = {}
        has_error = False
        # Send our attachments now (if specified and if it exists)
        for no, attachment in enumerate(attach, start=1):
            payload = payload if payload and no == 1 else {}
            payload.update(
                {
                    "title": (
                        attachment.name
                        if attachment.name
                        else f"file{no:03}.dat"
                    )
                }
            )

            if not self.send_media(
                target, notify_type, payload=payload, attach=attachment
            ):
                # We failed; don't continue
                has_error = True
                break

            self.logger.info(f"Sent Telegram attachment: {attachment}.")

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.bot_token)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "image": self.include_image,
            "detect": "yes" if self.detect_owner else "no",
            "silent": "yes" if self.silent else "no",
            "preview": "yes" if self.preview else "no",
            "content": self.content,
            "mdv": TELEGRAM_MARKDOWN_VERSIONS[self.markdown_ver],
        }

        if self.topic:
            params["topic"] = self.topic

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        targets = []
        for chat_id, topic_ in self.targets:
            topic = topic_ if topic_ else self.topic

            targets.append(
                "".join(
                    [
                        (
                            NotifyTelegram.quote(f"{chat_id}", safe="@")
                            if isinstance(chat_id, str)
                            else f"{chat_id}"
                        ),
                        "" if not topic else f":{topic}",
                    ]
                )
            )

        # No need to check the user token because the user automatically gets
        # appended into the list of chat ids
        return "{schema}://{bot_token}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            bot_token=self.pprint(self.bot_token, privacy, safe=""),
            targets="/".join(targets),
            params=NotifyTelegram.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return 1 if not self.targets else len(self.targets)

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        # This is a dirty hack; but it's the only work around to tgram://
        # messages since the bot_token has a colon in it. It invalidates a
        # normal URL.

        # This hack searches for this bogus URL and corrects it so we can
        # properly load it further down. The other alternative is to ask users
        # to actually change the colon into a slash (which will work too), but
        # it's more likely to cause confusion... So this is the next best thing
        # we also check for %3A (incase the URL is encoded) as %3A == :
        try:
            tgram = re.match(
                rf"(?P<protocol>{NotifyTelegram.secure_protocol}://)"
                r"(bot)?(?P<prefix>([a-z0-9_-]+)"
                r"(:[a-z0-9_-]+)?@)?(?P<btoken_a>[0-9]+)(:|%3A)+"
                r"(?P<remaining>.*)$",
                url,
                re.I,
            )

        except (TypeError, AttributeError):
            # url is bad; force tgram to be None
            tgram = None

        if not tgram:
            # Content is simply not parseable
            return None

        if tgram.group("prefix"):
            # Try again
            results = NotifyBase.parse_url(
                "{}{}{}/{}".format(
                    tgram.group("protocol"),
                    tgram.group("prefix"),
                    tgram.group("btoken_a"),
                    tgram.group("remaining"),
                ),
                verify_host=False,
            )

        else:
            # Try again
            results = NotifyBase.parse_url(
                "{}{}/{}".format(
                    tgram.group("protocol"),
                    tgram.group("btoken_a"),
                    tgram.group("remaining"),
                ),
                verify_host=False,
            )

        # The first token is stored in the hostname
        bot_token_a = NotifyTelegram.unquote(results["host"])

        # Get a nice unquoted list of path entries
        entries = NotifyTelegram.split_path(results["fullpath"])

        # Now fetch the remaining tokens
        bot_token_b = entries.pop(0)

        bot_token = f"{bot_token_a}:{bot_token_b}"

        # Store our chat ids (as these are the remaining entries)
        results["targets"] = entries

        # content to be displayed 'before' or 'after' attachments
        if "content" in results["qsd"] and len(results["qsd"]["content"]):
            results["content"] = results["qsd"]["content"]

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyTelegram.parse_list(
                results["qsd"]["to"]
            )

        # Store our bot token
        results["bot_token"] = bot_token

        # Support Markdown Version
        if "mdv" in results["qsd"] and len(results["qsd"]["mdv"]):
            results["mdv"] = results["qsd"]["mdv"]

        # Support Thread Topic
        if "topic" in results["qsd"] and len(results["qsd"]["topic"]):
            results["topic"] = results["qsd"]["topic"]

        elif "thread" in results["qsd"] and len(results["qsd"]["thread"]):
            results["topic"] = results["qsd"]["thread"]

        # Silent (Sends the message Silently); users will receive
        # notification with no sound.
        results["silent"] = parse_bool(results["qsd"].get("silent", False))

        # Show Web Page Preview
        results["preview"] = parse_bool(results["qsd"].get("preview", False))

        # Include images with our message
        results["include_image"] = parse_bool(
            results["qsd"].get("image", False)
        )

        # Include images with our message
        results["detect_owner"] = parse_bool(
            results["qsd"].get("detect", not results["targets"])
        )

        return results
