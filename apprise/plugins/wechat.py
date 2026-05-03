#
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# WeCom (WeChat Work / Enterprise WeChat) Application Message API.
#
# This plugin sends notifications directly to users, departments, or
# tags within a WeCom enterprise organisation using the WeCom
# Application API.  No third-party intermediary is required.
#
# Setup:
#   1. Sign in to the WeCom admin console at
#      https://work.weixin.qq.com/wework_admin/frame#/index
#   2. Go to "Applications & Mini Programs" -> "Applications" and
#      create or select a self-built application.
#   3. Copy the AgentID shown on the application details page.
#   4. Go to "My Enterprise" -> "Enterprise Information" and note
#      the CorpID.
#   5. On the application page click "View" next to Secret and copy it.
#
# Basic Apprise URL forms:
#
#   Send to all users in the organisation:
#     wechat://{corpid}:{corpsecret}@{agentid}/@all
#
#   Send to specific user(s) by WeCom user ID (@ prefix optional
#   on input, always emitted in generated URLs):
#     wechat://{corpid}:{corpsecret}@{agentid}/@{userid}
#     wechat://{corpid}:{corpsecret}@{agentid}/@{user1}/@{user2}
#
#   Send to a department by its numeric ID (# encoded as %23 in URLs):
#     wechat://{corpid}:{corpsecret}@{agentid}/%23{deptid}
#
#   Send to a tag by its numeric ID (prefix with +):
#     wechat://{corpid}:{corpsecret}@{agentid}/+{tagid}
#
#   Mixed recipients:
#     wechat://{corpid}:{corpsecret}@{agentid}/@{user}/%23{dept}/+{tag}
#
#   Notes:
#     - # must be URL-encoded as %23 in URL paths to avoid being
#       treated as a fragment separator.
#     - At least one recipient (user, department, or tag) is required.
#     - Use @all as a user target to send to the entire organisation.
#     - Use ?to= to supply comma-separated extra targets as a query
#       parameter alternative.
#
# API References:
#   https://developer.work.weixin.qq.com/document/path/90235
#   https://developer.work.weixin.qq.com/document/path/90236

import json
import re

import requests

from ..common import NotifyFormat, NotifyType, PersistentStoreMode
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase

# WeCom API error code map.
# Reference: https://developer.work.weixin.qq.com/document/path/90313
WECHAT_ERROR_CODES = {
    0: "Request succeeded.",
    40001: "Invalid credential or access token expired.",
    40003: "Invalid user ID.",
    40014: "Invalid access token.",
    42001: "Access token expired.",
    48001: "API not authorized; check application permissions.",
    60020: "IP address not in the allowlist.",
    81013: "All recipients are invalid or unauthorized.",
}

# Error codes that indicate the cached access token must be discarded
# so the next send() call will fetch a fresh one.
WECHAT_TOKEN_ERROR_CODES = frozenset((40001, 40014, 42001))

# Validates a WeCom user ID.  The optional leading @ is stripped by
# the regex so both "johndoe" and "@johndoe" are accepted.  The
# special @all broadcast keyword is matched as "all"; the caller
# re-attaches the @ before storing.  url() always emits the @ prefix.
IS_USER = re.compile(
    r"^@?(?P<user>[A-Za-z0-9][A-Za-z0-9_@.\-]*)$",
)

# Validates a department target: # prefix followed by a numeric ID.
# The # will arrive already decoded from %23 by the URL path parser.
IS_DEPT = re.compile(r"^#(?P<dept>[0-9]+)$")

# Validates a tag target: + prefix followed by a numeric ID.
IS_TAG = re.compile(r"^\+(?P<tag>[0-9]+)$")


class NotifyWeChat(NotifyBase):
    """A wrapper for WeCom (WeChat Work) Application Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "WeChat (WeCom)"

    # The services URL
    service_url = "https://work.weixin.qq.com/"

    # The default secure protocol
    secure_protocol = "wechat"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/wechat/"

    # WeCom access token endpoint (GET request)
    token_url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"

    # WeCom message send endpoint (POST); access_token is a query param
    notify_url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"

    # WeCom text and markdown bodies are limited to 2048 bytes
    body_maxlen = 2048

    # WeCom application messages have no native separate title field
    title_maxlen = 0

    # Default to plain text; markdown is also natively supported
    notify_format = NotifyFormat.TEXT

    # Enable the persistent store so the access token survives across
    # plugin instantiations and process restarts
    storage_mode = PersistentStoreMode.AUTO

    # Cache the access token for slightly less than its 2-hour lifetime
    # to avoid racing the expiry boundary
    default_cache_expiry_sec = 7200 - 300  # 1 h 55 min

    # URL templates
    templates = (
        # No path targets: recipients supplied via ?to= or @all
        "{schema}://{user}:{password}@{host}",
        # One or more targets in the URL path
        "{schema}://{user}:{password}@{host}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            # Corp ID sits in the URL user field
            "user": {
                "name": _("Corp ID"),
                "type": "string",
                "required": True,
                "map_to": "corpid",
            },
            # App Secret sits in the URL password field
            "password": {
                "name": _("App Secret"),
                "type": "string",
                "private": True,
                "required": True,
                "map_to": "corpsecret",
            },
            # Agent ID sits in the URL host field; always numeric
            "host": {
                "name": _("Agent ID"),
                "type": "string",
                "required": True,
                "regex": (r"^[0-9]+$", ""),
                "map_to": "agentid",
            },
            # A WeCom user ID (@ prefix optional on input,
            # always emitted by url())
            "target_user": {
                "name": _("Target User"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
            },
            # A WeCom department ID (numeric; prefix with #)
            "target_department": {
                "name": _("Target Department"),
                "type": "string",
                "prefix": "#",
                "map_to": "targets",
            },
            # A WeCom tag ID (numeric; prefix with +)
            "target_tag": {
                "name": _("Target Tag"),
                "type": "string",
                "prefix": "+",
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
            # ?to= is the standard Apprise comma-separated recipient alias
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(self, corpid, corpsecret, agentid, targets=None, **kwargs):
        """Initialize WeChat (WeCom Application) Object."""
        super().__init__(**kwargs)

        # Validate the Corp ID
        self.corpid = validate_regex(corpid)
        if not self.corpid:
            msg = "A WeChat (WeCom) Corp ID must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate the App Secret
        self.corpsecret = validate_regex(corpsecret)
        if not self.corpsecret:
            msg = "A WeChat (WeCom) App Secret must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate the Agent ID (must be a non-negative integer string)
        self.agentid = validate_regex(
            str(agentid) if agentid is not None else "",
            *self.template_tokens["host"]["regex"],
        )
        if not self.agentid:
            msg = (
                "The WeChat (WeCom) Agent ID ({}) is invalid;"
                " it must be a non-negative integer.".format(agentid)
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Parsed and validated recipient lists
        self.users = []
        self.departments = []
        self.tag_ids = []

        # Preserve unrecognised targets for round-trip URL fidelity
        self.invalid_targets = []

        # Classify each entry from the targets list
        for target in parse_list(targets):
            # Department ID: # prefix + numeric
            result = IS_DEPT.match(target)
            if result:
                self.departments.append(result.group("dept"))
                continue

            # Tag ID: + prefix + numeric
            result = IS_TAG.match(target)
            if result:
                self.tag_ids.append(result.group("tag"))
                continue

            # User ID or @all broadcast.
            # The regex strips the optional leading @ so both "johndoe"
            # and "@johndoe" match.  "all" (captured from "@all" or bare
            # "all") is re-normalised to "@all" for the WeCom API.
            result = IS_USER.match(target)
            if result:
                user = result.group("user")
                self.users.append("@all" if user == "all" else user)
                continue

            # Unrecognised -- log and preserve for round-trip
            self.logger.warning(
                "Invalid/unrecognized WeChat (WeCom) target preserved"
                " for round-trip fidelity: %s",
                target,
            )
            self.invalid_targets.append(target)

        return

    def _get_access_token(self):
        """Return the cached WeCom access token, fetching a fresh one
        if the cache is empty or the token has expired."""

        # Check the persistent store for a cached token
        token = self.store.get("access_token")
        if token:
            # Return the cached token
            return token

        # Build the query parameters for the token request
        params = {
            "corpid": self.corpid,
            "corpsecret": self.corpsecret,
        }

        self.logger.debug(
            "WeChat (WeCom) token GET URL: %s (cert_verify=%r)",
            self.token_url,
            self.verify_certificate,
        )

        # Always throttle before any remote server I/O
        self.throttle()

        try:
            r = requests.get(
                self.token_url,
                params=params,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok:
                # HTTP-level failure
                status_str = NotifyWeChat.http_response_code_lookup(
                    r.status_code
                )
                self.logger.warning(
                    "Failed to fetch WeChat access token: "
                    "{}{}error={}.".format(
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )
                self.logger.debug(
                    "Response Details:\r\n%r",
                    (r.content or b"")[:2000],
                )
                # Return None to indicate failure
                return None

            # Parse the JSON response body
            try:
                content = json.loads(r.content)
            except (AttributeError, TypeError, ValueError):
                content = {}

            # Check the WeCom application-level error code
            errcode = content.get("errcode", 0) if content else -1
            if errcode != 0:
                errmsg = WECHAT_ERROR_CODES.get(
                    errcode,
                    content.get("errmsg", "Unknown error")
                    if content
                    else "Unknown error",
                )
                self.logger.warning(
                    "WeChat access token request failed: "
                    "errcode={}: {}.".format(errcode, errmsg)
                )
                # Return None to indicate failure
                return None

            # Extract the access token from the response
            token = content.get("access_token") if content else None
            if not token:
                self.logger.warning(
                    "WeChat access token response contained no token."
                )
                # Return None to indicate failure
                return None

            # Derive the cache TTL: expires_in minus a grace period to
            # avoid racing the expiry boundary
            expires_in = content.get("expires_in", 7200) if content else 7200
            ttl = max(60, expires_in - 300)

            # Cache the token for reuse across plugin instances
            self.store.set("access_token", token, expires=ttl)

            # Return the freshly fetched token
            return token

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred fetching the WeChat access token."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            # Return None to indicate failure
            return None

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform WeChat (WeCom Application) Notification."""

        # Compile the recipient lists
        users = list(self.users)
        departments = list(self.departments)
        tags = list(self.tag_ids)

        # At least one valid recipient is required to proceed
        if not users and not departments and not tags:
            self.logger.warning(
                "No WeChat (WeCom) recipients configured; aborting."
            )
            return False

        # Obtain (or reuse from cache) a valid access token
        token = self._get_access_token()
        if not token:
            return False

        # Determine the WeCom msgtype from the active notify_format
        if self.notify_format == NotifyFormat.MARKDOWN:
            msgtype = "markdown"
        else:
            # Both TEXT and HTML fall back to plain text
            msgtype = "text"

        # Build the message content wrapper
        msgbody = {"content": body}

        # Assemble the full request payload
        payload = {
            "agentid": int(self.agentid),
            "msgtype": msgtype,
            msgtype: msgbody,
        }

        # Add recipient fields -- only include lists that are non-empty
        if users:
            payload["touser"] = "|".join(users)
        if departments:
            payload["toparty"] = "|".join(departments)
        if tags:
            payload["totag"] = "|".join(tags)

        # Prepare the request headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Append the access token as a query parameter on the send URL
        send_url = "{}?access_token={}".format(self.notify_url, token)

        self.logger.debug(
            "WeChat (WeCom) POST URL: %s (cert_verify=%r)",
            self.notify_url,
            self.verify_certificate,
        )
        self.logger.debug("WeChat (WeCom) Payload: %r", payload)

        # Always throttle before any remote server I/O
        self.throttle()

        try:
            r = requests.post(
                send_url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok:
                # HTTP-level failure
                status_str = NotifyWeChat.http_response_code_lookup(
                    r.status_code
                )
                self.logger.warning(
                    "Failed to send WeChat (WeCom) notification: "
                    "{}{}error={}.".format(
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )
                self.logger.debug(
                    "Response Details:\r\n%r",
                    (r.content or b"")[:2000],
                )
                # Return; we're done
                return False

            # Parse the JSON response body
            try:
                content = json.loads(r.content)
            except (AttributeError, TypeError, ValueError):
                content = {}

            # Check the WeCom application-level error code
            errcode = content.get("errcode", 0) if content else -1
            if errcode != 0:
                # Token error codes mean the cached token has expired;
                # evict it so the next call fetches a fresh one
                if errcode in WECHAT_TOKEN_ERROR_CODES:
                    self.store.set("access_token", None, expires=1)

                errmsg = WECHAT_ERROR_CODES.get(
                    errcode,
                    content.get("errmsg", "Unknown error")
                    if content
                    else "Unknown error",
                )
                self.logger.warning(
                    "Failed to send WeChat (WeCom) notification: "
                    "errcode={}: {}.".format(errcode, errmsg)
                )
                self.logger.debug(
                    "Response Details:\r\n%r",
                    content if content else (r.content or b"")[:2000],
                )
                # Return; we're done
                return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending"
                " WeChat (WeCom) notification."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            # Return; we're done
            return False

        self.logger.info("Sent WeChat (WeCom) notification.")
        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique
        from another similar one.

        Targets or end points should never be identified here.
        """
        # Corp + secret + agentid together uniquely identify the app
        return (
            self.secure_protocol,
            self.corpid,
            self.corpsecret,
            self.agentid,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified
        arguments."""

        params = {}
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Re-assemble the targets list, restoring each type's prefix.
        # Department IDs use # which must be percent-encoded in paths.
        targets = []
        for user in self.users:
            if user.startswith("@"):
                # @all and any other @-prefixed broadcast keyword;
                # emit as-is since the @ is already present
                targets.append(NotifyWeChat.quote(user, safe="@"))
            else:
                # Regular user ID; always emit with @ prefix so the
                # URL is self-describing and consistent with the
                # target_user prefix declaration
                targets.append("@{}".format(NotifyWeChat.quote(user, safe="")))
        for dept in self.departments:
            # Encode # as %23 so it is not treated as a URL fragment
            targets.append("%23{}".format(dept))
        for tag in self.tag_ids:
            targets.append("+{}".format(tag))
        # Always include invalid entries so the URL round-trips without
        # silent data loss
        for inv in self.invalid_targets:
            targets.append(NotifyWeChat.quote(inv, safe=""))

        default_schema = self.secure_protocol

        if targets:
            return (
                "{schema}://{corpid}:{corpsecret}@{agentid}"
                "/{targets}/?{params}".format(
                    schema=default_schema,
                    corpid=NotifyWeChat.quote(self.corpid, safe=""),
                    corpsecret=self.pprint(self.corpsecret, privacy, safe=""),
                    agentid=self.agentid,
                    targets="/".join(targets),
                    params=NotifyWeChat.urlencode(params),
                )
            )

        return "{schema}://{corpid}:{corpsecret}@{agentid}/?{params}".format(
            schema=default_schema,
            corpid=NotifyWeChat.quote(self.corpid, safe=""),
            corpsecret=self.pprint(self.corpsecret, privacy, safe=""),
            agentid=self.agentid,
            params=NotifyWeChat.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Corp ID comes from the URL user field
        results["corpid"] = NotifyWeChat.unquote(results["user"])

        # App Secret comes from the URL password field
        results["corpsecret"] = NotifyWeChat.unquote(results["password"])

        # Agent ID comes from the URL host field
        results["agentid"] = NotifyWeChat.unquote(results["host"])

        # Collect targets from the URL path
        results["targets"] = NotifyWeChat.split_path(results["fullpath"])

        # Support ?to= for additional comma-separated targets
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifyWeChat.parse_list(results["qsd"]["to"])

        return results

    @staticmethod
    def parse_native_url(url):
        """WeCom does not expose a shareable single-URL credential form,
        so native URL detection is not supported."""
        return None
