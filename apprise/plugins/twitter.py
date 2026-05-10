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

# Migration guide from X API v1.1 to v2:
#   https://docs.x.com/x-api/migrate/overview
#
# X API v2 Tweet endpoint:
#   https://docs.x.com/x-api/posts/creation/quickstart/post-a-tweet
#
# X API v2 Direct Message endpoint:
#   https://docs.x.com/x-api/direct-messages/manage-direct-messages/
#       api-reference/post-dm_conversations-dm_conversation_id-messages
#
# X API v2 User Lookup endpoint:
#   https://docs.x.com/x-api/users/user-lookup/api-reference/get-users-by
#
# X API v2 Current User endpoint:
#   https://docs.x.com/x-api/users/user-lookup/api-reference/get-users-me
#
# X API v2 Media upload (available on all access tiers, including Free):
#   https://docs.x.com/x-api/media/upload-media
#
# Free-tier accounts can ONLY post tweets (mode=tweet).
# Sending Direct Messages (mode=dm, the default) requires a paid X API
# subscription (Basic or higher).
import contextlib
from copy import deepcopy
from datetime import datetime, timezone
from json import dumps, loads
import re

import requests
from requests_oauthlib import OAuth1

from ..attachment.base import AttachBase
from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_bool, parse_list, validate_regex
from .base import NotifyBase

IS_USER = re.compile(r"^\s*@?(?P<user>[A-Z0-9_]+)$", re.I)


class TwitterMessageMode:
    """Twitter Message Mode."""

    # DM (a Direct Message) -- requires Basic+ X API subscription
    DM = "dm"

    # A Public Tweet -- available on Free X API tier and above
    TWEET = "tweet"


# Define the types in a list for validation purposes
TWITTER_MESSAGE_MODES = (
    TwitterMessageMode.DM,
    TwitterMessageMode.TWEET,
)


class NotifyTwitter(NotifyBase):
    """A wrapper to Twitter Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Twitter"

    # The services URL
    service_url = "https://twitter.com/"

    # The default secure protocol is twitter.
    secure_protocol = ("x", "twitter", "tweet")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/twitter/"

    # Support attachments
    attachment_support = True

    # Do not set body_maxlen as it is set in a property value below
    # since the length varies depending if we are doing a direct message
    # or a tweet
    # body_maxlen = see below @propery defined

    # Twitter does have titles when creating a message
    title_maxlen = 0

    # X API v2 Endpoints:

    # X API v2 -- Post a Tweet
    # Available on Free tier and above
    twitter_tweet = "https://api.twitter.com/2/tweets"

    # X API v2 -- Current authenticated user info
    twitter_whoami = "https://api.twitter.com/2/users/me"

    # X API v2 -- Batch user lookup by username (?usernames=u1,u2,...)
    twitter_lookup = "https://api.twitter.com/2/users/by"

    # X API v2 -- Direct Message to a participant (format with user_id)
    # Requires Basic+ X API subscription
    twitter_dm = "https://api.twitter.com/2/dm_conversations/with/{}/messages"

    # X API v2 Media Upload (available on all access tiers, including Free)
    # media_category is required: "tweet_image" or "dm_image"

    # Twitter Media (Attachment) Upload Location
    twitter_media = "https://api.x.com/2/media/upload"

    # it is documented on the site that the maximum images per tweet
    # is 4 (unless it's a GIF, then it's only 1)
    __tweet_non_gif_images_batch = 4

    # Twitter is kind enough to return how many more requests we're allowed to
    # continue to make within it's header response as:
    # X-Rate-Limit-Reset: The epoc time (in seconds) we can expect our
    #                    rate-limit to be reset.
    # X-Rate-Limit-Remaining: an integer identifying how many requests we're
    #                        still allow to make.
    request_rate_per_sec = 0

    # For Tracking Purposes
    ratelimit_reset = datetime.now(timezone.utc).replace(tzinfo=None)

    # Default to 1000; users can send up to 1000 DM's and 2400 tweets a day
    # This value only get's adjusted if the server sets it that way
    ratelimit_remaining = 1

    templates = (
        "{schema}://{ckey}/{csecret}/{akey}/{asecret}",
        "{schema}://{ckey}/{csecret}/{akey}/{asecret}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "ckey": {
                "name": _("Consumer Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "csecret": {
                "name": _("Consumer Secret"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "akey": {
                "name": _("Access Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "asecret": {
                "name": _("Access Secret"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "target_user": {
                "name": _("Target User"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
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
            "mode": {
                "name": _("Message Mode"),
                "type": "choice:string",
                "values": TWITTER_MESSAGE_MODES,
                "default": TwitterMessageMode.DM,
            },
            "cache": {
                "name": _("Cache Results"),
                "type": "bool",
                "default": True,
            },
            "to": {
                "alias_of": "targets",
            },
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": True,
            },
        },
    )

    def __init__(
        self,
        ckey,
        csecret,
        akey,
        asecret,
        targets=None,
        mode=None,
        cache=True,
        batch=True,
        **kwargs,
    ):
        """Initialize Twitter Object."""
        super().__init__(**kwargs)

        self.ckey = validate_regex(ckey)
        if not self.ckey:
            msg = "An invalid Twitter Consumer Key was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.csecret = validate_regex(csecret)
        if not self.csecret:
            msg = "An invalid Twitter Consumer Secret was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.akey = validate_regex(akey)
        if not self.akey:
            msg = "An invalid Twitter Access Key was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.asecret = validate_regex(asecret)
        if not self.asecret:
            msg = "An invalid Access Secret was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our webhook mode
        self.mode = (
            self.template_args["mode"]["default"]
            if not isinstance(mode, str)
            else mode.lower()
        )

        if mode and isinstance(mode, str):
            self.mode = next(
                (a for a in TWITTER_MESSAGE_MODES if a.startswith(mode)), None
            )
            if self.mode not in TWITTER_MESSAGE_MODES:
                msg = (
                    f"The Twitter message mode specified ({mode}) is invalid."
                )
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.mode = self.template_args["mode"]["default"]

        # Set Cache Flag
        self.cache = cache

        # Prepare Image Batch Mode Flag
        self.batch = batch

        # Track any errors
        has_error = False

        # Identify our targets
        self.targets = []
        for target in parse_list(targets):
            match = IS_USER.match(target)
            if match and match.group("user"):
                self.targets.append(match.group("user"))
                continue

            has_error = True
            self.logger.warning(
                f"Dropped invalid Twitter user ({target}) specified.",
            )

        if has_error and not self.targets:
            # We have specified that we want to notify one or more individual
            # and we failed to load any of them.  Since it's also valid to
            # notify no one at all (which means we notify ourselves), it's
            # important we don't switch from the users original intentions
            self.targets = None

        # Initialize our cache values
        self._whoami_cache = None
        self._user_cache = {}

        return

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Twitter Notification."""

        if self.targets is None:
            self.logger.warning("No valid Twitter targets to notify.")
            return False

        # Build a list of our attachments
        attachments = []

        if attach and self.attachment_support:
            # We need to upload our payload first so that we can source it
            # in remaining messages
            for no, attachment in enumerate(attach, start=1):
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access attachment "
                        f"'{attachment.url(privacy=True)}."
                    )
                    return False

                if not re.match(r"^image/.*", attachment.mimetype, re.I):
                    # Only support images at this time
                    self.logger.warning(
                        "Ignoring unsupported Twitter attachment "
                        f"{attachment.url(privacy=True)}."
                    )
                    continue

                self.logger.debug(
                    "Preparing Twitter attachment "
                    f"{attachment.url(privacy=True)}"
                )

                # v2 media upload requires media_category:
                # "tweet_image" for public tweets, "dm_image" for DMs
                media_category = (
                    "tweet_image"
                    if self.mode == TwitterMessageMode.TWEET
                    else "dm_image"
                )

                # Upload our image and get our id associated with it
                # see: https://docs.x.com/x-api/media/upload-media
                postokay, response = self._fetch(
                    self.twitter_media,
                    payload=attachment,
                    extra={"media_category": media_category},
                )

                if not postokay:
                    # We can't post our attachment
                    return False

                # Prepare our filename
                filename = (
                    attachment.name if attachment.name else f"file{no:03}.dat"
                )

                # v2 response: {"data": {"id": "...", "media_key": "...", ...}}
                try:
                    media_id = response["data"]["id"]
                except (TypeError, KeyError):
                    media_id = None

                if not media_id:
                    self.logger.debug(
                        "Could not attach the file to Twitter: %s (mime=%s)",
                        filename,
                        attachment.mimetype,
                    )
                    continue

                response.update(
                    {
                        # Normalize id for _send_tweet/_send_dm consumption
                        "media_id": media_id,
                        # Update our response to additionally include the
                        # attachment details
                        "file_name": filename,
                        "file_mime": attachment.mimetype,
                        "file_path": attachment.path,
                    }
                )

                # Save our pre-prepared payload for attachment posting
                attachments.append(response)

        # - calls _send_tweet if the mode is set so
        # - calls _send_dm (direct message) otherwise
        return getattr(self, f"_send_{self.mode}")(
            body=body,
            title=title,
            notify_type=notify_type,
            attachments=attachments,
            **kwargs,
        )

    def _send_tweet(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attachments=None,
        **kwargs,
    ):
        """Twitter Public Tweet via X API v2."""

        # Error Tracking
        has_error = False

        # Base payload; v2 uses "text" instead of the v1.1 "status" key
        payload = {
            "text": body,
        }

        payloads = []
        if not attachments:
            payloads.append(payload)

        else:
            # Group our images if batch is set to do so
            batch_size = (
                1 if not self.batch else self.__tweet_non_gif_images_batch
            )

            # Track our batch control in our message generation
            batches = []
            batch = []
            for attachment in attachments:
                # v2 media_ids must be strings
                media_id = str(attachment["media_id"])

                # Twitter supports batching images together.  This allows
                # the batching of multiple images together.  Twitter also
                # makes it clear that you can't batch `gif` files; they need
                # to be separate.  So the below preserves the ordering that
                # a user passed their attachments in.  if 4-non-gif images
                # are passed, they are all part of a single message.
                #
                # however, if they pass in image, gif, image, gif.  The
                # gif's inbetween break apart the batches so this would
                # produce 4 separate tweets.
                #
                # If you passed in, image, image, gif, image. <- This would
                # produce 3 images (as the first 2 images could be lumped
                # together as a batch)
                if not re.match(
                    r"^image/(png|jpe?g)", attachment["file_mime"], re.I
                ):
                    # Non-batchable (e.g. GIF): flush any pending batch
                    # first, then emit this attachment alone
                    if batch:
                        batches.append(list(batch))
                        batch = []
                    batches.append([media_id])
                else:
                    # PNG/JPEG: accumulate until the batch is full
                    batch.append(media_id)
                    if len(batch) >= batch_size:
                        batches.append(list(batch))
                        batch = []

            if batch:
                batches.append(list(batch))

            for no, media_ids in enumerate(batches):
                payload_ = deepcopy(payload)
                # v2 places media in a nested dict with a list of id strings
                payload_["media"] = {"media_ids": media_ids}

                if no or not body:
                    # strip text and replace it with the image representation
                    payload_["text"] = f"{no + 1:02d}/{len(batches):02d}"
                payloads.append(payload_)

        for no, payload in enumerate(payloads, start=1):
            # Send Tweet via v2 (JSON body required)
            postokay, response = self._fetch(
                self.twitter_tweet,
                payload=payload,
                json=True,
            )

            if not postokay:
                # Track our error
                has_error = True

                errors = []
                with contextlib.suppress(AttributeError, KeyError, TypeError):
                    errors = [
                        "Error {}: {}".format(
                            e.get("title", e.get("code", "unk")),
                            e.get("detail", e.get("message", "")),
                        )
                        for e in response.get("errors", [])
                    ]

                for error in errors:
                    self.logger.debug(
                        "Tweet [%.2d/%.2d] Details: %s",
                        no,
                        len(payloads),
                        error,
                    )
                continue

            # v2 response: {"data": {"id": "...", "text": "..."}}
            try:
                tweet_id = response["data"]["id"]
                url = f"https://x.com/i/web/status/{tweet_id}"

            except (KeyError, TypeError):
                url = "unknown"

            self.logger.debug(
                "Tweet [%.2d/%.2d] Details: %s", no, len(payloads), url
            )

            self.logger.info(
                "Sent [%.2d/%.2d] Twitter notification as public tweet.",
                no,
                len(payloads),
            )

        return not has_error

    def _send_dm(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attachments=None,
        **kwargs,
    ):
        """Twitter Direct Message via X API v2.

        Requires a Basic or higher X API subscription.
        Free-tier accounts will receive a 403 error.
        """

        # Error Tracking
        has_error = False

        # Lookup our users (otherwise we look up ourselves)
        targets = (
            self._whoami(lazy=self.cache)
            if not len(self.targets)
            else self._user_lookup(self.targets, lazy=self.cache)
        )

        if not targets:
            # We failed to lookup any users
            self.logger.warning(
                "Failed to acquire user(s) to Direct Message via Twitter"
            )
            return False

        # Build our list of payloads; one per attachment (or a single message)
        payloads = []
        if not attachments:
            # Plain text DM
            payloads.append({"text": body})

        else:
            for no, attachment in enumerate(attachments):
                # v2 DM attachment format: attachments list with media_id
                payload_ = {
                    "text": (
                        body
                        if (not no and body)
                        else f"{no + 1:02d}/{len(attachments):02d}"
                    ),
                    "attachments": [{"media_id": str(attachment["media_id"])}],
                }
                payloads.append(payload_)

        for no, payload in enumerate(payloads, start=1):
            for screen_name, user_id in targets.items():
                # v2 DM endpoint embeds the recipient user_id in the URL
                url = self.twitter_dm.format(user_id)

                # Send Twitter DM
                postokay, _response = self._fetch(url, payload=payload)

                if not postokay:
                    # Track our error
                    has_error = True
                    continue

                self.logger.info(
                    f"Sent [{no:02d}/{len(payloads):02d}] "
                    f"Twitter DM notification to @{screen_name}."
                )

        return not has_error

    def _whoami(self, lazy=True):
        """Looks up details of the current authenticated user via v2."""

        if lazy and self._whoami_cache is not None:
            # Use cached response
            return self._whoami_cache

        # Contains a mapping of username to id
        results = {}

        # Get current user info via v2
        postokay, response = self._fetch(
            self.twitter_whoami,
            method="GET",
        )

        if postokay:
            # v2 response: {"data": {"id": "...", "username": "...", ...}}
            try:
                data = response["data"]
                results[data["username"]] = data["id"]
                self._whoami_cache = {data["username"]: data["id"]}
                self._user_cache.update(results)

            except (TypeError, KeyError):
                pass

        return results

    def _user_lookup(self, usernames, lazy=True):
        """Looks up usernames and returns user IDs via v2.

        usernames can be a list/set/tuple as well.
        """

        # Contains a mapping of username to id
        results = {}

        # Build a unique set of names
        names = parse_list(usernames)

        if lazy and self._user_cache:
            # Use cached response
            results = {k: v for k, v in self._user_cache.items() if k in names}

            # limit our names if they already exist in our cache
            names = [name for name in names if name not in results]

        if not len(names):
            # They're is nothing further to do
            return results

        # v2 supports up to 100 usernames per request
        # https://docs.x.com/x-api/users/user-lookup/api-reference/
        #     get-users-by
        for i in range(0, len(names), 100):
            batch = names[i : i + 100]

            # Build query-string URL for GET /2/users/by?usernames=...
            lookup_url = "{}?usernames={}".format(
                self.twitter_lookup,
                ",".join(NotifyTwitter.quote(n, safe="") for n in batch),
            )

            postokay, response = self._fetch(
                lookup_url,
                method="GET",
            )

            if not postokay or not isinstance(response, dict):
                # Track our error
                continue

            # v2 response: {"data": [{"id": "...", "username": "..."}, ...]}
            for entry in response.get("data", []):
                with contextlib.suppress(TypeError, KeyError):
                    results[entry["username"]] = entry["id"]

        # Cache our response for future use; this saves on un-nessisary extra
        # hits against the Twitter API when we already know the answer
        self._user_cache.update(results)

        return results

    def _fetch(self, url, payload=None, method="POST", json=True, extra=None):
        """Wrapper to Twitter API requests object."""

        headers = {
            "User-Agent": self.app_id,
        }

        data = None
        files = None

        # Open our attachment path if required:
        if isinstance(payload, AttachBase):
            # prepare payload
            files = {
                "media": (
                    payload.name,
                    # file handle is safely closed in `finally`; inline open is
                    # intentional
                    open(payload.path, "rb"),  # noqa: SIM115
                ),
            }
            # extra holds additional form fields (e.g. media_category)
            data = extra

        elif payload is not None:
            if json:
                headers["Content-Type"] = "application/json"
                data = dumps(payload)
            else:
                # form-encoded or raw body (e.g. media upload helper)
                data = payload

        auth = OAuth1(
            self.ckey,
            client_secret=self.csecret,
            resource_owner_key=self.akey,
            resource_owner_secret=self.asecret,
        )

        # Some Debug Logging
        self.logger.debug(
            f"Twitter {method} URL: {url} "
            f"(cert_verify={self.verify_certificate})"
        )
        self.logger.debug(f"Twitter Payload: {payload!s}")

        # By default set wait to None
        wait = None

        if self.ratelimit_remaining == 0:
            # Determine how long we should wait for or if we should wait at
            # all. This isn't fool-proof because we can't be sure the client
            # time (calling this script) is completely synced up with the
            # Twitter server.  One would hope we're on NTP and our clocks are
            # the same allowing this to role smoothly:

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if now < self.ratelimit_reset:
                # We need to throttle for the difference in seconds
                # We add 0.5 seconds to the end just to allow a grace
                # period.
                wait = (self.ratelimit_reset - now).total_seconds() + 0.5

        # Default content response object
        content = {}

        # Always call throttle before any remote server i/o is made;
        self.throttle(wait=wait)

        # acquire our request mode
        fn = requests.post if method == "POST" else requests.get
        try:
            r = fn(
                url,
                data=data,
                files=files,
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

            if not (200 <= r.status_code < 300):
                # We had a problem
                status_str = NotifyTwitter.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Twitter {} to {}: {}error={}.".format(
                        method, url, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Mark our failure
                return (False, content)

            try:
                # Capture rate limiting if possible
                self.ratelimit_remaining = int(
                    r.headers.get("x-rate-limit-remaining")
                )
                self.ratelimit_reset = datetime.fromtimestamp(
                    int(r.headers.get("x-rate-limit-reset")), timezone.utc
                ).replace(tzinfo=None)

            except (TypeError, ValueError):
                # This is returned if we could not retrieve this information
                # gracefully accept this state and move on
                pass

        except requests.RequestException as e:
            self.logger.warning(
                f"Exception received when sending Twitter {method} to {url}: "
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # Mark our failure
            return (False, content)

        except OSError as e:
            self.logger.warning(
                "An I/O error occurred while handling {}.".format(
                    payload.name
                    if isinstance(payload, AttachBase)
                    else payload
                )
            )
            self.logger.debug(f"I/O Exception: {e!s}")
            return (False, content)

        finally:
            # Close our file (if it's open) stored in the second element
            # of our files tuple (index 1)
            if files:
                files["media"][1].close()

        return (True, content)

    @property
    def body_maxlen(self):
        """The maximum allowable characters allowed in the body per message
        This is used during a Private DM Message Size (not Public Tweets which
        are limited to 280 characters)"""
        return 10000 if self.mode == TwitterMessageMode.DM else 280

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol[0],
            self.ckey,
            self.csecret,
            self.akey,
            self.asecret,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "mode": self.mode,
            "batch": "yes" if self.batch else "no",
            "cache": "yes" if self.cache else "no",
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return (
            "{schema}://{ckey}/{csecret}/{akey}/{asecret}"
            "/{targets}?{params}".format(
                schema=self.secure_protocol[0],
                ckey=self.pprint(self.ckey, privacy, safe=""),
                csecret=self.pprint(
                    self.csecret, privacy, mode=PrivacyMode.Secret, safe=""
                ),
                akey=self.pprint(self.akey, privacy, safe=""),
                asecret=self.pprint(
                    self.asecret, privacy, mode=PrivacyMode.Secret, safe=""
                ),
                targets=(
                    "/".join(
                        [
                            NotifyTwitter.quote(f"@{target}", safe="@")
                            for target in self.targets
                        ]
                    )
                    if self.targets
                    else ""
                ),
                params=NotifyTwitter.urlencode(params),
            )
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        targets = len(self.targets)
        return targets if targets > 0 else 1

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Acquire remaining tokens
        tokens = NotifyTwitter.split_path(results["fullpath"])

        # The consumer token is stored in the hostname
        results["ckey"] = NotifyTwitter.unquote(results["host"])

        #
        # Now fetch the remaining tokens
        #

        # Consumer Secret
        results["csecret"] = tokens.pop(0) if tokens else None
        # Access Token Key
        results["akey"] = tokens.pop(0) if tokens else None
        # Access Token Secret
        results["asecret"] = tokens.pop(0) if tokens else None

        # The defined twitter mode
        if "mode" in results["qsd"] and len(results["qsd"]["mode"]):
            results["mode"] = NotifyTwitter.unquote(results["qsd"]["mode"])

        elif results["schema"].startswith("tweet"):
            results["mode"] = TwitterMessageMode.TWEET

        results["targets"] = []

        # if a user has been defined, add it to the list of targets
        if results.get("user"):
            results["targets"].append(results.get("user"))

        # Store any remaining items as potential targets
        results["targets"].extend(tokens)

        # Get Cache Flag (reduces lookup hits)
        if "cache" in results["qsd"] and len(results["qsd"]["cache"]):
            results["cache"] = parse_bool(results["qsd"]["cache"], True)

        # Get Batch Mode Flag
        results["batch"] = parse_bool(
            results["qsd"].get(
                "batch", NotifyTwitter.template_args["batch"]["default"]
            )
        )

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyTwitter.parse_list(
                results["qsd"]["to"]
            )

        return results
