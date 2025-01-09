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

# Create an account https://messagebird.com if you don't already have one
#
# Get your (apikey) and api example from the dashboard here:
#   - https://dashboard.messagebird.com/en/user/index
#

import requests

from .base import NotifyBase
from ..common import NotifyType
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from ..locale import gettext_lazy as _


class NotifyMessageBird(NotifyBase):
    """
    A wrapper for MessageBird Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'MessageBird'

    # The services URL
    service_url = 'https://messagebird.com'

    # The default protocol
    secure_protocol = 'msgbird'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_messagebird'

    # MessageBird uses the http protocol with JSON requests
    notify_url = 'https://rest.messagebird.com/messages'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{apikey}/{source}',
        '{schema}://{apikey}/{source}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[a-z0-9]{25}$', 'i'),
        },
        'source': {
            'name': _('Source Phone No'),
            'type': 'string',
            'prefix': '+',
            'required': True,
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
        }
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'from': {
            'alias_of': 'source',
        },
    })

    def __init__(self, apikey, source, targets=None, **kwargs):
        """
        Initialize MessageBird Object
        """
        super().__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(
            apikey, *self.template_tokens['apikey']['regex'])
        if not self.apikey:
            msg = 'An invalid MessageBird API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        result = is_phone_no(source)
        if not result:
            msg = 'The MessageBird source specified ({}) is invalid.'\
                .format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our source
        self.source = result['full']

        # Parse our targets
        self.targets = list()

        targets = parse_phone_no(targets)
        if not targets:
            # No sources specified, use our own phone no
            self.targets.append(self.source)
            return

        # otherwise, store all of our target numbers
        for target in targets:
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

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform MessageBird Notification
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning('There were no MessageBird targets to notify.')
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'AccessKey {}'.format(self.apikey),
        }

        # Prepare our payload
        payload = {
            'originator': '+{}'.format(self.source),
            'recipients': None,
            'body': body,

        }

        # Create a copy of the targets list
        targets = list(self.targets)

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our user
            payload['recipients'] = '+{}'.format(target)

            # Some Debug Logging
            self.logger.debug(
                'MessageBird POST URL: {} (cert_verify={})'.format(
                    self.notify_url, self.verify_certificate))
            self.logger.debug('MessageBird Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                # Sample output of a successful transmission
                # {
                #   "originator": "+15553338888",
                #   "body": "test",
                #   "direction": "mt",
                #   "mclass": 1,
                #   "reference": null,
                #   "createdDatetime": "2019-08-22T01:32:18+00:00",
                #   "recipients": {
                #     "totalCount": 1,
                #     "totalSentCount": 1,
                #     "totalDeliveredCount": 0,
                #     "totalDeliveryFailedCount": 0,
                #     "items": [
                #       {
                #         "status": "sent",
                #         "statusDatetime": "2019-08-22T01:32:18+00:00",
                #         "recipient": 15553338888,
                #         "messagePartCount": 1
                #       }
                #     ]
                #   },
                #   "validity": null,
                #   "gateway": 10,
                #   "typeDetails": {},
                #   "href": "https://rest.messagebird.com/messages/\
                #       b5d424244a5b4fd0b5b5728bccaafc23",
                #   "datacoding": "plain",
                #   "scheduledDatetime": null,
                #   "type": "sms",
                #   "id": "b5d424244a5b4fd0b5b5728bccaafc23"
                # }

                if r.status_code not in (
                        requests.codes.ok, requests.codes.created):
                    # We had a problem
                    status_str = \
                        NotifyMessageBird.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send MessageBird notification to {}: '
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
                        'Sent MessageBird notification to {}.'.format(target))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending MessageBird:%s ' % (
                        target) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.apikey, self.source)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return '{schema}://{apikey}/{source}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=''),
            source=self.source,
            targets='/'.join(
                [NotifyMessageBird.quote(x, safe='') for x in self.targets]),
            params=NotifyMessageBird.urlencode(params))

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
        results['targets'] = NotifyMessageBird.split_path(results['fullpath'])

        try:
            # The first path entry is the source/originator
            results['source'] = results['targets'].pop(0)

        except IndexError:
            # No path specified... this URL is potentially un-parseable; we can
            # hope for a from= entry
            results['source'] = None

        # The hostname is our authentication key
        results['apikey'] = NotifyMessageBird.unquote(results['host'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyMessageBird.parse_phone_no(results['qsd']['to'])

        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyMessageBird.unquote(results['qsd']['from'])

        return results
