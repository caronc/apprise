# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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

# API Docs for sending a notification
#   Soure: https://dev.octopush.com/en/sms-gateway-api-documentation/send-sms/
#

import requests
from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import is_email
from ..utils import parse_phone_no
from ..utils import parse_bool
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


# Octopush Message Types
class OctopushType(object):
    PREMIUM = 'sms_premium'
    LOW_COST = 'sms_low_cost'


OCTOPUSH_TYPE_MAP = {
    # Maps against string 'sms_premium'
    'p': OctopushType.PREMIUM,
    'sms_p': OctopushType.PREMIUM,
    'smsp': OctopushType.PREMIUM,
    '+': OctopushType.PREMIUM,
    # Maps against string 'sms_low_cost'
    'l': OctopushType.LOW_COST,
    'sms_l': OctopushType.LOW_COST,
    'smsl': OctopushType.LOW_COST,
    '-': OctopushType.LOW_COST,
}

OCTOPUSH_TYPES = (
    OctopushType.PREMIUM,
    OctopushType.LOW_COST,
)


# Purpose
class OctopushPurpose(object):
    ALERT = 'alert'
    WHOLESALE = 'wholesale'


# A List of our Octopush Purposes we can use for verification
OCTOPUSH_PURPOSES = (
    OctopushPurpose.ALERT,
    OctopushPurpose.WHOLESALE,
)


class NotifyOctopush(NotifyBase):
    """
    A wrapper for Octopush
    """

    # The default descriptive name associated with the Notification
    service_name = 'Octopush Notification Service'

    # The services URL
    service_url = 'https://octopush.com'

    # The default secure protocol
    secure_protocol = 'octopush'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_octopush'

    # Notification URLs
    v1_notify_url = 'https://api.octopush.com/v1/public/sms-campaign/send'

    # The maximum length of the body
    body_maxlen = 1224

    # The maximum amount of phone numbers that can reside within a single
    # batch/frame transfer
    default_batch_size = 500

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{api_login}/{api_key}/{targets}',
        '{schema}://{sender}:{api_login}/{api_key}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'api_login': {
            'name': _('API Login'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'api_key': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'sender': {
            'name': _('Sender'),
            'type': 'string',
        },
        'target_phone_no': {
            'name': _('Target Phone No'),
            'type': 'string',
            'map_to': 'targets',
            'regex': (r'^[0-9\s)(+-]+$', 'i')
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
        'login': {
            'alias_of': 'api_login',
        },
        'key': {
            'alias_of': 'api_key',
        },
        'sender': {
            'alias_of': 'sender',
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
        'replies': {
            'name': _('Accept Replies'),
            'type': 'bool',
            'default': False,
        },
        'purpose': {
            'name': _('Purpose'),
            'type': 'choice:string',
            'values': OCTOPUSH_PURPOSES,
            'default': OctopushPurpose.ALERT,
        },
        'type': {
            'name': _('Type'),
            'type': 'choice:string',
            'values': OCTOPUSH_TYPES,
            'default': OctopushType.PREMIUM,
            'map_to': 'mtype',
        },
    })

    def __init__(self, api_login, api_key, targets=None, batch=False,
                 sender=None, purpose=None, mtype=None, replies=False,
                 **kwargs):
        """
        Initialize Notify Octopush Object
        """
        super(NotifyOctopush, self).__init__(**kwargs)

        # Store our API Login
        self.api_login = validate_regex(api_login)
        if not self.api_login or not is_email(self.api_login):
            msg = 'An invalid Octopush API Login ({}) was specified.' \
                .format(api_login)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our API Key
        self.api_key = validate_regex(api_key)
        if not self.api_key:
            msg = 'An invalid Octopush API Key ' \
                  '({}) was specified.'.format(api_key)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Prepare Batch Mode Flag
        self.batch = True if batch else False

        # Prepare Replies Mode Flag
        self.replies = True if replies else False

        # The Type of the message
        self.mtype = NotifyOctopush.template_args['type']['default'] \
            if not mtype else \
            next((
                v for k, v in OCTOPUSH_TYPE_MAP.items()
                if str(mtype).lower().startswith(k)), None)

        if self.mtype is None:
            # Invalid purpose specified
            msg = 'The Octopush type specified ({}) is invalid.' \
                  .format(mtype)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our purpose
        try:
            self.purpose = \
                NotifyOctopush.template_args['purpose']['default'] \
                if purpose is None else purpose.lower()

            if self.purpose not in OCTOPUSH_PURPOSES:
                # allow the outer except to handle this common response
                raise
        except:
            # Invalid purpose specified
            msg = 'The Octopush purpose specified ({}) is invalid.' \
                  .format(purpose)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.sender = None
        if sender:
            self.sender = validate_regex(sender)
            if not self.sender:
                msg = 'An invalid Octopush sender ({}) was specified.' \
                    .format(sender)
                self.logger.warning(msg)
                raise TypeError(msg)

        # Initialize numbers list
        self.targets = list()

        # Validate targets and drop bad ones:
        for target in parse_phone_no(targets):
            result = is_phone_no(target)
            if result:
                # store valid phone number in E.164 format
                self.targets.append('+{}'.format(result['full']))
                continue

            self.logger.warning(
                'Dropped invalid phone '
                '(%s) specified.' % target,
            )

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        wrapper to send_notification since we can alert more then one channel
        """

        if not self.targets:
            # We have a bot token and no target(s) to message
            self.logger.warning('No Octopush targets to notify.')
            return False

        # error tracking (used for function return)
        has_error = False

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        # Create a copy of our phone #'s to notify against
        targets = list(self.targets)

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Accept': 'application/json',
            'api-key': self.api_key,
            'api-login': self.api_login,
            'cache-control': 'no-cache',
        }

        # Prepare Octopush Message Payload
        payload = {
            # Recipients are populated prior to message xfer
            "recipients": [],
            "text": body,
            "type": self.mtype,
            "purpose": self.purpose,
            "sender": self.app_id if not self.sender else self.sender,
            "with_replies": self.replies,
        }

        for index in range(0, len(targets), batch_size):
            # Prepare our batch
            payload['recipients'] = \
                [{'phone_number': phone_no} for phone_no
                 in self.targets[index:index + batch_size]]

            # Always call throttle before any remote server i/o is made
            self.throttle()

            # Some Debug Logging
            self.logger.debug('Octopush POST URL: {} (cert_verify={})'.format(
                self.v1_notify_url, self.verify_certificate))
            self.logger.debug('Octopush Payload: {}' .format(payload))

            # For logging output of success and errors; we get a head count
            # of our outbound details:
            verbose_dest = ', '.join(
                [x[1] for x in self.targets[index:index + batch_size]]) \
                if len(self.targets[index:index + batch_size]) <= 3 \
                else '{} recipients'.format(
                    len(self.targets[index:index + batch_size]))

            try:
                r = requests.post(
                    self.v1_notify_url,
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send Octopush notification to {}: '
                        '{}{}error={}.'.format(
                            verbose_dest,
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
                        'Sent Octopush notification to {}.'.format(
                            verbose_dest))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Octopush:%s ' % (
                        verbose_dest) + 'notification.'
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

        # Define any URL parameters
        params = {
            'batch': 'yes' if self.batch else 'no',
            'replies': 'yes' if self.replies else 'no',
            'type': self.mtype,
            'purpose': self.purpose,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{sender}{api_login}/{api_key}/{targets}'\
            '?{params}'.format(
                schema=self.secure_protocol,
                sender='{}:'.format(NotifyOctopush.quote(self.sender))
                if self.sender else '',
                api_login=self.pprint(self.api_login, privacy, safe='@'),
                api_key=self.pprint(
                    self.api_key, privacy,
                    mode=PrivacyMode.Secret, safe=''),
                targets='/'.join(
                    [NotifyOctopush.quote(x, safe='+') for x in self.targets]),
                params=NotifyOctopush.urlencode(params),
            )

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

        tokens = NotifyOctopush.split_path(results['fullpath'])

        if 'key' in results['qsd'] and len(results['qsd']['key']):
            results['api_key'] = \
                NotifyOctopush.unquote(results['qsd']['key'])

        elif tokens:
            # The first target is the api_key
            results['api_key'] = tokens.pop(0)

        # The remaining elements are the phone numbers we want to contact
        results['targets'] = tokens
        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyOctopush.parse_phone_no(results['qsd']['to'])

        if 'login' in results['qsd'] and len(results['qsd']['login']):
            results['api_login'] = \
                NotifyOctopush.unquote(results['qsd']['login'])

        elif results['user'] or results['password']:
            # The Octopush API Login is extracted from the head of our URL
            results['api_login'] = '{}@{}'.format(
                NotifyOctopush.unquote(results['user'])
                if not results['password']
                else NotifyOctopush.unquote(results['password']),
                NotifyOctopush.unquote(results['host']),
            )

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get(
                'batch', NotifyOctopush.template_args['batch']['default']))

        # Get Replies Mode
        results['replies'] = \
            parse_bool(results['qsd'].get(
                'replies', NotifyOctopush.template_args['replies']['default']))

        if 'type' in results['qsd'] and len(results['qsd']['type']):
            # Extract Type
            results['mtype'] = \
                NotifyOctopush.unquote(results['qsd']['type'])

        if 'purpose' in results['qsd'] and len(results['qsd']['purpose']):
            # Extract Purpose
            results['purpose'] = \
                NotifyOctopush.unquote(results['qsd']['purpose'])

        if 'sender' in results['qsd'] and len(results['qsd']['sender']):
            # Extract Sender
            results['sender'] = \
                NotifyOctopush.unquote(results['qsd']['sender'])

        elif results['user'] and results['password']:
            results['sender'] = \
                NotifyOctopush.unquote(results['user'])

        # Return our result set
        return results
