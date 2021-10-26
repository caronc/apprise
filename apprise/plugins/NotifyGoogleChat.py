# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# For this to work correctly you need to create a webhook. You'll also
# need a GSuite account (there are free trials if you don't have one)
#
#  - Open Google Chat in your browser:
#     Link: https://chat.google.com/
#  - Go to the room to which you want to add a bot.
#  - From the room menu at the top of the page, select Manage webhooks.
#  - Provide it a name and optional avatar and click SAVE
#  - Copy the URL listed next to your new webhook in the Webhook URL column.
#  - Click outside the dialog box to close.
#
# When you've completed, you'll get a URL that looks a little like this:
#  https://chat.googleapis.com/v1/spaces/AAAAk6lGXyM/\
#       messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&\
#       token=O7b1nyri_waOpLMSzbFILAGRzgtQofPW71fEEXKcyFk%3D
#
# Simplified, it looks like this:
#     https://chat.googleapis.com/v1/spaces/WORKSPACE/messages?\
#       key=WEBHOOK_KEY&token=WEBHOOK_TOKEN
#
# This plugin will simply work using the url of:
#     gchat://WORKSPACE/WEBHOOK_KEY/WEBHOOK_TOKEN
#
# API Documentation on Webhooks:
#    - https://developers.google.com/hangouts/chat/quickstart/\
#         incoming-bot-python
#    - https://developers.google.com/hangouts/chat/reference/rest
#
import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class NotifyGoogleChat(NotifyBase):
    """
    A wrapper to Google Chat Notifications

    """
    # The default descriptive name associated with the Notification
    service_name = 'Google Chat'

    # The services URL
    service_url = 'https://chat.google.com/'

    # The default secure protocol
    secure_protocol = 'gchat'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_googlechat'

    # Google Chat Webhook
    notify_url = 'https://chat.googleapis.com/v1/spaces/{workspace}/messages' \
                 '?key={key}&token={token}'

    # Default Notify Format
    notify_format = NotifyFormat.MARKDOWN

    # A title can not be used for Google Chat Messages.  Setting this to zero
    # will cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 4000

    # Define object templates
    templates = (
        '{schema}://{workspace}/{webhook_key}/{webhook_token}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'workspace': {
            'name': _('Workspace'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'webhook_key': {
            'name': _('Webhook Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'webhook_token': {
            'name': _('Webhook Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'workspace': {
            'alias_of': 'workspace',
        },
        'key': {
            'alias_of': 'webhook_key',
        },
        'token': {
            'alias_of': 'webhook_token',
        },
    })

    def __init__(self, workspace, webhook_key, webhook_token, **kwargs):
        """
        Initialize Google Chat Object

        """
        super(NotifyGoogleChat, self).__init__(**kwargs)

        # Workspace (associated with project)
        self.workspace = validate_regex(workspace)
        if not self.workspace:
            msg = 'An invalid Google Chat Workspace ' \
                  '({}) was specified.'.format(workspace)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Webhook Key (associated with project)
        self.webhook_key = validate_regex(webhook_key)
        if not self.webhook_key:
            msg = 'An invalid Google Chat Webhook Key ' \
                  '({}) was specified.'.format(webhook_key)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Webhook Token (associated with project)
        self.webhook_token = validate_regex(webhook_token)
        if not self.webhook_token:
            msg = 'An invalid Google Chat Webhook Token ' \
                  '({}) was specified.'.format(webhook_token)
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Google Chat Notification
        """

        # Our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json; charset=utf-8',
        }

        payload = {
            # Our Message
            'text': body,
        }

        # Construct Notify URL
        notify_url = self.notify_url.format(
            workspace=self.workspace,
            key=self.webhook_key,
            token=self.webhook_token,
        )

        self.logger.debug('Google Chat POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('Google Chat Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code not in (
                    requests.codes.ok, requests.codes.no_content):

                # We had a problem
                status_str = \
                    NotifyBase.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Google Chat notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Google Chat notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred postingto Google Chat.')
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Set our parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return '{schema}://{workspace}/{key}/{token}/?{params}'.format(
            schema=self.secure_protocol,
            workspace=self.pprint(self.workspace, privacy, safe=''),
            key=self.pprint(self.webhook_key, privacy, safe=''),
            token=self.pprint(self.webhook_token, privacy, safe=''),
            params=NotifyGoogleChat.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        Syntax:
          gchat://workspace/webhook_key/webhook_token

        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Store our Workspace
        results['workspace'] = NotifyGoogleChat.unquote(results['host'])

        # Acquire our tokens
        tokens = NotifyGoogleChat.split_path(results['fullpath'])

        # Store our Webhook Key
        results['webhook_key'] = tokens.pop(0) if tokens else None

        # Store our Webhook Token
        results['webhook_token'] = tokens.pop(0) if tokens else None

        # Support arguments as overrides (if specified)
        if 'workspace' in results['qsd']:
            results['workspace'] = \
                NotifyGoogleChat.unquote(results['qsd']['workspace'])

        if 'key' in results['qsd']:
            results['webhook_key'] = \
                NotifyGoogleChat.unquote(results['qsd']['key'])

        if 'token' in results['qsd']:
            results['webhook_token'] = \
                NotifyGoogleChat.unquote(results['qsd']['token'])

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support
           https://chat.googleapis.com/v1/spaces/{workspace}/messages
                 '?key={key}&token={token}
        """

        result = re.match(
            r'^https://chat\.googleapis\.com/v1/spaces/'
            r'(?P<workspace>[A-Z0-9_-]+)/messages/*(?P<params>.+)$',
            url, re.I)

        if result:
            return NotifyGoogleChat.parse_url(
                '{schema}://{workspace}/{params}'.format(
                    schema=NotifyGoogleChat.secure_protocol,
                    workspace=result.group('workspace'),
                    params=result.group('params')))

        return None
