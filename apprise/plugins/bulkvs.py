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

# To use this service you will need a BulkVS account
# You will need credits (new accounts start with a few)
#     https://www.bulkvs.com/

# API is documented here:
#   - https://portal.bulkvs.com/api/v1.0/documentation#/\
#             Messaging/post_messageSend
import requests
import json
from .base import NotifyBase
from ..url import PrivacyMode
from ..common import NotifyType
from ..utils.parse import is_phone_no, parse_phone_no, parse_bool
from ..locale import gettext_lazy as _


class NotifyBulkVS(NotifyBase):
    """
    A wrapper for BulkVS Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'BulkVS'

    # The services URL
    service_url = 'https://www.bulkvs.com/'

    # All notification requests are secure
    secure_protocol = 'bulkvs'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_bulkvs'

    # BulkVS uses the http protocol with JSON requests
    notify_url = 'https://portal.bulkvs.com/api/v1.0/messageSend'

    # The maximum length of the body
    body_maxlen = 160

    # The maximum amount of texts that can go out in one batch
    default_batch_size = 4000

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{user}:{password}@{from_phone}/{targets}',
        '{schema}://{user}:{password}@{from_phone}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'user': {
            'name': _('User Name'),
            'type': 'string',
            'required': True,
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'from_phone': {
            'name': _('From Phone No'),
            'type': 'string',
            'regex': (r'^\+?[0-9\s)(+-]+$', 'i'),
            'map_to': 'source',
            'required': True,
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

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'from': {
            'name': _('From Phone No'),
            'type': 'string',
            'regex': (r'^\+?[0-9\s)(+-]+$', 'i'),
            'map_to': 'source',
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
    })

    def __init__(self, source=None, targets=None, batch=None, **kwargs):
        """
        Initialize BulkVS Object
        """
        super(NotifyBulkVS, self).__init__(**kwargs)

        if not (self.user and self.password):
            msg = 'A BulkVS user/pass was not provided.'
            self.logger.warning(msg)
            raise TypeError(msg)

        result = is_phone_no(source)
        if not result:
            msg = 'The Account (From) Phone # specified ' \
                  '({}) is invalid.'.format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Tidy source
        self.source = result['full']

        # Define whether or not we should operate in a batch mode
        self.batch = self.template_args['batch']['default'] \
            if batch is None else bool(batch)

        # Parse our targets
        self.targets = list()

        has_error = False
        for target in parse_phone_no(targets):
            # Parse each phone number we found
            result = is_phone_no(target)
            if result:
                self.targets.append(result['full'])
                continue

            has_error = True
            self.logger.warning(
                'Dropped invalid phone # ({}) specified.'.format(target),
            )

        if not targets and not has_error:
            # Default the SMS Message to ourselves
            self.targets.append(self.source)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform BulkVS Notification
        """

        if not self.targets:
            # We have nothing to notify
            self.logger.warning('There are no BulkVS targets to notify')
            return False

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        # Prepare our payload
        payload = {
            # The To gets populated in the loop below
            'From': self.source,
            'To': None,
            'Message': body,
        }

        # Authentication
        auth = (self.user, self.password)

        # Prepare our targets
        targets = list(self.targets) if batch_size == 1 else \
            [self.targets[index:index + batch_size]
             for index in range(0, len(self.targets), batch_size)]

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our user
            payload['To'] = target

            # Printable reference
            if isinstance(target, list):
                p_target = '{} targets'.format(len(target))

            else:
                p_target = target

            # Some Debug Logging
            self.logger.debug('BulkVS POST URL: {} (cert_verify={})'.format(
                self.notify_url, self.verify_certificate))
            self.logger.debug('BulkVS Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=json.dumps(payload),
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                # A Response may look like:
                # {
                #   "RefId": "5a66dee6-ff7a-40ee-8218-5805c074dc01",
                #   "From": "13109060901",
                #   "MessageType": "SMS|MMS",
                #   "Results": [
                #     {
                #       "To": "13105551212",
                #       "Status": "SUCCESS"
                #     },
                #     {
                #       "To": "13105551213",
                #       "Status": "SUCCESS"
                #     }
                #   ]
                # }
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(r.status_code)

                    # set up our status code to use
                    status_code = r.status_code

                    self.logger.warning(
                        'Failed to send BulkVS notification to {}: '
                        '{}{}error={}.'.format(
                            p_target,
                            status_str,
                            ', ' if status_str else '',
                            status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent BulkVS notification to {}.'.format(p_target))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending BulkVS: to %s ',
                    p_target)
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
        return (self.secure_protocol, self.source, self.user, self.password)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'batch': 'yes' if self.batch else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # A nice way of cleaning up the URL length a bit
        targets = [] if len(self.targets) == 1 \
            and self.targets[0] == self.source else self.targets

        return '{schema}://{user}:{password}@{source}/{targets}' \
            '?{params}'.format(
                schema=self.secure_protocol,
                source=self.source,
                user=self.pprint(self.user, privacy, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
                targets='/'.join([
                    NotifyBulkVS.quote('{}'.format(x), safe='+')
                    for x in targets]),
                params=NotifyBulkVS.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """

        #
        # Factor batch into calculation
        #
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets) if self.targets else 1
        if batch_size > 1:
            targets = int(targets / batch_size) + \
                (1 if targets % batch_size else 0)

        return targets

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

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyBulkVS.unquote(results['qsd']['from'])

            # hostname will also be a target in this case
            results['targets'] = [
                *NotifyBulkVS.parse_phone_no(results['host']),
                *NotifyBulkVS.split_path(results['fullpath'])]

        else:
            # store our source
            results['source'] = NotifyBulkVS.unquote(results['host'])

            # store targets
            results['targets'] = NotifyBulkVS.split_path(results['fullpath'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyBulkVS.parse_phone_no(results['qsd']['to'])

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get(
                'batch', NotifyBulkVS.template_args['batch']['default']))

        return results
