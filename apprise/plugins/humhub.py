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

# HumHub is a self-hosted social network for teams.
#
# To post notifications to HumHub you need:
#   1. A running HumHub instance with the REST API module enabled.
#      Visit: https://marketplace.humhub.com/module/rest
#   2. Authentication: either a Bearer token or a username and password
#      (Basic Authentication).
#   3. The numeric ID of the container (space) you want to post to.
#
# To enable and configure Bearer Authentication in HumHub:
#   1. Log in to your HumHub instance as an administrator.
#   2. Navigate to Administration > Modules and ensure the REST API
#      module is installed and active.
#   3. Go to Administration > Authentication > REST API > Bearer Auth.
#   4. Enable Bearer token authentication and create a new token.
#   5. Copy the generated token -- this is your {token}.
#
# To find a container (space) ID:
#   1. Navigate to the space in your HumHub instance.
#   2. The container ID appears in URLs such as:
#      https://yourhost/s/my-space-1  (the trailing number)
#   3. Alternatively, query the REST API:
#      GET /api/v1/space  to list all spaces with their IDs.
#
# Apprise URLs:
#   Bearer token over HTTPS (recommended):
#     humhubs://{token}@{hostname}/{container_id}
#   Multiple containers in one URL:
#     humhubs://{token}@{hostname}/{id1}/{id2}/{id3}
#   Basic authentication over HTTPS:
#     humhubs://{user}:{password}@{hostname}/{container_id}
#   Insecure HTTP -- not recommended for production:
#     humhub://{token}@{hostname}/{container_id}
#   Targets via ?to= parameter:
#     humhubs://{token}@{hostname}/?to={id1},{id2}
#
# API Reference:
#   https://marketplace.humhub.com/module/rest/docs/html/post.html

from itertools import chain
from json import dumps, loads

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_list
from .base import NotifyBase


class NotifyHumHub(NotifyBase):
    """A wrapper for HumHub Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "HumHub"

    # The services URL
    service_url = "https://www.humhub.com/"

    # The default protocol
    protocol = "humhub"

    # The default secure protocol (HTTPS)
    secure_protocol = "humhubs"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/humhub/"

    # HumHub posts have no native title field; the framework prepends
    # a non-empty title to the body automatically when title_maxlen <= 0
    title_maxlen = 0

    # Maximum post length (characters)
    body_maxlen = 4000

    # Self-hosted service; relax the default throttle slightly
    request_rate_per_sec = 0.02

    # HumHub supports file attachments via a two-step API:
    # POST /api/v1/post/container/{id} to create the post (returns post ID),
    # then POST /api/v1/post/{post_id}/upload-files to attach each file
    attachment_support = True

    # Define object URL templates
    templates = (
        # Bearer token -- user field only, no password
        "{schema}://{user}@{host}/{targets}",
        "{schema}://{user}@{host}:{port}/{targets}",
        # Basic auth -- user + password
        "{schema}://{user}:{password}@{host}/{targets}",
        "{schema}://{user}:{password}@{host}:{port}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "user": {
                "name": _("Token or Username"),
                "type": "string",
                "required": True,
                "private": True,
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
            },
            "host": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
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
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(self, targets=None, **kwargs):
        """Initialize HumHub Object."""
        super().__init__(**kwargs)

        # Determine our schema (http vs https)
        self.schema = "https" if self.secure else "http"

        # Require authentication credentials
        if not self.user:
            msg = "A HumHub bearer token or username must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Accumulate invalid targets for lossless URL round-tripping
        self._invalid_targets = []

        # Parse and validate container IDs (must be positive integers)
        self.targets = []
        for target in parse_list(targets):
            try:
                cid = int(str(target).strip())
                if cid > 0:
                    # Valid positive integer container ID
                    self.targets.append(str(cid))
                    continue
            except (ValueError, TypeError):
                pass

            # Invalid container ID -- track it so the URL round-trips
            self.logger.warning(
                "Dropping invalid HumHub container ID: %s", target
            )
            self._invalid_targets.append(str(target))

        # Require at least one valid container ID to proceed
        if not self.targets:
            msg = "No valid HumHub container ID(s) were specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform HumHub Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Determine authentication method
        if self.password:
            # Basic authentication -- pass credentials via auth= argument
            auth = (self.user, self.password)
        else:
            # Bearer token authentication via Authorization header
            auth = None
            headers["Authorization"] = "Bearer {}".format(self.user)

        # Prepare our payload (HumHub wraps the message in a data object)
        payload = {"data": {"message": body}}

        # Prepare port reference
        port = "" if self.port is None else ":{}".format(self.port)

        # Track overall success across all container posts
        has_error = False

        # Post to each container in turn
        for container_id in self.targets:
            # Build the HumHub post creation URL for this container
            url = "{}://{}{}/api/v1/post/container/{}".format(
                self.schema, self.host, port, container_id
            )

            # Create the post
            ok, content = self._send(url, dumps(payload), headers, auth)
            if not ok:
                # Mark our failure
                has_error = True
                continue

            self.logger.info(
                "Sent HumHub notification to container %s.",
                container_id,
            )

            # Skip attachment handling if no attachments were provided
            if not attach:
                continue

            # Parse the post ID from the creation response so we can
            # attach files to the newly created post
            try:
                response = loads(content)
                post_id = response.get("id")
            except (AttributeError, TypeError, ValueError):
                post_id = None

            if not post_id:
                self.logger.warning(
                    "Failed to parse HumHub post ID from response;"
                    " attachments will not be sent to container %s.",
                    container_id,
                )
                # Mark our failure
                has_error = True
                continue

            # Build the attachment upload URL for this post
            attach_url = "{}://{}{}/api/v1/post/{}/upload-files".format(
                self.schema, self.host, port, post_id
            )

            # Upload each attachment to the newly created post
            for attachment in attach:
                # Verify the attachment is accessible before uploading
                if not attachment:
                    self.logger.warning(
                        "Could not access HumHub attachment %s.",
                        attachment.url(privacy=True),
                    )
                    # Mark our failure
                    has_error = True
                    continue

                # Upload the attachment
                ok, _ = self._send(
                    attach_url,
                    None,
                    headers,
                    auth,
                    attach=attachment,
                )
                if not ok:
                    # Mark our failure
                    has_error = True

        return not has_error

    def _send(self, url, payload=None, headers=None, auth=None, attach=None):
        """Wrapper to the requests (post) object.

        Returns (ok, content) where content is the raw response bytes
        on success, or None on failure.
        """

        # Track any open file handle for cleanup in finally
        files = None

        self.logger.debug(
            "HumHub POST URL: %s (cert_verify=%r)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("HumHub Payload: %s", str(payload))

        # Always call throttle before any network request
        self.throttle()

        try:
            # Open our attachment and build multipart payload if provided;
            # strip Content-Type so requests sets multipart/form-data
            if attach:
                _headers = {
                    k: v
                    for k, v in (headers or {}).items()
                    if k != "Content-Type"
                }
                files = {"files[]": (attach.name, attach.open())}
            else:
                _headers = headers or {}

            r = requests.post(
                url,
                data=payload,
                headers=_headers,
                files=files,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code != requests.codes.ok:
                # We had a failure
                status_str = NotifyHumHub.http_response_code_lookup(
                    r.status_code
                )
                self.logger.warning(
                    "Failed to send HumHub %s: %s%serror=%s.",
                    "attachment" if attach else "notification",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )
                self.logger.debug("Response Details:\r\n%s", r.content)
                # Return failure with no content
                return (False, None)

            # Return success with raw response content
            return (True, r.content)

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending HumHub %s.",
                "attachment" if attach else "notification",
            )
            self.logger.debug("Socket Exception: %s", str(e))
            # Return failure with no content
            return (False, None)

        except OSError as e:
            self.logger.warning(
                "An I/O error occurred while reading %s.",
                attach.name if attach else "attachment",
            )
            self.logger.debug("I/O Exception: %s", str(e))
            # Return failure with no content
            return (False, None)

        finally:
            # Close our file handle (if it was opened)
            if files:
                files["files[]"][1].close()

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user,
            self.password,
            self.host,
            self.port if self.port else (443 if self.secure else 80),
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Prepare our parameters
        params = {}
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Default port reference
        default_port = 443 if self.secure else 80

        # Build the auth portion of the URL
        if self.password:
            # Basic auth: user:password@
            auth = "{user}:{password}@".format(
                user=self.pprint(self.user, privacy, safe=""),
                password=self.pprint(
                    self.password,
                    privacy,
                    mode=PrivacyMode.Secret,
                    safe="",
                ),
            )
        else:
            # Bearer token: token@
            auth = "{token}@".format(
                token=self.pprint(self.user, privacy, safe=""),
            )

        return "{schema}://{auth}{host}{port}/{targets}/?{params}".format(
            schema=(self.secure_protocol if self.secure else self.protocol),
            auth=auth,
            host=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else ":{}".format(self.port)
            ),
            targets="/".join(
                NotifyHumHub.quote(t, safe="")
                for t in chain(self.targets, self._invalid_targets)
            ),
            params=NotifyHumHub.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us
        to re-instantiate this object."""
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early
            return results

        # Acquire container IDs from the URL path
        results["targets"] = NotifyHumHub.split_path(results["fullpath"])

        # Support ?to= as a comma-separated list of additional container IDs
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifyHumHub.parse_list(results["qsd"]["to"])

        return results
