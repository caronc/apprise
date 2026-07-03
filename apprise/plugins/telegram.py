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
    build_backtick_run_index,
    commonmark_prepend_title,
    commonmark_scan_angle_dest,
    find_unescaped_run,
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

    # Default Notify Format
    notify_format = NotifyFormat.HTML

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

    # Convert HTML-derived CommonMark to Telegram Markdown in one pass while
    # preserving nested entities and independently valid message chunks.
    _TELEGRAM_STRICT_CHARS = "~#+=|{}.!<>-"

    # Legacy Markdown recognizes escapes only for these characters.
    _TELEGRAM_V1_ESCAPABLE = "`*_[]"

    # Full MarkdownV2 reserved set for previously unescaped fragments.
    _TELEGRAM_RESERVED_FULL = "_*[]()~`>#+=|{}.!<>-"

    @classmethod
    def _strict_escape(cls, text):
        """Escape an unescaped MarkdownV2 fragment without double-escaping."""

        out = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "\\" and i + 1 < n:
                out.append(text[i : i + 2])
                i += 2
                continue
            if ch in cls._TELEGRAM_RESERVED_FULL:
                out.append("\\" + ch)
            else:
                out.append(ch)
            i += 1
        return "".join(out)

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

        Both versions strip angle brackets from link destinations. Strict
        mode additionally escapes every MarkdownV2-reserved character.
        """

        # Accumulate output fragments; joined once at the end.
        out = []
        # Track emphasis spans; ``None`` marks nesting suppressed by v1.
        stack = []

        # Initialize the single-pass scanner.
        i = 0
        n = len(body)

        # Pre-compute backtick run positions once; reused for every "`" hit.
        backtick_runs = build_backtick_run_index(body)

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

            # Convert matched CommonMark code runs to Telegram delimiters.
            if ch == "`":
                j = i
                # Count consecutive backticks to get the run length.
                while j < n and body[j] == "`":
                    j += 1
                run = j - i
                # Find the next unescaped run of the same length.
                close = find_unescaped_run(backtick_runs, j, run)

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

            # Strip CommonMark angle brackets from Telegram link destinations.
            if body.startswith("](<", i):
                close = commonmark_scan_angle_dest(body, i, n)

                if close is not None:
                    # Extract the URL content between "(" and ">".
                    url = body[i + 3 : close]
                    # In Telegram's format, backslashes and closing
                    # parentheses inside the URL must be escaped.
                    url = url.replace("\\", "\\\\").replace(")", "\\)")
                    # Emit the Telegram-style destination and skip past ">)".
                    out.append("](" + url + ")")
                    i = close + 2
                    continue

            # Map CommonMark emphasis, including combined ``***`` runs.
            if ch == "*":
                j = i
                # Measure the full asterisk run.
                while j < n and body[j] == "*":
                    j += 1
                run = j - i

                # Detect runs that exactly close multiple nested spans.
                cascade_levels = 0
                cascade_width = 0
                for delim, _ in reversed(stack):
                    # Width contribution of this stack frame's close delimiter.
                    need = 2 if delim == "*" else 1
                    if cascade_width + need > run:
                        # Adding this frame would overshoot; no cascade match.
                        break
                    cascade_width += need
                    cascade_levels += 1
                    if cascade_width == run:
                        # Exact match found; cascade will close these frames.
                        break

                if cascade_levels and cascade_width == run:
                    # The run exactly closes cascade_levels stack frames.
                    # Pop them innermost-first and emit each close delimiter.
                    for _ in range(cascade_levels):
                        delim, open_index = stack.pop()
                        if open_index is None:
                            # V1 suppressed span: nesting was not emitted,
                            # so no close delimiter is needed here either.
                            pass
                        else:
                            # Emit the closing delimiter for this span.
                            out.append(delim)
                    # Advance past the entire asterisk run and move on.
                    i = j
                    continue

                # Otherwise consume the run one span at a time.
                while run > 0:
                    if stack and stack[-1][0] == "*" and run >= 2:
                        # Top of stack is a bold span; 2 asterisks close it.
                        delim, open_index = stack.pop()
                        if open_index is None:
                            # V1 suppressed bold: discard silently.
                            pass
                        elif open_index == len(out) - 1:
                            # Bold was opened but no content followed --
                            # remove the dangling open delimiter entirely.
                            out.pop()
                        else:
                            # Emit the bold close delimiter.
                            out.append(delim)
                        run -= 2
                    elif run >= 2:
                        # No closeable bold on stack; open a new bold span.
                        # Legacy v1 suppresses nested emphasis delimiters.
                        if strict or not stack:
                            out.append("*")
                            stack.append(("*", len(out) - 1))
                        else:
                            # Record suppression for the matching close.
                            stack.append(("*", None))
                        run -= 2
                    else:
                        # run == 1: open (or close, via cascade) an italic.
                        if strict or not stack:
                            out.append("_")
                            stack.append(("_", len(out) - 1))
                        else:
                            stack.append(("_", None))
                        run -= 1

                # Advance past the entire asterisk run.
                i = j
                continue

            # Escape remaining MarkdownV2-reserved characters.
            if strict and ch in cls._TELEGRAM_STRICT_CHARS:
                out.append("\\" + ch)
                i += 1
                continue

            # Preserve ordinary characters.
            out.append(ch)
            i += 1

        # Close nonempty spans left open by malformed or truncated input.
        while stack:
            delim, open_index = stack.pop()
            if open_index is None:
                # V1 suppressed span: never emitted an open, nothing to close.
                pass
            elif open_index == len(out) - 1:
                # Span opened but collected no content -- remove the orphan
                # opening delimiter so the output contains no empty spans.
                out.pop()
            else:
                # Emit the close delimiter to produce valid Telegram Markdown.
                out.append(delim)

        # Join the translated fragments once.
        return "".join(out)

    @classmethod
    def _repair_split_chunk(cls, text, strict, pending):
        """Repair one Telegram Markdown chunk and return its pending state.

        Each returned chunk is independently valid. ``pending`` carries only
        the state needed to interpret delimiters appearing in later chunks:

        Key             Meaning
        --------------  ----------------------------------------------
        ``in_code``     Width of a code fence continued from this chunk
        ``in_link_dest`` Link destination continues into the next chunk
        ``*`` / ``_``   Emphasis closes to discard in a later chunk

        Returns ``(repaired_text, next_pending)``.
        """

        # Output fragment list; joined once at the end.
        out = []
        # Track emphasis opened within this chunk.
        open_state = {"*": False, "_": False}
        # Record the out-index of each open delimiter for empty-span cleanup.
        open_pos = {"*": None, "_": None}
        # Work on a mutable copy so we do not mutate the caller's dict.
        pending = dict(pending)
        # Track possible link-label openings in this chunk.
        link_stack = []

        # Initialize the single-pass scanner.
        i = 0
        n = len(text)
        # Pre-compute backtick run positions once for O(log n) code matching.
        backtick_runs = build_backtick_run_index(text)

        # Resume an entity left open by the previous chunk.
        in_code_width = pending.pop("in_code", None)
        if in_code_width and strict:
            # Search this chunk for the carried code span's closing fence.
            close = find_unescaped_run(backtick_runs, 0, in_code_width)
            if close is not None:
                # Escape carried code content and consume its closing fence.
                out.append(cls._strict_escape(text[:close]))
                i = close + in_code_width
            else:
                # Escape this chunk and carry the code state forward.
                out.append(cls._strict_escape(text))
                pending["in_code"] = in_code_width
                i = n

        elif pending.pop("in_link_dest", False) and strict:
            # Search for a carried link destination's closing parenthesis.
            close = None
            k = 0
            while k < n:
                if text[k] == "\\" and k + 1 < n:
                    # Skip escape sequences -- they cannot be the terminator.
                    k += 2
                    continue
                if text[k] == ")":
                    # Found the unescaped closing parenthesis.
                    close = k
                    break
                k += 1

            if close is not None:
                # Strict-escape the URL fragment up to ")" then emit "\\)".
                out.append(cls._strict_escape(text[:close]))
                out.append("\\)")
                i = close + 1
            else:
                # Destination has not closed yet: carry the state forward.
                out.append(cls._strict_escape(text))
                pending["in_link_dest"] = True
                i = n

        # Scan the remainder of this chunk.
        while i < n:
            ch = text[i]

            # Preserve escapes already applied by the dialect adapter.
            if ch == "\\" and i + 1 < n:
                out.append(text[i : i + 2])
                i += 2
                continue

            # Preserve complete code spans or carry split spans forward.
            if ch == "`":
                j = i
                # Measure the opening backtick run.
                while j < n and text[j] == "`":
                    j += 1
                run = j - i
                # Look for the matching close run in the pre-built index.
                close = find_unescaped_run(backtick_runs, j, run)
                if close is not None:
                    # Complete span in this chunk: copy verbatim.
                    out.append(text[i : close + run])
                    i = close + run
                    continue

                if strict:
                    # Split code span: escape the partial content and carry
                    # the fence width so the next chunk knows where to close.
                    pending["in_code"] = run
                    out.append(cls._strict_escape(text[j:]))
                    i = n
                    continue

            # Reconcile carried or local emphasis delimiters.
            if ch in "*_":
                if pending.get(ch, 0) > 0:
                    # Discard the close for an opening dropped previously.
                    pending[ch] -= 1
                    i += 1
                    continue

                if open_state[ch]:
                    # Close the local span, dropping an empty opening.
                    if open_pos[ch] == len(out) - 1:
                        out.pop()
                    else:
                        # Emit the close delimiter.
                        out.append(ch)
                    open_state[ch] = False
                    open_pos[ch] = None
                else:
                    # This delimiter opens a new span in this chunk.
                    out.append(ch)
                    open_pos[ch] = len(out) - 1
                    open_state[ch] = True
                i += 1
                continue

            # Track link labels only in strict MarkdownV2 mode.
            if strict and ch == "[":
                # Record the position of this "[" in out so we can escape it
                # later if we never find a matching "](dest)" in this chunk.
                link_stack.append(len(out))
                out.append(ch)
                i += 1
                continue

            if strict and text.startswith("](", i):
                # We are at the "](" that closes a pending link label.
                # Scan forward for the unescaped closing ")" of the URL.
                close = None
                k = i + 2
                while k < n:
                    if text[k] == "\\" and k + 1 < n:
                        # Skip escaped chars inside the destination.
                        k += 2
                        continue
                    if text[k] == ")":
                        # Found the closing paren -- mark and stop.
                        close = k
                        break
                    k += 1

                if close is not None:
                    if link_stack:
                        # Matched a "[" from this chunk: emit the full
                        # "](...)" substring verbatim.
                        link_stack.pop()
                        out.append(text[i : close + 1])
                    else:
                        # No matching "[" in this chunk (it was in a previous
                        # chunk that ended mid-label).  Escape the brackets
                        # and strict-escape the destination so the output is
                        # valid MarkdownV2 literal text.
                        out.append("\\]\\(")
                        out.append(cls._strict_escape(text[i + 2 : close]))
                        out.append("\\)")
                    i = close + 1
                    continue

                # Escape the partial destination and carry it forward.
                out.append("\\]\\(")
                out.append(cls._strict_escape(text[i + 2 :]))
                pending["in_link_dest"] = True
                i = n
                continue

            if strict and ch in "[]()":
                # Stray link punctuation outside a complete construct must be
                # escaped so MarkdownV2's strict parser does not reject it.
                out.append("\\" + ch)
                i += 1
                continue

            # All other characters pass through unchanged.
            out.append(ch)
            i += 1

        # Escape unmatched labels before index-changing cleanup.
        if strict:
            for idx in link_stack:
                out[idx] = "\\" + out[idx]

        # Classify open spans before deletions shift their indexes.
        empty, nonempty = [], []
        for d in ("*", "_"):
            if not open_state[d]:
                continue
            (empty if open_pos[d] == len(out) - 1 else nonempty).append(d)

        # Delete empty spans from right to left to preserve earlier indexes.
        for d in sorted(empty, key=lambda d: open_pos[d], reverse=True):
            del out[open_pos[d]]

        # Close nonempty spans and carry their unmatched closes forward.
        new_pending = dict(pending)
        for d in nonempty:
            out.append(d)
            new_pending[d] = new_pending.get(d, 0) + 1

        # Return the repaired chunk and state for its successor.
        return "".join(out), new_pending

    def _build_send_calls(
        self, body=None, title=None, body_format=None, **kwargs
    ):
        """Convert HTML-derived CommonMark and repair each split chunk.

        Pending Telegram entity state is carried between generated calls.
        """

        if not (
            self.notify_format == NotifyFormat.MARKDOWN
            and body_format == NotifyFormat.HTML
        ):
            yield from super()._build_send_calls(
                body=body, title=title, body_format=body_format, **kwargs
            )
            return

        strict = self.markdown_ver == TelegramMarkdownVersion.TWO

        # Merge the title before translating its heading syntax.
        if self.title_maxlen <= 0 and title:
            body, title = commonmark_prepend_title(body, title)

        body = self._commonmark_to_telegram(body, strict=strict)

        pending = {}
        for kwargs2 in super()._build_send_calls(
            body=body,
            title=title,
            # Use Markdown-aware splitting on the translated body.
            body_format=NotifyFormat.MARKDOWN,
            **kwargs,
        ):
            kwargs2["body"], pending = self._repair_split_chunk(
                kwargs2["body"], strict, pending
            )
            yield kwargs2

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        body_format=None,
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
        if self.notify_format == NotifyFormat.MARKDOWN:
            if (
                body_format == NotifyFormat.TEXT
                and self.markdown_ver == TelegramMarkdownVersion.TWO
            ):
                # Escape MarkdownV2-only reserved characters in plain text.
                # See: https://stackoverflow.com/a/69892704/355584
                # Also: https://core.telegram.org/bots/api#markdownv2-style
                # HTML bodies were already escaped during dialect adaptation.
                body = re.sub(r"(?<!\\)([_*[\]()~`>#+=|{}.!-])", r"\\\1", body)

            # HTML was converted to Telegram Markdown before splitting so no
            # further transformation is required here; direct Telegram Markdown
            # input is left unchanged regardless of version.
            payload_["parse_mode"] = self.markdown_ver
            payload_["text"] = body

        else:  # HTML
            # Use Telegram's HTML mode
            payload_["parse_mode"] = "HTML"
            for r, v, m in self.__telegram_escape_html_entries:
                if "html" in m:
                    # Handle special cases where we need to alter new lines for
                    # presentation purposes
                    v = v.format(
                        m["html"]
                        if body_format
                        in (NotifyFormat.HTML, NotifyFormat.MARKDOWN)
                        else ""
                    )

                body = r.sub(v, body)

            # Prepare our payload based on HTML or TEXT
            payload_["text"] = body

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
            and body
            and len(payload_.get("text", "")) < self.telegram_caption_maxlen
            else {}
        )

        # Handle payloads without a body specified (but an attachment present)
        attach_content = (
            TelegramContentPlacement.AFTER
            if not body or caption_payload
            else self.content
        )

        # Create a copy of the chat_ids list
        targets = list(self.targets)
        while len(targets):
            target = targets.pop(0)
            chat_id, topic = target

            # Printable chat_id details
            pchat_id = f"{chat_id}" if not topic else f"{chat_id}:{topic}"

            payload = payload_.copy()
            payload["chat_id"] = chat_id
            if topic:
                payload["message_thread_id"] = topic

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

                if not body:
                    # Nothing more to do; move along to the next attachment
                    continue

            if caption_payload:
                # nothing further to do; move along to the next attachment
                continue

            # Always call throttle before any remote server i/o is made;
            # Telegram throttles to occur before sending the image so that
            # content can arrive together.
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
                        f"Failed to send Telegram notification to {pchat_id}: "
                        f"{error_msg if error_msg else status_str}, "
                        f"error={r.status_code}."
                    )

                    self.logger.debug(f"Response Details:\r\n{r.content}")

                    # Flag our error
                    has_error = True
                    continue

            except requests.RequestException as e:
                self.logger.warning(
                    f"A connection error occurred sending Telegram:{pchat_id} "
                    + "notification."
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # Flag our error
                has_error = True
                continue

            self.logger.info("Sent Telegram notification.")

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
