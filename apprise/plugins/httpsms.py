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

# To use this service you will need a httpSMS account
# You will need credits (new accounts start with a few)
#     https://httpsms.com
import requests
import json
from .base import NotifyBase
from ..common import NotifyType
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from ..locale import gettext_lazy as _


class NotifyHttpSMS(NotifyBase):
    """
    A wrapper for HttpSMS Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'httpSMS'

    # The services URL
    service_url = 'https://httpsms.com'

    # All notification requests are secure
    secure_protocol = 'httpsms'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_httpsms'

    # HttpSMS uses the http protocol with JSON requests
    notify_url = 'https://api.httpsms.com/v1/messages/send'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{apikey}@{from_phone}',
        '{schema}://{apikey}@{from_phone}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
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
            'map_to': 'source',
        },
    })

    def __init__(self, apikey=None, source=None, targets=None, **kwargs):
        """
        Initialize HttpSMS Object
        """
        super(NotifyHttpSMS, self).__init__(**kwargs)

        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = 'An invalid API Key ({}) was specified.'.format(apikey)
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
        Perform HttpSMS Notification
        """

        if not self.targets:
            # We have nothing to notify
            self.logger.warning('There are no HttpSMS targets to notify')
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'x-api-key': self.apikey,
            'Content-Type': 'application/json',
        }

        # Prepare our payload
        payload = {
            # The To gets populated in the loop below
            'from': '+' + self.source,
            'to': None,
            'content': body,
        }

        # Prepare our targets
        targets = list(self.targets)
        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our user
            payload['to'] = '+' + target

            # Some Debug Logging
            self.logger.debug('HttpSMS POST URL: {} (cert_verify={})'.format(
                self.notify_url, self.verify_certificate))
            self.logger.debug('HttpSMS Payload: {}' .format(payload))

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

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(r.status_code)

                    # set up our status code to use
                    status_code = r.status_code

                    self.logger.warning(
                        'Failed to send HttpSMS notification to {}: '
                        '{}{}error={}.'.format(
                            target,
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
                        'Sent HttpSMS notification to {}.'.format(target))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending HttpSMS: to %s ',
                    target)
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
        return (self.secure_protocol, self.source, self.apikey)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Prepare our parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # A nice way of cleaning up the URL length a bit
        targets = [] if len(self.targets) == 1 \
            and self.targets[0] == self.source else self.targets

        return '{schema}://{apikey}@{source}/{targets}' \
            '?{params}'.format(
                schema=self.secure_protocol,
                source=self.source,
                apikey=self.pprint(self.apikey, privacy, safe=''),
                targets='/'.join([
                    NotifyHttpSMS.quote('{}'.format(x), safe='+')
                    for x in targets]),
                params=NotifyHttpSMS.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """

        return len(self.targets) if self.targets else 1

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
        results['apikey'] = NotifyHttpSMS.unquote(results['user'])

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyHttpSMS.unquote(results['qsd']['from'])

            # hostname will also be a target in this case
            results['targets'] = [
                *NotifyHttpSMS.parse_phone_no(results['host']),
                *NotifyHttpSMS.split_path(results['fullpath'])]

        else:
            # store our source
            results['source'] = NotifyHttpSMS.unquote(results['host'])

            # store targets
            results['targets'] = NotifyHttpSMS.split_path(results['fullpath'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyHttpSMS.parse_phone_no(results['qsd']['to'])

        if 'key' in results['qsd'] and len(results['qsd']['key']):
            results['apikey'] = \
                NotifyHttpSMS.unquote(results['qsd']['key'])

        return results
