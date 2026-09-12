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

# Delta Chat reuses Email delivery and adds its chat-specific headers.
#
# Steps to set this up:
#  1. Get a mailbox for your bot. Any regular e-mail account works, but a
#     purpose-built "chatmail" relay (see https://chatmail.at/) is what
#     most Delta Chat users are already on.
#  2. Note the account's SMTP host, port, username, and password.
#  3. The person you want to notify must already have (or add) your bot's
#     address as a contact in Delta Chat; a first message from an unknown
#     address lands in their "Contact Requests" list until accepted.
#
#  Your Apprise URL should be assembled as:
#     deltachat://user:password@smtp.example.com/friend@example.org
#
# Many chatmail relays reject unencrypted mail outright, so consider
# pairing this with ?pgp=sign or ?pgp=encrypt. Email's PGP documentation
# applies here unchanged.
#
# Resources:
# - https://delta.chat/
# - https://github.com/deltachat/spec (the e-mail-chat protocol)
# - https://docs.autocrypt.org/level1.html (the Autocrypt header format)

from ..common import NotifyFormat, NotifyType
from .email.base import NotifyEmail, PGPMode

# Longest excerpt of the message body placed in the outer Subject header
DELTACHAT_SUBJECT_EXCERPT_LEN = 50


class NotifyDeltaChat(NotifyEmail):
    """Send Delta Chat messages through Email's SMTP and PGP support."""

    # The default descriptive name associated with the Notification
    service_name = "Delta Chat"

    # The services URL
    service_url = "https://delta.chat/"

    # The default protocol
    protocol = "deltachat"

    # The default secure protocol
    secure_protocol = "deltachats"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/deltachat/"

    # Delta Chat clients render messages as plain text
    notify_format = NotifyFormat.TEXT

    # Delta Chat has no separate subject/title field in the chat bubble
    # itself, so let the framework merge the title into the body for us
    title_maxlen = 0

    @staticmethod
    def parse_url(url):
        """Parse an Email URL while always selecting plain text."""
        results = NotifyEmail.parse_url(url)
        if results:
            results["format"] = "text"

        return results

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        body_format=None,
        **kwargs,
    ):
        """Perform Delta Chat Notification."""

        # The framework has merged the title into the body. Build the chat
        # subject from that combined text.
        return super().send(
            body=body,
            title=self._chat_subject(body),
            notify_type=notify_type,
            attach=attach,
            body_format=body_format,
            **kwargs,
        )

    def _protocol_headers(self, body):
        """Return Delta Chat's protocol headers."""

        # Chat-Version is required by the spec on every outgoing message
        return {"Chat-Version": "1.0"}

    def _chat_subject(self, body):
        """Build a ``Chat:`` subject without exposing protected content."""

        if self.pgp_mode == PGPMode.ENCRYPT:
            # Delta Chat recommends this placeholder when encrypted metadata
            # is not carried with Memoryhole.
            return "Chat: Encrypted message"

        if self.pgp_mode == PGPMode.SIGN:
            return "Chat:"

        excerpt = " ".join(body.split())
        if len(excerpt) > DELTACHAT_SUBJECT_EXCERPT_LEN:
            excerpt = excerpt[:DELTACHAT_SUBJECT_EXCERPT_LEN] + "..."

        return f"Chat: {excerpt}" if excerpt else "Chat:"
