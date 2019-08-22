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

# Create an account https://messagebird.com if you don't already have one
#
# Get your (apikey) and api example from the dashboard here:
#   - https://dashboard.messagebird.com/en/user/index
#

import re
import requests

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _

# Token required as part of the API request
VALIDATE_APIKEY = re.compile(r'^[a-z0-9]{25}$', re.I)

# Some Phone Number Detection
IS_PHONE_NO = re.compile(r'^\+?(?P<phone>[0-9\s)(+-]+)\s*$')


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
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_msgbird'

    # MessageBird uses the http protocol with JSON requests
    notify_url = 'https://rest.messagebird.com/messages'

    # The maximum length of the body
    body_maxlen = 140

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
            'regex': (r'[a-z0-9]{25}', 'i'),
        },
        'source': {
            'name': _('Source Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'[0-9\s)(+-]+', 'i'),
        },
        'target_phone': {
            'name': _('Target Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'[0-9\s)(+-]+', 'i'),
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
        super(NotifyMessageBird, self).__init__(**kwargs)

        try:
            # The authentication key associated with the account
            self.apikey = apikey.strip()

        except AttributeError:
            # Token was None
            msg = 'No MessageBird authentication key was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not VALIDATE_APIKEY.match(self.apikey):
            msg = 'The MessageBird authentication key specified ({}) is ' \
                'invalid.'.format(self.apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        result = IS_PHONE_NO.match(source)
        if not result:
            msg = 'The MessageBird source specified ({}) is invalid.'\
                .format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Further check our phone # for it's digit count
        result = ''.join(re.findall(r'\d+', result.group('phone')))
        if len(result) < 11 or len(result) > 14:
            msg = 'The MessageBird source # specified ({}) is invalid.'\
                .format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our source
        self.source = result

        # Parse our targets
        self.targets = list()

        for target in parse_list(targets):
            # Validate targets and drop bad ones:
            result = IS_PHONE_NO.match(target)
            if result:
                # Further check our phone # for it's digit count
                result = ''.join(re.findall(r'\d+', result.group('phone')))
                if len(result) < 11 or len(result) > 14:
                    self.logger.warning(
                        'Dropped invalid phone # '
                        '({}) specified.'.format(target),
                    )
                    continue

                # store valid phone number
                self.targets.append(result)
                continue

            self.logger.warning(
                'Dropped invalid phone # '
                '({}) specified.'.format(target),
            )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform MessageBird Notification
        """

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

        if len(targets) == 0:
            # No sources specified, use our own phone no
            targets.append(self.source)

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
                    'A Connection error occured sending MessageBird:%s ' % (
                        target) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        return '{schema}://{apikey}/{source}/{targets}/?{args}'.format(
            schema=self.secure_protocol,
            apikey=self.apikey,
            source=self.source,
            targets='/'.join(
                [NotifyMessageBird.quote(x, safe='') for x in self.targets]),
            args=NotifyMessageBird.urlencode(args))

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

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = NotifyMessageBird.split_path(results['fullpath'])

        try:
            # The first path entry is the source/originator
            results['source'] = results['targets'].pop(0)
        except IndexError:
            # No path specified... this URL is potentially un-parseable; we can
            # hope for a from= entry
            pass

        # The hostname is our authentication key
        results['apikey'] = NotifyMessageBird.unquote(results['host'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyMessageBird.parse_list(results['qsd']['to'])

        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyMessageBird.unquote(results['qsd']['from'])

        return results
