# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

# To use this service you will need a Clickatell account to which you can get your
# API_TOKEN at:
#     https://www.clickatell.com/
import requests

from .base import NotifyBase
from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import validate_regex, parse_phone_no


class NotifyClickatell(NotifyBase):
    """
    A wrapper for Clickatell Notifications
    """

    service_name = _('Clickatell')
    service_url = 'https://www.clickatell.com/'
    secure_protocol = 'clickatell'
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_clickatell'
    notify_url = 'https://platform.clickatell.com/messages/http/send?apiKey={}'

    templates = (
        '{schema}://{api_token}/{targets}',
        '{schema}://{api_token}@{from_phone}/{targets}',
    )

    template_tokens = dict(NotifyBase.template_tokens, **{
        'api_token': {
            'name': _('API Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'from_phone': {
            'name': _('From Phone No'),
            'type': 'string',
            'regex': (r'^[0-9\s)(+-]+$', 'i'),
        },
        'target_phone': {
            'name': _('Target Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'^[0-9\s)(+-]+$', 'i'),
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
            'required': True,
        },
    })

    template_args = dict(NotifyBase.template_args, **{
        'token': {
            'alias_of': 'api_token'
        },
        'to': {
            'alias_of': 'targets',
        },
        'from': {
            'alias_of': 'from_phone',
        },
    })

    def __init__(self, api_token, from_phone, targets=None, **kwargs):
        """
        Initialize Clickatell Object
        """

        super().__init__(**kwargs)

        self.api_token = validate_regex(api_token)
        if not self.api_token:
            msg = 'An invalid Clickatell API Token ' \
                  '({}) was specified.'.format(api_token)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.from_phone = validate_regex(from_phone)
        self.targets = parse_phone_no(targets, prefix=True)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return '{schema}://{apikey}/?{params}'.format(
            schema=self.secure_protocol,
            apikey=self.quote(self.api_token, safe='/'),
            params=self.urlencode(params),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Clickatell Notification
        """

        if not self.targets:
            self.logger.warning('There are no valid targets to notify.')
            return False

        headers = {
            'User-Agent': self.app_id,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        url = self.notify_url.format(self.api_token)
        if self.from_phone:
            url += '&from={}'.format(self.from_phone)
        url += '&to={}'.format(','.join(self.targets))
        url += '&content={}'.format(' '.join([title, body]))

        self.logger.debug('Clickatell GET URL: %s', url)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.get(
                url,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok \
                    and r.status_code != requests.codes.accepted:
                # We had a problem
                status_str = self.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Clickatell notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))
                return False
            else:
                self.logger.info('Sent Clickatell notification.')
        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Clickatell '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))
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
            # We're done early as we couldn't parse the URL
            return results

        results['targets'] = NotifyClickatell.split_path(results['fullpath'])

        if not results['targets']:
            return results

        if results['user']:
            results['api_token'] = NotifyClickatell.unquote(results['user'])
            results['from_phone'] = NotifyClickatell.unquote(results['host'])
        else:
            results['api_token'] = NotifyClickatell.unquote(results['host'])
            results['from_phone'] = ''

        return results
