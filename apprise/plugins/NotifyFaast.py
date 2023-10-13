# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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

import requests

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _
from ..utils import validate_regex


class NotifyFaast(NotifyBase):
    """
    A wrapper for Faast Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Faast'

    # The services URL
    service_url = 'http://www.faast.io/'

    # The default protocol (this is secure for faast)
    protocol = 'faast'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_faast'

    # Faast uses the http protocol with JSON requests
    notify_url = 'https://www.appnotifications.com/account/notifications.json'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # Define object templates
    templates = (
        '{schema}://{authtoken}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'authtoken': {
            'name': _('Authorization Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
    })

    def __init__(self, authtoken, include_image=True, **kwargs):
        """
        Initialize Faast Object
        """
        super().__init__(**kwargs)

        # Store the Authentication Token
        self.authtoken = validate_regex(authtoken)
        if not self.authtoken:
            msg = 'An invalid Faast Authentication Token ' \
                  '({}) was specified.'.format(authtoken)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Associate an image with our post
        self.include_image = include_image

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Faast Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'multipart/form-data'
        }

        # prepare JSON Object
        payload = {
            'user_credentials': self.authtoken,
            'title': title,
            'message': body,
        }

        # Acquire our image if we're configured to do so
        image_url = None if not self.include_image \
            else self.image_url(notify_type)

        if image_url:
            payload['icon_url'] = image_url

        self.logger.debug('Faast POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Faast Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyFaast.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Faast notification:'
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Faast notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Faast notification.',
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{authtoken}/?{params}'.format(
            schema=self.protocol,
            authtoken=self.pprint(self.authtoken, privacy, safe=''),
            params=NotifyFaast.urlencode(params),
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

        # Store our authtoken using the host
        results['authtoken'] = NotifyFaast.unquote(results['host'])

        # Include image with our post
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        return results
