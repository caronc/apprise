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

# To use this plugin, you need to create a webhook; you can read more about
# this here:
#    https://dev.outlook.com/Connectors/\
#       GetStarted#creating-messages-through-office-365-connectors-\
#           in-microsoft-teams
#
# More details are here on API Construction:
#    https://docs.microsoft.com/en-ca/outlook/actionable-messages/\
#        message-card-reference
#
# I personally created a free account at teams.microsoft.com and then
# went to the store (bottom left hand side of slack like interface).
#
# From here you can search for 'Incoming Webhook'. Once you click on it,
# you can associate the webhook with your team. At this point, you can
# optionally also assign it a name, an avatar.  Finally you'll have to
# assign it a channel it will notify.
#
# When you've completed this, it will generate you a (webhook) URL that
# looks like:
#   https://outlook.office.com/webhook/ \
#       abcdefgf8-2f4b-4eca-8f61-225c83db1967@abcdefg2-5a99-4849-8efc-\
#        c9e78d28e57d/IncomingWebhook/291289f63a8abd3593e834af4d79f9fe/\
#          a2329f43-0ffb-46ab-948b-c9abdad9d643
#
# Yes... The URL is that big... But it looks like this (greatly simplified):
# https://outlook.office.com/webhook/ABCD/IncomingWebhook/DEFG/HIJK
#                                     ^                    ^    ^
#                                     |                    |    |
#  These are important <--------------^--------------------^----^
#
# You'll notice that the first token is actually 2 separated by an @ symbol
# But lets just ignore that and assume it's one great big token instead.
#
# These 3 tokens is what you'll need to build your URL with:
#   msteams://ABCD/DEFG/HIJK
#
import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType
from ..common import NotifyFormat
from ..utils import parse_bool
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# Used to prepare our UUID regex matching
UUID4_RE = \
    r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'


class NotifyMSTeams(NotifyBase):
    """
    A wrapper for Microsoft Teams Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'MSTeams'

    # The services URL
    service_url = 'https://teams.micrsoft.com/'

    # The default secure protocol
    secure_protocol = 'msteams'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_msteams'

    # MSTeams uses the http protocol with JSON requests
    notify_url = 'https://outlook.office.com/webhook'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    # Default Notification Format
    notify_format = NotifyFormat.MARKDOWN

    # Define object templates
    templates = (
        '{schema}://{token_a}/{token_b}{token_c}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        # Token required as part of the API request
        #  /AAAAAAAAA@AAAAAAAAA/........./.........
        'token_a': {
            'name': _('Token A'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^{}@{}$'.format(UUID4_RE, UUID4_RE), 'i'),
        },
        # Token required as part of the API request
        #  /................../BBBBBBBBB/..........
        'token_b': {
            'name': _('Token B'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[A-Za-z0-9]{32}$', 'i'),
        },
        # Token required as part of the API request
        #  /........./........./CCCCCCCCCCCCCCCCCCCCCCCC
        'token_c': {
            'name': _('Token C'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^{}$'.format(UUID4_RE), 'i'),
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': False,
            'map_to': 'include_image',
        },
    })

    def __init__(self, token_a, token_b, token_c, include_image=True,
                 **kwargs):
        """
        Initialize Microsoft Teams Object
        """
        super(NotifyMSTeams, self).__init__(**kwargs)

        self.token_a = validate_regex(
            token_a, *self.template_tokens['token_a']['regex'])
        if not self.token_a:
            msg = 'An invalid MSTeams (first) Token ' \
                  '({}) was specified.'.format(token_a)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.token_b = validate_regex(
            token_b, *self.template_tokens['token_b']['regex'])
        if not self.token_b:
            msg = 'An invalid MSTeams (second) Token ' \
                  '({}) was specified.'.format(token_b)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.token_c = validate_regex(
            token_c, *self.template_tokens['token_c']['regex'])
        if not self.token_c:
            msg = 'An invalid MSTeams (third) Token ' \
                  '({}) was specified.'.format(token_c)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Place a thumbnail image inline with the message body
        self.include_image = include_image

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Microsoft Teams Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        url = '%s/%s/IncomingWebhook/%s/%s' % (
            self.notify_url,
            self.token_a,
            self.token_b,
            self.token_c,
        )

        # Prepare our payload
        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": self.app_desc,
            "themeColor": self.color(notify_type),
            "sections": [
                {
                    "activityImage": None,
                    "activityTitle": title,
                    "text": body,
                },
            ]
        }

        # Acquire our to-be footer icon if configured to do so
        image_url = None if not self.include_image \
            else self.image_url(notify_type)

        if image_url:
            payload['sections'][0]['activityImage'] = image_url

        self.logger.debug('MSTeams POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('MSTeams Payload: %s' % str(payload))

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
                    NotifyMSTeams.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send MSTeams notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # We failed
                return False

            else:
                self.logger.info('Sent MSTeams notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending MSTeams notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # We failed
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{token_a}/{token_b}/{token_c}/'\
            '?{params}'.format(
                schema=self.secure_protocol,
                token_a=self.pprint(self.token_a, privacy, safe=''),
                token_b=self.pprint(self.token_b, privacy, safe=''),
                token_c=self.pprint(self.token_c, privacy, safe=''),
                params=NotifyMSTeams.urlencode(params),
            )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Get unquoted entries
        entries = NotifyMSTeams.split_path(results['fullpath'])

        if results.get('user'):
            # If a user was found, it's because it's still part of the first
            # token, so we concatinate them
            results['token_a'] = '{}@{}'.format(
                NotifyMSTeams.unquote(results['user']),
                NotifyMSTeams.unquote(results['host']),
            )

        else:
            # The first token is stored in the hostname
            results['token_a'] = NotifyMSTeams.unquote(results['host'])

        # Now fetch the remaining tokens
        try:
            results['token_b'] = entries.pop(0)

        except IndexError:
            # We're done
            results['token_b'] = None

        try:
            results['token_c'] = entries.pop(0)

        except IndexError:
            # We're done
            results['token_c'] = None

        # Get Image
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support:
            https://outlook.office.com/webhook/ABCD/IncomingWebhook/DEFG/HIJK
        """

        # We don't need to do incredibly details token matching as the purpose
        # of this is just to detect that were dealing with an msteams url
        # token parsing will occur once we initialize the function
        result = re.match(
            r'^https?://outlook\.office\.com/webhook/'
            r'(?P<token_a>[A-Z0-9-]+@[A-Z0-9-]+)/'
            r'IncomingWebhook/'
            r'(?P<token_b>[A-Z0-9]+)/'
            r'(?P<token_c>[A-Z0-9-]+)/?'
            r'(?P<params>\?.+)?$', url, re.I)

        if result:
            return NotifyMSTeams.parse_url(
                '{schema}://{token_a}/{token_b}/{token_c}/{params}'.format(
                    schema=NotifyMSTeams.secure_protocol,
                    token_a=result.group('token_a'),
                    token_b=result.group('token_b'),
                    token_c=result.group('token_c'),
                    params='' if not result.group('params')
                    else result.group('params')))

        return None
