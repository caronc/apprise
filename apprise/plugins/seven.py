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
# Create an account https://www.seven.io if you don't already have one
#
# Get your (apikey) from here:
#   - https://help.seven.io/en/api-key-access
#
import requests
import json
from .base import NotifyBase
from ..common import NotifyType
from ..utils.parse import is_phone_no, parse_phone_no, parse_bool
from ..locale import gettext_lazy as _


class NotifySeven(NotifyBase):
    """
    A wrapper for seven Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'seven'

    # The services URL
    service_url = 'https://www.seven.io'

    # The default protocol
    secure_protocol = 'seven'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_seven'

    # Seven uses the http protocol with JSON requests
    notify_url = 'https://gateway.seven.io/api/sms'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{apikey}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'required': True,
            'private': True,
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
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'source': {
            # Originating address,In cases where the rewriting of the sender's
            # address is supported or permitted by the SMS-C. This is used to
            # transmit the message, this number is transmitted as the
            # originating address and is completely optional.
            'name': _('Originating Address'),
            'type': 'string',
            'map_to': 'source',
        },
        'from': {
            'alias_of': 'source',
        },
        'flash': {
            'name': _('Flash'),
            'type': 'bool',
            'default': False,
        },
        'label': {
            'name': _('Label'),
            'type': 'string'
        },
    })

    def __init__(self, apikey, targets=None, source=None, flash=None,
                 label=None, **kwargs):
        """
        Initialize Seven Object
        """
        super().__init__(**kwargs)
        # API Key (associated with project)
        self.apikey = apikey
        if not self.apikey:
            msg = 'An invalid seven API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.source = None \
            if not isinstance(source, str) else source.strip()
        self.flash = self.template_args['flash']['default'] \
            if flash is None else bool(flash)
        self.label = None \
            if not isinstance(label, str) else label.strip()

        # Parse our targets
        self.targets = list()

        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    'Dropped invalid phone # '
                    '({}) specified.'.format(target),
                )
                continue
            # store valid phone number
            self.targets.append(result['full'])
        return

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another similar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.apikey)

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform seven Notification
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning('There were no seven targets to notify.')
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'SentWith': 'Apprise',
            'X-Api-Key': self.apikey,
        }

        # Prepare our payload
        payload = {
            'to': None,
            'text': body,
        }
        if self.source:
            payload['from'] = self.source
        if self.flash:
            payload['flash'] = self.flash
        if self.label:
            payload['label'] = self.label
        # Create a copy of the targets list
        targets = list(self.targets)
        while len(targets):
            # Get our target to notify
            target = targets.pop(0)
            # Prepare our user
            payload['to'] = '+{}'.format(target)
            # Some Debug Logging
            self.logger.debug(
                'seven POST URL: {} (cert_verify={})'.format(
                    self.notify_url, self.verify_certificate))
            self.logger.debug('seven Payload: {}' .format(payload))
            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=json.dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                # Sample output of a successful transmission
                # {
                #     "success": "100",
                #     "total_price": 0.075,
                #     "balance": 46.748,
                #     "debug": "false",
                #     "sms_type": "direct",
                #     "messages": [
                #         {
                #             "id": "77229135982",
                #             "sender": "492022839080",
                #             "recipient": "4917661254799",
                #             "text": "x",
                #             "encoding": "gsm",
                #             "label": null,
                #             "parts": 1,
                #             "udh": null,
                #             "is_binary": false,
                #             "price": 0.075,
                #             "success": true,
                #             "error": null,
                #             "error_text": null
                #         }
                #     ]
                # }
                if r.status_code not in (
                        requests.codes.ok, requests.codes.created):
                    # We had a problem
                    status_str = \
                        NotifySeven.http_response_code_lookup(
                            r.status_code)
                    self.logger.warning(
                        'Failed to send seven notification to {}: '
                        '{}{}error={}.'.format(
                            ','.join(target),
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))
                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))
                    # Mark our failure
                    has_error = True
                    continue
                else:
                    self.logger.info(
                        'Sent seven notification to {}.'.format(target))
            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending seven:%s ' % (
                        target) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                # Mark our failure
                has_error = True
                continue
        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        params = {
            'flash': 'yes' if self.flash else 'no',
        }
        if self.source:
            params['from'] = self.source
        if self.label:
            params['label'] = self.label

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return '{schema}://{apikey}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=''),
            targets='/'.join(
                [NotifySeven.quote(x, safe='') for x in self.targets]),
            params=NotifySeven.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        targets = len(self.targets)
        return targets if targets > 0 else 1

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

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = NotifySeven.split_path(results['fullpath'])

        # The hostname is our authentication key
        results['apikey'] = NotifySeven.unquote(results['host'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifySeven.parse_phone_no(results['qsd']['to'])

        # Support the 'from' and source variable
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifySeven.unquote(results['qsd']['from'])

        elif 'source' in results['qsd'] and len(results['qsd']['source']):
            results['source'] = \
                NotifySeven.unquote(results['qsd']['source'])

        results['flash'] = \
            parse_bool(results['qsd'].get('flash', False))
        results['label'] = \
            results['qsd'].get('label', None)

        return results
