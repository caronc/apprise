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

# API Reference: https://smsmanager.cz/api/http#send

# To use this service you will need a SMS Manager account
# You will need credits (new accounts start with a few)
#     https://smsmanager.cz
#    1. Sign up and get test credit
#    2. Generate an API key in web administration.

import requests
from .base import NotifyBase
from ..common import NotifyType
from ..utils.parse import (
    is_phone_no, parse_phone_no, parse_bool, validate_regex)
from ..locale import gettext_lazy as _


class SMSManagerGateway(object):
    """
    The different gateway values
    """
    HIGH = "high"
    ECONOMY = "economy"
    LOW = "low"
    DIRECT = "direct"


# Used for verification purposes
SMS_MANAGER_GATEWAYS = (
    SMSManagerGateway.HIGH,
    SMSManagerGateway.ECONOMY,
    SMSManagerGateway.LOW,
    SMSManagerGateway.DIRECT,
)


class NotifySMSManager(NotifyBase):
    """
    A wrapper for SMS Manager Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'SMS Manager'

    # The services URL
    service_url = 'https://smsmanager.cz'

    # All notification requests are secure
    secure_protocol = ('smsmgr', 'smsmanager',)

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_sms_manager'

    # SMS Manager uses the http protocol with JSON requests
    notify_url = 'https://http-api.smsmanager.cz/Send'

    # The maximum amount of texts that can go out in one batch
    default_batch_size = 4000

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{apikey}@{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
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
        'key': {
            'alias_of': 'apikey',
        },
        'to': {
            'alias_of': 'targets',
        },
        'from': {
            'name': _('From Phone No'),
            'type': 'string',
            'regex': (r'^\+?[0-9\s)(+-]+$', 'i'),
            'map_to': 'sender',
        },
        'sender': {
            'alias_of': 'from',
        },
        'gateway': {
            'name': _('Gateway'),
            'type': 'choice:string',
            'values': SMS_MANAGER_GATEWAYS,
            'default': SMS_MANAGER_GATEWAYS[0],
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
    })

    def __init__(self, apikey=None, sender=None, targets=None, batch=None,
                 gateway=None, **kwargs):
        """
        Initialize SMS Manager Object
        """
        super(NotifySMSManager, self).__init__(**kwargs)

        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = 'An invalid API Key ({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Setup our gateway
        self.gateway = self.template_args['gateway']['default'] \
            if not isinstance(gateway, str) else gateway.lower()
        if self.gateway not in SMS_MANAGER_GATEWAYS:
            msg = 'The Gateway specified ({}) is invalid.'.format(gateway)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Define whether or not we should operate in a batch mode
        self.batch = self.template_args['batch']['default'] \
            if batch is None else bool(batch)

        # Maximum 11 characters and must be approved by administrators of site
        self.sender = sender[0:11] if isinstance(sender, str) else None

        # Parse our targets
        self.targets = list()

        for target in parse_phone_no(targets):
            # Parse each phone number we found
            # It is documented that numbers with a length of 9 characters are
            # supplemented by "420".
            result = is_phone_no(target, min_len=9)
            if result:
                # Carry forward '+' if defined, otherwise do not...
                self.targets.append(
                    ('+' + result['full'])
                    if target.lstrip()[0] == '+' else result['full'])
                continue

            self.logger.warning(
                'Dropped invalid phone # ({}) specified.'.format(target),
            )

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform SMS Manager Notification
        """

        if not self.targets:
            # We have nothing to notify
            self.logger.warning('There are no SMS Manager targets to notify')
            return False

        # error tracking (used for function return)
        has_error = False

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
        }

        # Prepare our targets
        targets = list(self.targets) if batch_size == 1 else \
            [self.targets[index:index + batch_size]
             for index in range(0, len(self.targets), batch_size)]

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our payload
            # Note: Payload is assembled inside of our while-loop due to
            #       mock testing issues (payload singleton isn't persistent
            #       when performing follow up checks on the params object.
            payload = {
                'apikey': self.apikey,
                'gateway': self.gateway,
                # The number gets populated in the loop below
                'number': None,
                'message': body,
            }

            if self.sender:
                # Sender is ony set if specified
                payload['sender'] = self.sender

            # Printable target details
            if isinstance(target, list):
                p_target = '{} targets'.format(len(target))

                # Prepare our target numbers
                payload['number'] = ';'.join(target)

            else:
                p_target = target
                # Prepare our target numbers
                payload['number'] = target

            # Some Debug Logging
            self.logger.debug(
                'SMS Manager POST URL: {} (cert_verify={})'.format(
                    self.notify_url, self.verify_certificate))
            self.logger.debug('SMS Manager Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.get(
                    self.notify_url,
                    params=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(r.status_code)

                    # set up our status code to use
                    status_code = r.status_code

                    self.logger.warning(
                        'Failed to send SMS Manager notification to {}: '
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
                        'Sent SMS Manager notification to {}.'.format(
                            p_target))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending SMS Manager: to %s ',
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
        return (self.secure_protocol[0], self.apikey)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'batch': 'yes' if self.batch else 'no',
            'gateway': self.gateway,
        }

        if self.sender:
            # Set our sender if it was set
            params['sender'] = self.sender

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{apikey}@{targets}' \
            '?{params}'.format(
                schema=self.secure_protocol[0],
                apikey=self.pprint(self.apikey, privacy, safe=''),
                targets='/'.join([
                    NotifySMSManager.quote('{}'.format(x), safe='+')
                    for x in self.targets]),
                params=NotifySMSManager.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """

        #
        # Factor batch into calculation
        #
        # Note: Groups always require a separate request (and can not be
        # included in batch calculations)
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets)
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

        # Get our API Key
        results['apikey'] = NotifySMSManager.unquote(results['user'])

        # Store our targets
        results['targets'] = [
            *NotifySMSManager.parse_phone_no(results['host']),
            *NotifySMSManager.split_path(results['fullpath'])]

        # The 'from' makes it easier to use yaml configuration
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['sender'] = \
                NotifySMSManager.unquote(results['qsd']['from'])

        elif 'sender' in results['qsd'] and len(results['qsd']['sender']):
            # Support sender= value as well to align with SMS Manager API
            results['sender'] = \
                NotifySMSManager.unquote(results['qsd']['sender'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifySMSManager.parse_phone_no(results['qsd']['to'])

        if 'key' in results['qsd'] and len(results['qsd']['key']):
            results['apikey'] = \
                NotifySMSManager.unquote(results['qsd']['key'])

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get(
                'batch', NotifySMSManager.template_args['batch']['default']))

        # Define our gateway
        if 'gateway' in results['qsd'] and len(results['qsd']['gateway']):
            results['gateway'] = \
                NotifySMSManager.unquote(results['qsd']['gateway'])

        return results
