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

# To use this service you will need a D7 Networks account from their website
# at https://d7networks.com/
#
# After you've established your account you can get your api login credentials
# (both user and password) from the API Details section from within your
# account profile area:  https://d7networks.com/accounts/profile/
#
# API Reference: https://d7networks.com/docs/Messages/Send_Message/

import requests
from json import dumps
from json import loads

from .base import NotifyBase
from ..common import NotifyType
from ..utils.parse import (
    is_phone_no, parse_phone_no, validate_regex, parse_bool)
from ..locale import gettext_lazy as _

# Extend HTTP Error Messages
D7NETWORKS_HTTP_ERROR_MAP = {
    401: 'Invalid Argument(s) Specified.',
    403: 'Unauthorized - Authentication Failure.',
    412: 'A Routing Error Occured',
    500: 'A Serverside Error Occured Handling the Request.',
}


class NotifyD7Networks(NotifyBase):
    """
    A wrapper for D7 Networks Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'D7 Networks'

    # The services URL
    service_url = 'https://d7networks.com/'

    # All notification requests are secure
    secure_protocol = 'd7sms'

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_d7networks'

    # D7 Networks single notification URL
    notify_url = 'https://api.d7networks.com/messages/v1/send'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{token}@{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'token': {
            'name': _('API Access Token'),
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
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'unicode': {
            # Unicode characters (default is 'auto')
            'name': _('Unicode Characters'),
            'type': 'bool',
            'default': False,
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
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
    })

    def __init__(self, token=None, targets=None, source=None,
                 batch=False, unicode=None, **kwargs):
        """
        Initialize D7 Networks Object
        """
        super().__init__(**kwargs)

        # Prepare Batch Mode Flag
        self.batch = batch

        # Setup our source address (if defined)
        self.source = None \
            if not isinstance(source, str) else source.strip()

        # Define whether or not we should set the unicode flag
        self.unicode = self.template_args['unicode']['default'] \
            if unicode is None else bool(unicode)

        # The token associated with the account
        self.token = validate_regex(token)
        if not self.token:
            msg = 'The D7 Networks token specified ({}) is invalid.'\
                .format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Parse our targets
        self.targets = list()
        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            result = result = is_phone_no(target)
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
        Depending on whether we are set to batch mode or single mode this
        redirects to the appropriate handling
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning('There were no D7 Networks targets to notify.')
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.token}',
        }

        payload = {
            'message_globals': {
                'channel': 'sms',
            },
            'messages': [{
                # Populated later on
                'recipients': None,
                'content': body,
                'data_coding':
                # auto is a better substitute over 'text' as text is easier to
                # detect from a post than `unicode` is.
                'auto' if not self.unicode else 'unicode',
            }],
        }

        # use the list directly
        targets = list(self.targets)

        if self.source:
            payload['message_globals']['originator'] = self.source

        target = None
        while len(targets):

            if self.batch:
                # Prepare our payload
                payload['messages'][0]['recipients'] = self.targets

                # Reset our targets so we don't keep going. This is required
                # because we're in batch mode; we only need to loop once.
                targets = []

            else:
                # We're not in a batch mode; so get our next target
                # Get our target(s) to notify
                target = targets.pop(0)

                # Prepare our payload
                payload['messages'][0]['recipients'] = [target]

            # Some Debug Logging
            self.logger.debug(
                'D7 Networks POST URL: {} (cert_verify={})'.format(
                    self.notify_url, self.verify_certificate))
            self.logger.debug('D7 Networks Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code not in (
                        requests.codes.created, requests.codes.ok):
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(
                            r.status_code, D7NETWORKS_HTTP_ERROR_MAP)

                    try:
                        # Update our status response if we can
                        json_response = loads(r.content)
                        status_str = json_response.get('message', status_str)

                    except (AttributeError, TypeError, ValueError):
                        # ValueError = r.content is Unparsable
                        # TypeError = r.content is None
                        # AttributeError = r is None

                        # We could not parse JSON response.
                        # We will just use the status we already have.
                        pass

                    self.logger.warning(
                        'Failed to send D7 Networks SMS notification to {}: '
                        '{}{}error={}.'.format(
                            ', '.join(target) if self.batch else target,
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:

                    if self.batch:
                        self.logger.info(
                            'Sent D7 Networks batch SMS notification to '
                            '{} target(s).'.format(len(self.targets)))

                    else:
                        self.logger.info(
                            'Sent D7 Networks SMS notification to {}.'.format(
                                target))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending D7 Networks:%s ' % (
                        ', '.join(self.targets)) + 'notification.'
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
            'unicode': 'yes' if self.unicode else 'no',
        }

        if self.source:
            params['from'] = self.source

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{token}@{targets}/?{params}'.format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=''),
            targets='/'.join(
                [NotifyD7Networks.quote(x, safe='') for x in self.targets]),
            params=NotifyD7Networks.urlencode(params))

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.token)

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        #
        # Factor batch into calculation
        #
        return len(self.targets) if not self.batch else 1

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

        if 'token' in results['qsd'] and len(results['qsd']['token']):
            results['token'] = \
                NotifyD7Networks.unquote(results['qsd']['token'])

        elif results['user']:
            results['token'] = NotifyD7Networks.unquote(results['user'])

            if results['password']:
                # Support token containing a colon (:)
                results['token'] += \
                    ':' + NotifyD7Networks.unquote(results['password'])

        elif results['password']:
            # Support token starting with a colon (:)
            results['token'] = \
                ':' + NotifyD7Networks.unquote(results['password'])

        # Initialize our targets
        results['targets'] = list()

        # The store our first target stored in the hostname
        results['targets'].append(NotifyD7Networks.unquote(results['host']))

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'].extend(
            NotifyD7Networks.split_path(results['fullpath']))

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get('batch', False))

        # Get Unicode Flag
        results['unicode'] = \
            parse_bool(results['qsd'].get('unicode', False))

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyD7Networks.parse_phone_no(results['qsd']['to'])

        # Support the 'from' and source variable
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyD7Networks.unquote(results['qsd']['from'])

        elif 'source' in results['qsd'] and len(results['qsd']['source']):
            results['source'] = \
                NotifyD7Networks.unquote(results['qsd']['source'])

        return results
