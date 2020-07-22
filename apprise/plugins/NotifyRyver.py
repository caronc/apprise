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
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


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

    # Define object templates
    templates = (
        '{schema}://{organization}/{token}',
        '{schema}://{user}@{organization}/{token}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'organization': {
            'name': _('Organization'),
            'type': 'string',
            'required': True,
            'regex': (r'^[A-Z0-9_-]{3,32}$', 'i'),
        },
        'token': {
            'name': _('Token'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[A-Z0-9]{15}$', 'i'),
        },
        'user': {
            'name': _('Bot Name'),
            'type': 'string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'mode': {
            'name': _('Webhook Mode'),
            'type': 'choice:string',
            'values': RYVER_WEBHOOK_MODES,
            'default': RyverWebhookMode.RYVER,
        },
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
    })

    def __init__(self, organization, token, mode=RyverWebhookMode.RYVER,
                 include_image=True, **kwargs):
        """
        Initialize Ryver Object
        """
        super(NotifyRyver, self).__init__(**kwargs)

        # API Token (associated with project)
        self.token = validate_regex(
            token, *self.template_tokens['token']['regex'])
        if not self.token:
            msg = 'An invalid Ryver API Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Organization (associated with project)
        self.organization = validate_regex(
            organization, *self.template_tokens['organization']['regex'])
        if not self.organization:
            msg = 'An invalid Ryver Organization ' \
                  '({}) was specified.'.format(organization)
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

        return

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
                timeout=self.request_timeout,
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
                'A Connection error occurred sending Ryver:%s ' % (
                    self.organization) + 'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
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
            token=self.pprint(self.token, privacy, safe=''),
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

    @staticmethod
    def parse_native_url(url):
        """
        Support https://RYVER_ORG.ryver.com/application/webhook/TOKEN
        """

        result = re.match(
            r'^https?://(?P<org>[A-Z0-9_-]+)\.ryver\.com/application/webhook/'
            r'(?P<webhook_token>[A-Z0-9]+)/?'
            r'(?P<args>\?.+)?$', url, re.I)

        if result:
            return NotifyRyver.parse_url(
                '{schema}://{org}/{webhook_token}/{args}'.format(
                    schema=NotifyRyver.secure_protocol,
                    org=result.group('org'),
                    webhook_token=result.group('webhook_token'),
                    args='' if not result.group('args')
                    else result.group('args')))

        return None
