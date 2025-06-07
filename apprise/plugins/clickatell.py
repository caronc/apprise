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

# To use this service you will need a Clickatell account to which you can get
# your API_TOKEN at:
#     https://www.clickatell.com/
import requests
from itertools import chain
from .base import NotifyBase
from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import is_phone_no, validate_regex, parse_phone_no


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
        '{schema}://{apikey}/{targets}',
        '{schema}://{source}@{apikey}/{targets}',
    )

    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'source': {
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
        'apikey': {
            'alias_of': 'apikey'
        },
        'to': {
            'alias_of': 'targets',
        },
        'from': {
            'alias_of': 'source',
        },
    })

    def __init__(self, apikey, source=None, targets=None, **kwargs):
        """
        Initialize Clickatell Object
        """

        super().__init__(**kwargs)

        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = 'An invalid Clickatell API Token ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.source = None
        if source:
            result = is_phone_no(source)
            if not result:
                msg = 'The Account (From) Phone # specified ' \
                      '({}) is invalid.'.format(source)
                self.logger.warning(msg)

                raise TypeError(msg)

            # Tidy source
            self.source = result['full']

        # Used for URL generation afterwards only
        self._invalid_targets = list()

        # Parse our targets
        self.targets = list()

        for target in parse_phone_no(targets, prefix=True):
            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    'Dropped invalid phone # '
                    '({}) specified.'.format(target),
                )
                self._invalid_targets.append(target)
                continue

            # store valid phone number
            self.targets.append(result['full'])

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.apikey, self.source)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return '{schema}://{source}{apikey}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            source='{}@'.format(self.source) if self.source else '',
            apikey=self.pprint(self.apikey, privacy, safe='='),
            targets='/'.join(
                [NotifyClickatell.quote(t, safe='')
                 for t in chain(self.targets, self._invalid_targets)]),
            params=self.urlencode(params),
        )

    def __len__(self):
        """
        Returns the number of targets associated with this notification

        Always return 1 at least
        """
        return len(self.targets) if self.targets else 1

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

        url = self.notify_url.format(self.apikey)
        if self.source:
            url += '&from={}'.format(self.source)
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
        results['apikey'] = NotifyClickatell.unquote(results['host'])

        if results['user']:
            results['source'] = NotifyClickatell.unquote(results['user'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyClickatell.parse_phone_no(results['qsd']['to'])

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyClickatell.unquote(results['qsd']['from'])

        return results
