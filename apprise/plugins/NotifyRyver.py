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
import six
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType
from ..utils import parse_bool

# Token required as part of the API request
VALIDATE_TOKEN = re.compile(r'[A-Za-z0-9]{15}')

# Organization required as part of the API request
VALIDATE_ORG = re.compile(r'[A-Za-z0-9-]{3,32}')


class RyverWebhookMode(object):
    """
    Ryver supports to webhook modes
    """
    SLACK = 'slack'
    RYVER = 'ryver'


# Define the types in a list for validation purposes
RYVER_WEBHOOK_MODES = (
    RyverWebhookMode.SLACK,
    RyverWebhookMode.RYVER,
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

    def __init__(self, organization, token, mode=RyverWebhookMode.RYVER,
                 include_image=True, **kwargs):
        """
        Initialize Ryver Object
        """
        super(NotifyRyver, self).__init__(**kwargs)

        if not token:
            msg = 'No Ryver token was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not organization:
            msg = 'No Ryver organization was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not VALIDATE_TOKEN.match(token.strip()):
            msg = 'The Ryver token specified ({}) is invalid.'\
                .format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        if not VALIDATE_ORG.match(organization.strip()):
            msg = 'The Ryver organization specified ({}) is invalid.'\
                .format(organization)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our webhook mode
        self.mode = None \
            if not isinstance(mode, six.string_types) else mode.lower()

        if self.mode not in RYVER_WEBHOOK_MODES:
            msg = 'The Ryver webhook mode specified ({}) is invalid.' \
                .format(mode)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The organization associated with the account
        self.organization = organization.strip()

        # The token associated with the account
        self.token = token.strip()

        # Place an image inline with the message body
        self.include_image = include_image

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

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Ryver Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        if self.mode == RyverWebhookMode.SLACK:
            # Perform Slack formatting
            title = self._re_formatting_rules.sub(  # pragma: no branch
                lambda x: self._re_formatting_map[x.group()], title,
            )
            body = self._re_formatting_rules.sub(  # pragma: no branch
                lambda x: self._re_formatting_map[x.group()], body,
            )

        url = 'https://{}.ryver.com/application/webhook/{}'.format(
            self.organization,
            self.token,
        )

        # prepare JSON Object
        payload = {
            'body': body if not title else '**{}**\r\n{}'.format(title, body),
            'createSource': {
                'displayName': self.user,
                'avatar': None,
            },
        }

        # Acquire our image url if configured to do so
        image_url = None if not self.include_image else \
            self.image_url(notify_type)

        if image_url:
            payload['createSource']['avatar'] = image_url

        self.logger.debug('Ryver POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Ryver Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyBase.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Ryver notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

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
            'overflow': self.overflow_mode,
            'image': 'yes' if self.include_image else 'no',
            'mode': self.mode,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        # Determine if there is a botname present
        botname = ''
        if self.user:
            botname = '{botname}@'.format(
                botname=NotifyRyver.quote(self.user, safe=''),
            )

        return '{schema}://{botname}{organization}/{token}/?{args}'.format(
            schema=self.secure_protocol,
            botname=botname,
            organization=NotifyRyver.quote(self.organization, safe=''),
            token=NotifyRyver.quote(self.token, safe=''),
            args=NotifyRyver.urlencode(args),
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

        # The first token is stored in the hostname
        results['organization'] = NotifyRyver.unquote(results['host'])

        # Now fetch the remaining tokens
        try:
            results['token'] = \
                NotifyRyver.split_path(results['fullpath'])[0]

        except IndexError:
            # no token
            results['token'] = None

        if 'webhook' in results['qsd']:
            # Deprication Notice issued for v0.7.5
            NotifyRyver.logger.deprecate(
                'The Ryver URL contains the parameter '
                '"webhook=" which will be deprecated in an upcoming '
                'release. Please use "mode=" instead.'
            )

        # use mode= for consistency with the other plugins but we also
        # support webhook= for backwards compatibility.
        results['mode'] = results['qsd'].get(
            'mode', results['qsd'].get(
                'webhook', RyverWebhookMode.RYVER))

        # use image= for consistency with the other plugins
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        return results
