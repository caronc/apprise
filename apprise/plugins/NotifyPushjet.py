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

import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..AppriseLocale import gettext_lazy as _


class NotifyPushjet(NotifyBase):
    """
    A wrapper for Pushjet Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Pushjet'

    # The default protocol
    protocol = 'pjet'

    # The default secure protocol
    secure_protocol = 'pjets'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pushjet'

    # Disable throttle rate for Pushjet requests since they are normally
    # local anyway (the remote/online service is no more)
    request_rate_per_sec = 0

    # Define object templates
    templates = (
        '{schema}://{host}:{port}/{secret_key}',
        '{schema}://{host}/{secret_key}',
        '{schema}://{user}:{password}@{host}:{port}/{secret_key}',
        '{schema}://{user}:{password}@{host}/{secret_key}',

        # Kept for backwards compatibility; will be depricated eventually
        '{schema}://{secret_key}@{host}',
        '{schema}://{secret_key}@{host}:{port}',
    )

    # Define our tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'host': {
            'name': _('Hostname'),
            'type': 'string',
            'required': True,
        },
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
        },
        'secret_key': {
            'name': _('Secret Key'),
            'type': 'string',
            'required': True,
            'private': True,
        },
        'user': {
            'name': _('Username'),
            'type': 'string',
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
        },
    })

    template_args = dict(NotifyBase.template_args, **{
        'secret': {
            'alias_of': 'secret_key',
        },
    })

    def __init__(self, secret_key, **kwargs):
        """
        Initialize Pushjet Object
        """
        super(NotifyPushjet, self).__init__(**kwargs)

        if not secret_key:
            # You must provide a Pushjet key to work with
            msg = 'You must specify a Pushjet Secret Key.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # store our key
        self.secret_key = secret_key

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'secret': self.secret_key,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        default_port = 443 if self.secure else 80

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyPushjet.quote(self.user, safe=''),
                password=NotifyPushjet.quote(self.password, safe=''),
            )

        return '{schema}://{auth}{hostname}{port}/?{args}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=NotifyPushjet.quote(self.host, safe=''),
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            args=NotifyPushjet.urlencode(args),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Pushjet Notification
        """

        params = {
            'secret': self.secret_key,
        }

        # prepare Pushjet Object
        payload = {
            'message': body,
            'title': title,
            'link': None,
            'level': None,
        }

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
        }

        auth = None
        if self.user:
            auth = (self.user, self.password)

        notify_url = '{schema}://{host}{port}/message/'.format(
            schema="https" if self.secure else "http",
            host=self.host,
            port=':{}'.format(self.port) if self.port else '')

        self.logger.debug('Pushjet POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('Pushjet Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url,
                params=params,
                data=dumps(payload),
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyPushjet.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Pushjet notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Pushjet notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Pushjet '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        Syntax:
           pjet://hostname/secret_key
           pjet://hostname:port/secret_key
           pjet://user:pass@hostname/secret_key
           pjet://user:pass@hostname:port/secret_key
           pjets://hostname/secret_key
           pjets://hostname:port/secret_key
           pjets://user:pass@hostname/secret_key
           pjets://user:pass@hostname:port/secret_key

        Legacy (Depricated) Syntax:
           pjet://secret_key@hostname
           pjet://secret_key@hostname:port
           pjets://secret_key@hostname
           pjets://secret_key@hostname:port

        """
        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        try:
            # Retrieve our secret_key from the first entry in the url path
            results['secret_key'] = \
                NotifyPushjet.split_path(results['fullpath'])[0]

        except IndexError:
            # no secret key specified
            results['secret_key'] = None

        # Allow over-riding the secret by specifying it as an argument
        # this allows people who have http-auth infront to login
        # through it in addition to supporting the secret key
        if 'secret' in results['qsd'] and len(results['qsd']['secret']):
            results['secret_key'] = \
                NotifyPushjet.parse_list(results['qsd']['secret'])

        if results.get('secret_key') is None:
            # Deprication Notice issued for v0.7.9
            NotifyPushjet.logger.deprecate(
                'The Pushjet URL contains secret_key in the user field'
                ' which will be deprecated in an upcoming '
                'release. Please place this in the path of the URL instead.'
            )

            # Store it as it's value based on the user field
            results['secret_key'] = \
                NotifyPushjet.unquote(results.get('user'))

            # there is no way http-auth is enabled, be sure to unset the
            # current defined user (if present). This is done due to some
            # logic that takes place in the send() since we support http-auth.
            results['user'] = None
            results['password'] = None

        return results
