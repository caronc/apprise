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
from base64 import b64encode

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import parse_phone_no
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _

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
        '{schema}://{user}:{password}@{targets}',
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
            'Authorization': 'Basic {}'.format(
                b64encode('{}:{}'.format(
                    self.user, self.password).encode('utf-8'))),
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

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyClickSend.parse_phone_no(results['qsd']['to'])

        return results
