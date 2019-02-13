# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
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

# To use this plugin, you need to first generate a webhook.

# When you're complete, you will recieve a URL that looks something like this:
#                https://apprise.ryver.com/application/webhook/ckhrjW8w672m6HG
#                          ^                                        ^
#                          |                                        |
#  These are important <---^----------------------------------------^
#
import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyImageSize

# Token required as part of the API request
VALIDATE_TOKEN = re.compile(r'[A-Za-z0-9]{15}')

# Organization required as part of the API request
VALIDATE_ORG = re.compile(r'[A-Za-z0-9-]{3,32}')


class RyverWebhookType(object):
    """
    Ryver supports to webhook types
    """
    SLACK = 'slack'
    RYVER = 'ryver'


# Define the types in a list for validation purposes
RYVER_WEBHOOK_TYPES = (
    RyverWebhookType.SLACK,
    RyverWebhookType.RYVER,
)


class NotifyRyver(NotifyBase):
    """
    A wrapper for Ryver Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Ryver'

    # The services URL
    service_url = 'https://ryver.com/'

    # The default secure protocol
    secure_protocol = 'ryver'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_ryver'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    def __init__(self, organization, token, webhook=RyverWebhookType.RYVER,
                 **kwargs):
        """
        Initialize Ryver Object
        """
        super(NotifyRyver, self).__init__(**kwargs)

        if not VALIDATE_TOKEN.match(token.strip()):
            self.logger.warning(
                'The token specified (%s) is invalid.' % token,
            )
            raise TypeError(
                'The token specified (%s) is invalid.' % token,
            )

        if not VALIDATE_ORG.match(organization.strip()):
            self.logger.warning(
                'The organization specified (%s) is invalid.' % organization,
            )
            raise TypeError(
                'The organization specified (%s) is invalid.' % organization,
            )

        # Store our webhook type
        self.webhook = webhook

        if self.webhook not in RYVER_WEBHOOK_TYPES:
            self.logger.warning(
                'The webhook specified (%s) is invalid.' % webhook,
            )
            raise TypeError(
                'The webhook specified (%s) is invalid.' % webhook,
            )

        # The organization associated with the account
        self.organization = organization.strip()

        # The token associated with the account
        self.token = token.strip()

        # Slack formatting requirements are defined here which Ryver supports:
        # https://api.slack.com/docs/message-formatting
        self._re_formatting_map = {
            # New lines must become the string version
            r'\r\*\n': '\\n',
            # Escape other special characters
            r'&': '&amp;',
            r'<': '&lt;',
            r'>': '&gt;',
        }

        # Iterate over above list and store content accordingly
        self._re_formatting_rules = re.compile(
            r'(' + '|'.join(self._re_formatting_map.keys()) + r')',
            re.IGNORECASE,
        )

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Ryver Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        if self.webhook == RyverWebhookType.SLACK:
            # Perform Slack formatting
            title = self._re_formatting_rules.sub(  # pragma: no branch
                lambda x: self._re_formatting_map[x.group()], title,
            )
            body = self._re_formatting_rules.sub(  # pragma: no branch
                lambda x: self._re_formatting_map[x.group()], body,
            )

        url = 'https://%s.ryver.com/application/webhook/%s' % (
            self.organization,
            self.token,
        )

        # prepare JSON Object
        payload = {
            "body": body if not title else '**%s**\r\n%s' % (title, body),
            'createSource': {
                "displayName": self.user,
                "avatar": self.image_url(notify_type),
            },
        }

        self.logger.debug('Ryver POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Ryver Payload: %s' % str(payload))
        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to send Ryver:%s '
                        'notification: %s (error=%s).' % (
                            self.organization,
                            HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to send Ryver:%s '
                        'notification (error=%s).' % (
                            self.organization,
                            r.status_code))

                # self.logger.debug('Response Details: %s' % r.raw.read())

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Ryver notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Ryver:%s ' % (
                    self.organization) + 'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        return True

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'webhook': self.webhook,
        }

        # Determine if there is a botname present
        botname = ''
        if self.user:
            botname = '{botname}@'.format(
                botname=self.quote(self.user, safe=''),
            )

        return '{schema}://{botname}{organization}/{token}/?{args}'.format(
            schema=self.secure_protocol,
            botname=botname,
            organization=self.quote(self.organization, safe=''),
            token=self.quote(self.token, safe=''),
            args=self.urlencode(args),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Apply our settings now

        # The first token is stored in the hostname
        organization = results['host']

        # Now fetch the remaining tokens
        try:
            token = [x for x in filter(
                bool, NotifyBase.split_path(results['fullpath']))][0]

        except (ValueError, AttributeError, IndexError):
            # We're done
            return None

        if 'webhook' in results['qsd'] and len(results['qsd']['webhook']):
            results['webhook'] = results['qsd']\
                .get('webhook', RyverWebhookType.RYVER).lower()

        results['organization'] = organization
        results['token'] = token

        return results
