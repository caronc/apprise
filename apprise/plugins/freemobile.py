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

# Free Mobile
#   1. Visit https://mobile.free.fr/

# the URL will look something like this:
#      https://smsapi.free-mobile.fr/sendmsg
#

import requests
from json import dumps

from .base import NotifyBase
from ..common import NotifyType
from ..locale import gettext_lazy as _


class NotifyFreeMobile(NotifyBase):
    """
    A wrapper for Free-Mobile Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = _('Free-Mobile')

    # The services URL
    service_url = 'https://mobile.free.fr/'

    # The default secure protocol
    secure_protocol = 'freemobile'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_freemobile'

    # Plain Text Notification URL
    notify_url = 'https://smsapi.free-mobile.fr/sendmsg'

    # Define object templates
    templates = (
        '{schema}://{user}@{password}',
    )

    # The title is not used
    title_maxlen = 0

    # SMS Messages are restricted in size
    body_maxlen = 160

    # Define our tokens; these are the minimum tokens required required to
    # be passed into this function (as arguments). The syntax appends any
    # previously defined in the base package and builds onto them
    template_tokens = dict(NotifyBase.template_tokens, **{
        'user': {
            'name': _('Username'),
            'type': 'string',
            'required': True,
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
            'required': True,
        },
    })

    def __init__(self, **kwargs):
        """
        Initialize Free Mobile Object
        """
        super().__init__(**kwargs)

        if not (self.user and self.password):
            msg = 'A FreeMobile user and password ' \
                  'combination was not provided.'
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.user, self.password)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Prepare our parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return '{schema}://{user}@{password}/?{params}'.format(
            schema=self.secure_protocol,
            user=self.user,
            password=self.pprint(self.password, privacy, safe=''),
            params=NotifyFreeMobile.urlencode(params),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Send our notification
        """

        # prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # Prepare our payload
        payload = {
            'user': self.user,
            'pass': self.password,
            'msg': body
        }

        self.logger.debug('Free Mobile GET URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate))
        self.logger.debug('Free Mobile Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload).encode('utf-8'),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyFreeMobile.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Free Mobile notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Free Mobile notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Free Mobile '
                'notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """

        # parse_url already handles getting the `user` and `password` fields
        # populated.
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The hostname can act as the password if specified and a password
        # was otherwise not (specified):
        if not results.get('password'):
            results['password'] = NotifyFreeMobile.unquote(results['host'])

        return results
