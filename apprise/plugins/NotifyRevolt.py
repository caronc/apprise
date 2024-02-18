# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

# Youll need your own Revolt Bot and a Channel Id for the notifications to
# be sent in since Revolt does not support webhooks yet.
#
#  This plugin will simply work using the url of:
#     revolt://BOT_TOKEN/CHANNEL_ID
#
# API Documentation:
#    - https://api.revolt.chat/swagger/index.html
#

import requests
from json import dumps, loads
from datetime import timedelta
from datetime import datetime
from datetime import timezone

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import validate_regex
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _


class NotifyRevolt(NotifyBase):
    """
    A wrapper for Revolt Notifications

    """
    # The default descriptive name associated with the Notification
    service_name = 'Revolt'

    # The services URL
    service_url = 'https://revolt.chat/'

    # The default secure protocol
    secure_protocol = 'revolt'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_revolt'

    # Revolt Channel Message
    notify_url = 'https://api.revolt.chat/'

    # Revolt supports attachments but doesn't support it here (for now)
    attachment_support = False

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # Revolt is kind enough to return how many more requests we're allowed to
    # continue to make within it's header response as:
    # X-RateLimit-Reset: The epoc time (in seconds) we can expect our
    #                    rate-limit to be reset.
    # X-RateLimit-Remaining: an integer identifying how many requests we're
    #                        still allow to make.
    request_rate_per_sec = 3

    # Safety net
    clock_skew = timedelta(seconds=2)

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 2000

    # Title Maximum Length
    title_maxlen = 100

    # Define object templates
    templates = (
        '{schema}://{bot_token}/{targets}',
    )

    # Defile out template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'bot_token': {
            'name': _('Bot Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_channel': {
            'name': _('Channel ID'),
            'type': 'string',
            'map_to': 'targets',
            'regex': (r'^[a-z0-9_-]+$', 'i'),
            'private': True,
            'required': True,
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'channel': {
            'alias_of': 'targets',
        },
        'bot_token': {
            'alias_of': 'bot_token',
        },
        'icon_url': {
            'name': _('Icon URL'),
            'type': 'string'
        },
        'url': {
            'name': _('Embed URL'),
            'type': 'string',
            'map_to': 'link',
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, bot_token, targets, icon_url=None, link=None,
                 **kwargs):
        super().__init__(**kwargs)

        # Bot Token
        self.bot_token = validate_regex(bot_token)
        if not self.bot_token:
            msg = 'An invalid Revolt Bot Token ' \
                '({}) was specified.'.format(bot_token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Parse our Channel IDs
        self.targets = []
        for target in parse_list(targets):
            results = validate_regex(
                target, *self.template_tokens['target_channel']['regex'])

            if not results:
                self.logger.warning(
                    'Dropped invalid Revolt channel ({}) specified.'
                    .format(target),
                )
                continue

            # Add our target
            self.targets.append(target)

        # Image for Embed
        self.icon_url = icon_url

        # Url for embed title
        self.link = link

        # For Tracking Purposes
        self.ratelimit_reset = datetime.now(timezone.utc).replace(tzinfo=None)

        # Default to 1.0
        self.ratelimit_remaining = 1.0

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Revolt Notification

        """

        if len(self.targets) == 0:
            self.logger.warning('There were not Revolt channels to notify.')
            return False

        payload = {}

        # Acquire image_url
        image_url = self.icon_url \
            if self.icon_url else self.image_url(notify_type)

        if self.notify_format == NotifyFormat.MARKDOWN:
            payload['embeds'] = [{
                'title': None if not title else title[0:self.title_maxlen],
                'description': body,

                # Our color associated with our notification
                'colour': self.color(notify_type),
                'replies': None
            }]

            if image_url:
                payload['embeds'][0]['icon_url'] = image_url

            if self.link:
                payload['embeds'][0]['url'] = self.link

        else:
            payload['content'] = \
                body if not title else "{}\n{}".format(title, body)

        has_error = False
        channel_ids = list(self.targets)
        for channel_id in channel_ids:
            postokay, response = self._send(payload, channel_id)
            if not postokay:
                # Failed to send message
                has_error = True

        return not has_error

    def _send(self, payload, channel_id, retries=1, **kwargs):
        """
        Wrapper to the requests (post) object

        """

        headers = {
            'User-Agent': self.app_id,
            'X-Bot-Token': self.bot_token,
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json; charset=utf-8',
        }

        notify_url = '{0}channels/{1}/messages'.format(
            self.notify_url,
            channel_id
        )

        self.logger.debug('Revolt POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate
        ))
        self.logger.debug('Revolt Payload: %s' % str(payload))

        # By default set wait to None
        wait = None

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if self.ratelimit_remaining <= 0.0:
            # Determine how long we should wait for or if we should wait at
            # all. This isn't fool-proof because we can't be sure the client
            # time (calling this script) is completely synced up with the
            # Discord server.  One would hope we're on NTP and our clocks are
            # the same allowing this to role smoothly:
            if now < self.ratelimit_reset:
                # We need to throttle for the difference in seconds
                wait = abs(
                    (self.ratelimit_reset - now + self.clock_skew)
                    .total_seconds())

        # Default content response object
        content = {}

        # Always call throttle before any remote server i/o is made;
        self.throttle(wait=wait)

        try:
            r = requests.post(
                notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout
            )

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

            # Handle rate limiting (if specified)
            try:
                # Store our rate limiting (if provided)
                self.ratelimit_remaining = \
                    int(r.headers.get('X-RateLimit-Remaining'))
                self.ratelimit_reset = \
                    now + timedelta(seconds=(int(
                        r.headers.get('X-RateLimit-Reset-After')) / 1000))

            except (TypeError, ValueError):
                # This is returned if we could not retrieve this
                # information gracefully accept this state and move on
                pass

            if r.status_code not in (
                    requests.codes.ok, requests.codes.no_content):

                # Some details to debug by
                self.logger.debug('Response Details:\r\n{}'.format(
                    content if content else r.content))

                # We had a problem
                status_str = \
                    NotifyBase.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Revolt request limit reached; '
                    'instructed to throttle for %.3fs',
                    abs((self.ratelimit_reset - now + self.clock_skew)
                        .total_seconds()))

                if r.status_code == requests.codes.too_many_requests \
                        and retries > 0:

                    # Try again
                    return self._send(
                        payload=payload, channel_id=channel_id,
                        retries=retries - 1, **kwargs)

                self.logger.warning(
                    'Failed to send to Revolt notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                # Return; we're done
                return (False, content)

            else:
                self.logger.info('Sent Revolt notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred posting to Revolt.')
            self.logger.debug('Socket Exception: %s' % str(e))
            return (False, content)

        return (True, content)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.

        """

        # Define any URL parameters
        params = {}

        if self.icon_url:
            params['icon_url'] = self.icon_url

        if self.link:
            params['url'] = self.link

        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{bot_token}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            bot_token=self.pprint(self.bot_token, privacy, safe=''),
            targets='/'.join(
                [self.pprint(x, privacy, safe='') for x in self.targets]),
            params=NotifyRevolt.urlencode(params),
        )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        return 1 if not self.targets else len(self.targets)

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Store our bot token
        bot_token = NotifyRevolt.unquote(results['host'])

        # Now fetch the Channel IDs
        targets = NotifyRevolt.split_path(results['fullpath'])

        results['bot_token'] = bot_token
        results['targets'] = targets

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyRevolt.parse_list(results['qsd']['to'])

        # Support channel id on the URL string (if specified)
        if 'channel' in results['qsd']:
            results['targets'] += \
                NotifyRevolt.parse_list(results['qsd']['channel'])

        # Support bot token on the URL string (if specified)
        if 'bot_token' in results['qsd']:
            results['bot_token'] = \
                NotifyRevolt.unquote(results['qsd']['bot_token'])

        if 'icon_url' in results['qsd']:
            results['icon_url'] = \
                NotifyRevolt.unquote(results['qsd']['icon_url'])

        if 'url' in results['qsd']:
            results['link'] = NotifyRevolt.unquote(results['qsd']['url'])

        if 'format' not in results['qsd'] and (
                'url' in results or 'icon_url' in results):
            # Markdown is implied
            results['format'] = NotifyFormat.MARKDOWN

        return results
