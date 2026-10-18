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


# Create a GitHub access token:
#  1. Visit https://github.com/settings/personal-access-tokens and create a
#     fine-grained token.
#  2. Give it access to the repository you want to notify, and grant it
#     "Issues: Read and write".  Add "Pull requests: Read and write" to
#     comment on pull requests, and "Discussions: Read and write" for
#     discussions.
#  3. Copy the token, it looks like: github_pat_11ABCDEFG0123456789_abc...
#
#  Classic tokens with the "repo" scope and GitHub Actions' GITHUB_TOKEN
#  also work.
#
#  Each URL targets one GitHub location. Its path matches the browser URL:
#
#     github://{token}@{owner}/{repo}
#        - opens a new issue (the title becomes the issue title)
#     github://{token}@{owner}/{repo}/issues/{number}
#        - adds a comment to an existing issue
#     github://{token}@{owner}/{repo}/pull/{number}
#        - adds a comment to a pull request's conversation
#     github://{token}@{owner}/{repo}/discussions
#        - starts a new discussion (in the General category by default)
#     github://{token}@{owner}/{repo}/discussions/{number}
#        - adds a comment to an existing discussion
#
# Resources:
# - https://docs.github.com/en/rest/issues/issues#create-an-issue
# - https://docs.github.com/en/rest/issues/comments#create-an-issue-comment
# - https://docs.github.com/en/graphql/guides/\
#      using-the-graphql-api-for-discussions

from __future__ import annotations

from json import dumps, loads
import re
from typing import Any, Optional, Union

import requests

from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase

# GitHub-specific HTTP errors
# Based on: https://docs.github.com/en/rest/issues/issues#create-an-issue
GITHUB_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid Token.",
    403: "Forbidden - Missing permission or rate limited.",
    404: "Not Found - Unknown repository or issue, or no access to it.",
    410: "Gone - Issues are disabled on this repository.",
    422: "Validation Failed - GitHub rejected the request.",
}


class GitHubKind:
    """GitHub notification targets."""

    # An issue (opened new, or commented on)
    ISSUE = "issues"

    # A pull request (commented on only)
    PULL = "pull"

    # A discussion (started new, or commented on)
    DISCUSSION = "discussions"


# Supported target types
GITHUB_KINDS = (
    GitHubKind.ISSUE,
    GitHubKind.PULL,
    GitHubKind.DISCUSSION,
)

# Accept singular and plural target names from GitHub URLs
GITHUB_KIND_MAP = {
    "issues": GitHubKind.ISSUE,
    "issue": GitHubKind.ISSUE,
    "pull": GitHubKind.PULL,
    "pulls": GitHubKind.PULL,
    "discussions": GitHubKind.DISCUSSION,
    "discussion": GitHubKind.DISCUSSION,
}

# Default category for new discussions
GITHUB_DEFAULT_CATEGORY = "General"

# Issue, pull request, or discussion number
IS_NUMBER = re.compile(r"^\s*#?(?P<number>[1-9][0-9]{0,9})\s*$")

# Finds a discussion's internal ID from its number
GITHUB_QUERY_DISCUSSION = (
    "query($owner: String!, $repo: String!, $number: Int!) {"
    " repository(owner: $owner, name: $repo) {"
    " discussion(number: $number) { id } } }"
)

# Finds a repository's internal ID and its discussion categories
GITHUB_QUERY_CATEGORIES = (
    "query($owner: String!, $repo: String!) {"
    " repository(owner: $owner, name: $repo) { id"
    " discussionCategories(first: 100) { nodes { id name slug } } } }"
)

# Adds a comment to a discussion
GITHUB_MUTATION_COMMENT = (
    "mutation($id: ID!, $body: String!) {"
    " addDiscussionComment(input: {discussionId: $id, body: $body})"
    " { comment { id } } }"
)

# Starts a new discussion
GITHUB_MUTATION_DISCUSSION = (
    "mutation($repo: ID!, $category: ID!, $title: String!,"
    " $body: String!) {"
    " createDiscussion(input: {repositoryId: $repo,"
    " categoryId: $category, title: $title, body: $body})"
    " { discussion { number } } }"
)


class NotifyGitHub(NotifyBase):
    """Send notifications to GitHub issues, pull requests, and discussions."""

    # The default descriptive name associated with the Notification
    service_name = "GitHub"

    # Service URL
    service_url = "https://github.com/"

    # Secure protocol
    secure_protocol = "github"

    # Setup guide
    setup_url = "https://appriseit.com/services/github/"

    # REST endpoint for issues and pull request comments
    notify_url = "https://api.github.com/repos/{owner}/{repo}/issues"

    # GraphQL endpoint for discussions
    graphql_url = "https://api.github.com/graphql"

    # Supported GitHub REST API version
    api_version = "2022-11-28"

    # Shared body limit for issues, discussions, and comments
    body_maxlen = 65536

    # GitHub renders Markdown in issues, discussions and comments
    notify_format = NotifyFormat.MARKDOWN

    # Supported URL forms
    templates = (
        # Open a new issue
        "{schema}://{token}@{owner}/{repo}",
        # Open a new issue or start a new discussion
        "{schema}://{token}@{owner}/{repo}/{kind}",
        # Comment on an issue, pull request or discussion
        "{schema}://{token}@{owner}/{repo}/{kind}/{number}",
    )

    # URL path tokens
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
            "owner": {
                "name": _("Owner"),
                "type": "string",
                "required": True,
                "regex": (r"^[a-z0-9-]+$", "i"),
            },
            "repo": {
                "name": _("Repository"),
                "type": "string",
                "required": True,
                "regex": (r"^[a-z0-9_.-]+$", "i"),
            },
            "kind": {
                "name": _("Type"),
                "type": "choice:string",
                "values": GITHUB_KINDS,
                "default": GitHubKind.ISSUE,
            },
            "number": {
                "name": _("Number"),
                "type": "int",
                "min": 1,
            },
        },
    )

    # URL query arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "token": {
                "alias_of": "token",
            },
            "labels": {
                "name": _("Labels"),
                "type": "list:string",
            },
            "assignees": {
                "name": _("Assignees"),
                "type": "list:string",
            },
            "category": {
                "name": _("Category"),
                "type": "string",
                "default": GITHUB_DEFAULT_CATEGORY,
            },
        },
    )

    def __init__(
        self,
        token: Optional[str] = None,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        kind: Optional[str] = None,
        number: Optional[Union[int, str]] = None,
        labels: Optional[Union[str, list[str]]] = None,
        assignees: Optional[Union[str, list[str]]] = None,
        category: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a GitHub notification target."""
        super().__init__(**kwargs)

        # Access token
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = "An invalid GitHub access token was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # User or organization that owns the repository
        self.owner = validate_regex(
            owner, *self.template_tokens["owner"]["regex"]
        )
        if not self.owner:
            msg = f"An invalid GitHub owner ({owner}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Repository name
        self.repo = validate_regex(
            repo, *self.template_tokens["repo"]["regex"]
        )
        if not self.repo:
            msg = f"An invalid GitHub repository ({repo}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Target type; issues are the default
        self.kind = (
            GITHUB_KIND_MAP.get(str(kind).lower())
            if kind
            else self.template_tokens["kind"]["default"]
        )
        if not self.kind:
            msg = f"An unsupported GitHub path ({kind}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Existing target number; omit it to create a new target
        self.number = None
        if number is not None:
            result = IS_NUMBER.match(str(number))
            if not result:
                msg = f"An invalid GitHub number ({number}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            # Store the normalized number
            self.number = int(result.group("number"))

        # A pull request can only be commented on, never created
        if self.kind == GitHubKind.PULL and not self.number:
            msg = "A GitHub pull request number must be specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Labels and assignees only apply when opening a new issue
        self.labels = parse_list(labels)
        self.assignees = parse_list(assignees)

        # Category for new discussions
        self.category = (
            category.strip()
            if isinstance(category, str) and category.strip()
            else self.template_args["category"]["default"]
        )

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Send the notification to GitHub."""

        # New issues and discussions require a title
        title = title if title else self.app_desc

        if self.kind == GitHubKind.DISCUSSION:
            # Discussions are only reachable through GraphQL
            return self._send_discussion(body, title)

        # Start with the repository's issues endpoint
        url = self.notify_url.format(
            owner=NotifyGitHub.quote(self.owner, safe=""),
            repo=NotifyGitHub.quote(self.repo, safe=""),
        )

        if self.number:
            # Issues and pull requests share the same comment endpoint
            url += f"/{self.number}/comments"

            # Apprise has already merged the title into the comment body
            payload = {"body": body}

        else:
            # Create a new issue
            payload = {"title": title, "body": body}

            # Add optional labels and assignees
            if self.labels:
                payload["labels"] = self.labels

            if self.assignees:
                payload["assignees"] = self.assignees

        # Send the request
        return self._post(url, payload)[0]

    def _send_discussion(self, body: str, title: str) -> bool:
        """Comment on a discussion, or start a new one."""

        if self.number:
            # Look up the discussion's internal ID
            ok, content = self._post(
                self.graphql_url,
                {
                    "query": GITHUB_QUERY_DISCUSSION,
                    "variables": {
                        "owner": self.owner,
                        "repo": self.repo,
                        "number": self.number,
                    },
                },
            )
            if not ok:
                return False

            # Read the internal discussion ID
            try:
                discussion_id = content["data"]["repository"]["discussion"][
                    "id"
                ]

            except (KeyError, TypeError):
                # A missing discussion, or a reply shaped unexpectedly
                discussion_id = None

            if not discussion_id:
                self.logger.warning(
                    "GitHub discussion %d was not found in %s/%s.",
                    self.number,
                    self.owner,
                    self.repo,
                )
                return False

            # Add the comment
            return self._post(
                self.graphql_url,
                {
                    "query": GITHUB_MUTATION_COMMENT,
                    "variables": {"id": discussion_id, "body": body},
                },
            )[0]

        # Look up the repository's internal ID and its categories
        ok, content = self._post(
            self.graphql_url,
            {
                "query": GITHUB_QUERY_CATEGORIES,
                "variables": {"owner": self.owner, "repo": self.repo},
            },
        )
        if not ok:
            return False

        # Read the repository and its available categories
        try:
            repository = content["data"]["repository"]
            repository_id = repository["id"]
            nodes = repository["discussionCategories"]["nodes"]

            # Every category can be matched by its name or its URL slug
            category_ids = {
                key.lower(): c["id"]
                for c in nodes
                for key in (c["name"], c["slug"])
            }
            names = [c["name"] for c in nodes]

        except (AttributeError, KeyError, TypeError):
            # A reply shaped unexpectedly leaves nothing to match against
            repository_id, category_ids, names = None, {}, []

        # Match the category by name or URL slug
        category_id = category_ids.get(self.category.lower())

        if not repository_id or not category_id:
            self.logger.warning(
                "GitHub discussion category %s was not found in %s/%s;"
                " available: %s.",
                self.category,
                self.owner,
                self.repo,
                ", ".join(names) or "none",
            )
            return False

        # Start the discussion
        return self._post(
            self.graphql_url,
            {
                "query": GITHUB_MUTATION_DISCUSSION,
                "variables": {
                    "repo": repository_id,
                    "category": category_id,
                    "title": title,
                    "body": body,
                },
            },
        )[0]

    def _post(
        self, url: str, payload: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        """POST to GitHub and return ``(ok, parsed response)``."""

        # Request headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": self.api_version,
        }

        self.logger.debug(
            "GitHub POST URL: %s (cert_verify=%r)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("GitHub Payload: %s", payload)

        # Apply rate limiting before contacting GitHub
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # The HTTP status remains useful without a readable body
                content = {}

            if not isinstance(content, dict):
                # Ignore unexpected non-object responses
                content = {}

            if r.status_code not in (
                requests.codes.ok,
                requests.codes.created,
            ):
                status_str = NotifyGitHub.http_response_code_lookup(
                    r.status_code, GITHUB_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send GitHub notification: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                return (False, content)

            errors = content.get("errors")
            if errors:
                # GraphQL reports its errors inside a successful response
                self.logger.warning(
                    "Failed to send GitHub notification: %s",
                    "; ".join(
                        str(e.get("message", e))
                        if isinstance(e, dict)
                        else str(e)
                        for e in (
                            errors if isinstance(errors, list) else [errors]
                        )
                    ),
                )

                return (False, content)

            self.logger.info("Sent GitHub notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending GitHub notification."
            )
            self.logger.debug("Socket Exception: %s", str(e))

            return (False, {})

        return (True, content)

    @property
    def title_maxlen(self) -> int:
        """Maximum title length: 256 for something new, 0 for a comment."""
        # A comment has no title field, so let Apprise merge it into the body
        return 0 if self.number else 256

    @property
    def url_identifier(self) -> tuple[str, ...]:
        """Return the account fields that uniquely identify this URL."""
        # The repository is a target, so only the token identifies the account
        return (self.secure_protocol, self.token)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Return this notification target as an Apprise URL."""

        # Optional query parameters
        params = {}

        if self.labels:
            params["labels"] = ",".join(self.labels)

        if self.assignees:
            params["assignees"] = ",".join(self.assignees)

        if self.category != self.template_args["category"]["default"]:
            params["category"] = self.category

        # Add common Apprise parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # New issues need no target path
        path = (
            f"/{self.kind}/{self.number}"
            if self.number
            else (f"/{self.kind}" if self.kind != GitHubKind.ISSUE else "")
        )

        return "{schema}://{token}@{owner}/{repo}{path}/?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            owner=NotifyGitHub.quote(self.owner, safe=""),
            repo=NotifyGitHub.quote(self.repo, safe=""),
            path=path,
            params=NotifyGitHub.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parse an Apprise URL into GitHub constructor arguments."""
        results = NotifyBase.parse_url(url)
        if not results:
            return results

        # The owner is stored in the host field
        results["owner"] = NotifyGitHub.unquote(results["host"])

        # The token is stored in the user field
        results["token"] = (
            NotifyGitHub.unquote(results["user"]) if results["user"] else None
        )

        # Let the query string override the user-field token
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyGitHub.unquote(results["qsd"]["token"])

        # The remaining path follows a GitHub browser URL
        entries = NotifyGitHub.split_path(results["fullpath"])

        # Repository name
        results["repo"] = entries.pop(0) if entries else None

        # Target type
        if entries:
            results["kind"] = entries.pop(0)

        # Target number; /new means create a new issue or discussion
        if entries and entries[0].lower() == "new":
            entries.pop(0)

        elif entries:
            results["number"] = entries.pop(0)

        # Ignore browser suffixes such as /files, but reject another number
        if any(IS_NUMBER.match(e) for e in entries):
            results["number"] = "/".join(
                [str(results.get("number") or "new"), *entries]
            )

        # New issue options
        if "labels" in results["qsd"] and results["qsd"]["labels"]:
            results["labels"] = NotifyGitHub.unquote(results["qsd"]["labels"])

        if "assignees" in results["qsd"] and results["qsd"]["assignees"]:
            results["assignees"] = NotifyGitHub.unquote(
                results["qsd"]["assignees"]
            )

        # New discussion category
        if "category" in results["qsd"] and results["qsd"]["category"]:
            results["category"] = NotifyGitHub.unquote(
                results["qsd"]["category"]
            )

        return results
