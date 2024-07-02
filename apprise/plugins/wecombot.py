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

# WeCom for PC
#   1. On WeCom for PC, find the target WeCom group for receiving alarm
#        notifications.
#   2. Right-click the WeCom group. In the window that appears, click
#        "Add Group Bot".
#   3. In the window that appears, click Create a Bot.
#   4. In the window that appears, enter a custom bot name and click Add.
#   5. You will be provided a Webhook URL that looks like:
#          https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abcd
#
# WeCom for Web
#   1. On WebCom for Web, open the target WeCom group for receiving alarm
#        notifications.
#   2. Click the group settings icon in the upper-right corner.
#   3. On the group settings page, choose Group Bots > Add a Bot.
#   4. On the management page for adding bots, enter a custom name for the new
#        bot.
#   5. Click Add, copy the webhook address, and configure the API callback by
#        following Step 2.

# the URL will look something like this:
#       https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abcd
#                                                             ^
#                                                             |
#                                                     webhook key
#
# This plugin also supports taking the URL (as identified above) directly
# as well.

import re
import requests
from json import dumps

from .base import NotifyBase
from ..common import NotifyType
from ..utils import validate_regex
from ..locale import gettext_lazy as _


class NotifyWeComBot(NotifyBase):
    """
    A wrapper for WeCom Bot Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'WeCom Bot'

    # The services URL
    service_url = 'https://weixin.qq.com/'

    # The default secure protocol
    secure_protocol = 'wecombot'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_wecombot'

    # Plain Text Notification URL
    notify_url = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}'

    # Define object templates
    templates = (
        '{schema}://{key}',
    )

    # The title is not used
    title_maxlen = 0

    # Define our template arguments
    template_tokens = dict(NotifyBase.template_tokens, **{
        # The Bot Key can be found at the end of the webhook provided (?key=)
        'key': {
            'name': _('Bot Webhook Key'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[a-z0-9_-]+$', 'i'),
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        # You can optionally pass IRC colors into
        'key': {
            'alias_of': 'key',
        },
    })

    def __init__(self, key, **kwargs):
        """
        Initialize WeCom Bot Object
        """
        super().__init__(**kwargs)

        # Assign our bot webhook
        self.key = validate_regex(
            key, *self.template_tokens['key']['regex'])
        if not self.key:
            msg = 'An invalid WeCom Bot Webhook Key ' \
                  '({}) was specified.'.format(key)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Prepare our notification URL now:
        self.api_url = self.notify_url.format(
            key=self.key,
        )
        return

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.key)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Prepare our parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return '{schema}://{key}/?{params}'.format(
            schema=self.secure_protocol,
            key=self.pprint(self.key, privacy, safe=''),
            params=NotifyWeComBot.urlencode(params),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        wrapper to _send since we can alert more then one channel
        """

        # prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json; charset=utf-8',
        }

        # Prepare our payload
        payload = {
            'msgtype': "text",
            'text': {
                'content': body,
            }
        }

        self.logger.debug('WeCom Bot GET URL: %s (cert_verify=%r)' % (
            self.api_url, self.verify_certificate))
        self.logger.debug('WeCom Bot Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.api_url,
                data=dumps(payload).encode('utf-8'),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyWeComBot.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send WeCom Bot notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent WeCom Bot notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending WeCom Bot '
                'notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

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

        # The first token is stored in the hostname
        results['key'] = NotifyWeComBot.unquote(results['host'])

        # The 'key' makes it easier to use yaml configuration
        if 'key' in results['qsd'] and len(results['qsd']['key']):
            results['key'] = \
                NotifyWeComBot.unquote(results['qsd']['key'])

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=BOTKEY
        """

        result = re.match(
            r'^https?://qyapi\.weixin\.qq\.com/cgi-bin/webhook/send/?\?key='
            r'(?P<key>[A-Z0-9_-]+)/?'
            r'&?(?P<params>.+)?$', url, re.I)

        if result:
            return NotifyWeComBot.parse_url(
                '{schema}://{key}{params}'.format(
                    schema=NotifyWeComBot.secure_protocol,
                    key=result.group('key'),
                    params='' if not result.group('params')
                    else '?' + result.group('params')))

        return None
