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
from json import dumps
from datetime import timedelta
from datetime import datetime
from datetime import timezone

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_bool
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class NotifyRevolt(NotifyBase):
    """
    A wrapper for Revolt Notifications

    """
    # The default descriptive name associated with the Notification
    service_name = 'Revolt'

    # The services URL
    service_url = 'https://api.revolt.chat/'

    # The default secure protocol
    secure_protocol = 'revolt'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_revolt'

    # Revolt Channel Message
    notify_url = 'https://api.revolt.chat/'

    # Revolt supports attachments but don't implemenet for now
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

    # Taken right from google.auth.helpers:
    clock_skew = timedelta(seconds=10)

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 2000

    # The 2000 characters above defined by the body_maxlen include that of the
    # title.  Setting this to True ensures overflow options behave properly
    overflow_amalgamate_title = True

    # Define object templates
    templates = (
        '{schema}://{bot_token}/{channel_id}',
    )

    # Defile out template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'bot_token': {
            'name': _('Bot Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'channel_id': {
            'name': _('Channel Id'),
            'type': 'string',
            'private': True,
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'channel_id': {
            'alias_of': 'channel_id',
        },
        'bot_token': {
            'alias_of': 'bot_token',
        },
        'embed_img': {
            'name': _('Embed Image Url'),
            'type': 'string'
        },
        'embed_url': {
            'name': _('Embed Url'),
            'type': 'string'
        },
        'custom_img': {
            'name': _('Custom Embed Url'),
            'type': 'bool',
            'default': False
        }
    })

    def __init__(self, bot_token, channel_id, embed_img=None, embed_url=None,
                 custom_img=None, **kwargs):
        super().__init__(**kwargs)

        # Bot Token
        self.bot_token = validate_regex(bot_token)
        if not self.bot_token:
            msg = 'An invalid Revolt Bot Token ' \
                '({}) was specified.'.format(bot_token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Channel Id
        self.channel_id = validate_regex(channel_id)
        if not self.channel_id:
            msg = 'An invalid Revolt Channel Id' \
                '({}) was specified.'.format(channel_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Use custom image for embed image
        self.custom_img = parse_bool(custom_img) \
            if custom_img is not None \
            else self.template_args['custom_img']['default']

        # Image for Embed
        self.embed_img = embed_img

        # Url for embed title
        self.embed_url = embed_url

        # For Tracking Purposes
        self.ratelimit_reset = datetime.now(timezone.utc).replace(tzinfo=None)

        # Default to 1.0
        self.ratelimit_remaining = 1.0

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Revolt Notification

        """

        payload = {}

        # Acquire image_url
        image_url = self.image_url(notify_type)

        if self.custom_img and (image_url or self.embed_url):
            image_url = self.embed_url if self.embed_url else image_url

        if body:
            if self.notify_format == NotifyFormat.MARKDOWN:
                if len(title) > 100:
                    msg = 'Title length must be less than 100 when ' \
                        'embeds are enabled (is %s)' % len(title)
                    self.logger.warning(msg)
                    title = title[0:100]
                payload['embeds'] = [{
                    'title': title,
                    'description': body,

                    # Our color associated with our notification
                    'colour': self.color(notify_type, int)
                }]

                if self.embed_img:
                    payload['embeds'][0]['icon_url'] = image_url

                if self.embed_url:
                    payload['embeds'][0]['url'] = self.embed_url
            else:
                payload['content'] = \
                    body if not title else "{}\n{}".format(title, body)

            if not self._send(payload):
                # Failed to send message
                return False
        return True

    def _send(self, payload, rate_limit=1, **kwargs):
        """
        Wrapper to the requests (post) object

        """

        headers = {
            'User-Agent': self.app_id,
            'X-Bot-Token': self.bot_token,
            'Content-Type': 'application/json; charset=utf-8'
        }

        notify_url = '{0}/channels/{1}/send'.format(
            self.notify_url,
            self.channel_id
        )

        self.logger.debug('Revolt POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate
        ))
        self.logger.debug('Revolt Payload: %s' % str(payload))

        # By default set wait to None
        wait = None

        if self.ratelimit_remaining <= 0.0:
            # Determine how long we should wait for or if we should wait at
            # all. This isn't fool-proof because we can't be sure the client
            # time (calling this script) is completely synced up with the
            # Discord server.  One would hope we're on NTP and our clocks are
            # the same allowing this to role smoothly:

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if now < self.ratelimit_reset:
                # We need to throttle for the difference in seconds
                wait = abs(
                    (self.ratelimit_reset - now + self.clock_skew)
                    .total_seconds())

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

            # Handle rate limiting (if specified)
            try:
                # Store our rate limiting (if provided)
                self.ratelimit_remaining = \
                    float(r.headers.get(
                        'X-RateLimit-Remaining'))
                self.ratelimit_reset = datetime.fromtimestamp(
                    int(r.headers.get('X-RateLimit-Reset')),
                    timezone.utc).replace(tzinfo=None)

            except (TypeError, ValueError):
                # This is returned if we could not retrieve this
                # information gracefully accept this state and move on
                pass

            if r.status_code not in (
                    requests.codes.ok, requests.codes.no_content):

                # We had a problem
                status_str = \
                    NotifyBase.http_response_code_lookup(r.status_code)

                if r.status_code == requests.codes.too_many_requests \
                        and rate_limit > 0:

                    # handle rate limiting
                    self.logger.warning(
                        'Revolt rate limiting in effect; '
                        'blocking for %.2f second(s)',
                        self.ratelimit_remaining)

                    # Try one more time before failing
                    return self._send(
                        payload=payload,
                        rate_limit=rate_limit - 1, **kwargs)

                self.logger.warning(
                    'Failed to send to Revolt notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Revolt notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred posting to Revolt.')
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.

        """

        params = {}

        if self.embed_img:
            params['embed_img'] = self.embed_img

        if self.embed_url:
            params['embed_url'] = self.embed_url

        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{bot_token}/{channel_id}/?{params}'.format(
            schema=self.secure_protocol,
            bot_token=self.pprint(self.bot_token, privacy, safe=''),
            channel_id=self.pprint(self.channel_id, privacy, safe=''),
            params=NotifyRevolt.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        Syntax:
          revolt://bot_token/channel_id

        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Store our bot token
        bot_token = NotifyRevolt.unquote(results['host'])

        # Now fetch the channel id
        try:
            channel_id = \
                NotifyRevolt.split_path(results['fullpath'])[0]

        except IndexError:
            # Force some bad values that will get caught
            # in parsing later
            channel_id = None

        results['bot_token'] = bot_token
        results['channel_id'] = channel_id

        # Text To Speech
        results['tts'] = parse_bool(results['qsd'].get('tts', False))

        # Support channel id on the URL string (if specified)
        if 'channel_id' in results['qsd']:
            results['channel_id'] = \
                NotifyRevolt.unquote(results['qsd']['channel_id'])

        # Support bot token on the URL string (if specified)
        if 'bot_token' in results['qsd']:
            results['bot_token'] = \
                NotifyRevolt.unquote(results['qsd']['bot_token'])

        # Extract avatar url if it was specified
        if 'embed_img' in results['qsd']:
            results['embed_img'] = \
                NotifyRevolt.unquote(results['qsd']['embed_img'])

        if 'custom_img' in results['qsd']:
            results['custom_img'] = \
                NotifyRevolt.unquote(results['qsd']['custom_img'])

        elif 'embed_url' in results['qsd']:
            results['embed_url'] = \
                NotifyRevolt.unquote(results['qsd']['embed_url'])
            # Markdown is implied
            results['format'] = NotifyFormat.MARKDOWN

        return results
