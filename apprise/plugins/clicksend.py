# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

# To use this plugin, simply signup with clicksend:
#  https://www.clicksend.com/
#
# You're done at this point, you only need to know your user/pass that
# you signed up with.

#  The following URLs would be accepted by Apprise:
#   - clicksend://{user}:{password}@{phoneno}
#   - clicksend://{user}:{password}@{phoneno1}/{phoneno2}

# The API reference used to build this plugin was documented here:
#  https://developers.clicksend.com/docs/rest/v3/
#
import requests
from json import dumps

from .base import NotifyBase
from ..url import PrivacyMode
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import parse_phone_no
from ..utils import parse_bool
from ..locale import gettext_lazy as _

# Extend HTTP Error Messages
CLICKSEND_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
}


class NotifyClickSend(NotifyBase):
    """
    A wrapper for ClickSend Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'ClickSend'

    # The services URL
    service_url = 'https://clicksend.com/'

    # The default secure protocol
    secure_protocol = 'clicksend'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_clicksend'

    # ClickSend uses the http protocol with JSON requests
    notify_url = 'https://rest.clicksend.com/v3/sms/send'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # The maximum SMS batch size accepted by the ClickSend API
    default_batch_size = 1000

    # Define object templates
    templates = (
        '{schema}://{user}:{apikey}@{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'user': {
            'name': _('User Name'),
            'type': 'string',
            'required': True,
        },
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'required': True,
            'map_to': 'password',
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
        'key': {
            'alias_of': 'apikey',
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
    })

    def __init__(self, targets=None, batch=False, **kwargs):
        """
        Initialize ClickSend Object
        """
        super().__init__(**kwargs)

        # Prepare Batch Mode Flag
        self.batch = batch

        # Parse our targets
        self.targets = list()

        if not (self.user and self.password):
            msg = 'A ClickSend user/pass was not provided.'
            self.logger.warning(msg)
            raise TypeError(msg)

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

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform ClickSend Notification
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning('There were no ClickSend targets to notify.')
            return False

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json; charset=utf-8',
        }

        # error tracking (used for function return)
        has_error = False

        # prepare JSON Object
        payload = {
            'messages': []
        }

        # Send in batches if identified to do so
        default_batch_size = 1 if not self.batch else self.default_batch_size

        for index in range(0, len(self.targets), default_batch_size):
            payload['messages'] = [{
                'source': 'php',
                'body': body,
                'to': '+{}'.format(to),
            } for to in self.targets[index:index + default_batch_size]]

            self.logger.debug('ClickSend POST URL: %s (cert_verify=%r)' % (
                self.notify_url, self.verify_certificate,
            ))
            self.logger.debug('ClickSend Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    auth=(self.user, self.password),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyClickSend.http_response_code_lookup(
                            r.status_code, CLICKSEND_HTTP_ERROR_MAP)

                    self.logger.warning(
                        'Failed to send {} ClickSend notification{}: '
                        '{}{}error={}.'.format(
                            len(payload['messages']),
                            ' to {}'.format(self.targets[index])
                            if default_batch_size == 1 else '(s)',
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
                        'Sent {} ClickSend notification{}.'
                        .format(
                            len(payload['messages']),
                            ' to {}'.format(self.targets[index])
                            if default_batch_size == 1 else '(s)',
                        ))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending {} ClickSend '
                    'notification(s).'.format(len(payload['messages'])))
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
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Setup Authentication
        auth = '{user}:{password}@'.format(
            user=NotifyClickSend.quote(self.user, safe=''),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=''),
        )

        return '{schema}://{auth}{targets}?{params}'.format(
            schema=self.secure_protocol,
            auth=auth,
            targets='/'.join(
                [NotifyClickSend.quote(x, safe='') for x in self.targets]),
            params=NotifyClickSend.urlencode(params),
        )

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.user, self.password)

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        #
        # Factor batch into calculation
        #
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

        # All elements are targets
        results['targets'] = [NotifyClickSend.unquote(results['host'])]

        # All entries after the hostname are additional targets
        results['targets'].extend(
            NotifyClickSend.split_path(results['fullpath']))

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get('batch', False))

        # API Key
        if 'key' in results['qsd'] and len(results['qsd']['key']):
            # Extract the API Key from an argument
            results['password'] = \
                NotifyClickSend.unquote(results['qsd']['key'])

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyClickSend.parse_phone_no(results['qsd']['to'])

        return results
