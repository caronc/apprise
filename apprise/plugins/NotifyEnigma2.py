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

# Sources
# - https://dreambox.de/en/
# - https://dream.reichholf.net/wiki/Hauptseite
# - https://dream.reichholf.net/wiki/Enigma2:WebInterface#Message
# - https://github.com/E2OpenPlugins/e2openplugin-OpenWebif
# - https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/wiki/\
#       OpenWebif-API-documentation#message

import six
import requests
from json import loads

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..AppriseLocale import gettext_lazy as _


class Enigma2MessageType(object):
    # Defines the Enigma2 notification types Apprise can map to
    INFO = 1
    WARNING = 2
    ERROR = 3


# If a mapping fails, the default of Enigma2MessageType.INFO is used
MESSAGE_MAPPING = {
    NotifyType.INFO: Enigma2MessageType.INFO,
    NotifyType.SUCCESS: Enigma2MessageType.INFO,
    NotifyType.WARNING: Enigma2MessageType.WARNING,
    NotifyType.FAILURE: Enigma2MessageType.ERROR,
}


class NotifyEnigma2(NotifyBase):
    """
    A wrapper for Enigma2 Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Enigma2'

    # The services URL
    service_url = 'https://dreambox.de/'

    # The default protocol
    protocol = 'enigma2'

    # The default secure protocol
    secure_protocol = 'enigma2s'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_enigma2'

    # Enigma2 does not support a title
    title_maxlen = 0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    # Throttle a wee-bit to avoid thrashing
    request_rate_per_sec = 0.5

    # Define object templates
    templates = (
        '{schema}://{host}',
        '{schema}://{host}:{port}',
        '{schema}://{user}@{host}',
        '{schema}://{user}@{host}:{port}',
        '{schema}://{user}:{password}@{host}',
        '{schema}://{user}:{password}@{host}:{port}',
        '{schema}://{host}/{fullpath}',
        '{schema}://{host}:{port}/{fullpath}',
        '{schema}://{user}@{host}/{fullpath}',
        '{schema}://{user}@{host}:{port}/{fullpath}',
        '{schema}://{user}:{password}@{host}/{fullpath}',
        '{schema}://{user}:{password}@{host}:{port}/{fullpath}',
    )

    # Define our template tokens
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
        'user': {
            'name': _('Username'),
            'type': 'string',
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
        },
        'fullpath': {
            'name': _('Path'),
            'type': 'string',
        },
    })

    template_args = dict(NotifyBase.template_args, **{
        'timeout': {
            'name': _('Server Timeout'),
            'type': 'int',
            # The number of seconds to display the message for
            'default': 13,
            # -1 means infinit
            'min': -1,
        },
    })

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('HTTP Header'),
            'prefix': '+',
        },
    }

    def __init__(self, timeout=None, headers=None, **kwargs):
        """
        Initialize Enigma2 Object

        headers can be a dictionary of key/value pairs that you want to
        additionally include as part of the server headers to post with
        """
        super(NotifyEnigma2, self).__init__(**kwargs)

        try:
            self.timeout = int(timeout)
            if self.timeout < self.template_args['timeout']['min']:
                # Bulletproof; can't go lower then min value
                self.timeout = self.template_args['timeout']['min']

        except (ValueError, TypeError):
            # Use default timeout
            self.timeout = self.template_args['timeout']['default']

        self.fullpath = kwargs.get('fullpath')
        if not isinstance(self.fullpath, six.string_types):
            self.fullpath = '/'

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
            'timeout': str(self.timeout),
        }

        # Append our headers into our args
        args.update({'+{}'.format(k): v for k, v in self.headers.items()})

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyEnigma2.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyEnigma2.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}{fullpath}?{args}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=NotifyEnigma2.quote(self.host, safe=''),
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            fullpath=NotifyEnigma2.quote(self.fullpath, safe='/'),
            args=NotifyEnigma2.urlencode(args),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Enigma2 Notification
        """

        # prepare Enigma2 Object
        headers = {
            'User-Agent': self.app_id,
        }

        params = {
            'text': body,
            'type': MESSAGE_MAPPING.get(
                notify_type, Enigma2MessageType.INFO),
            'timeout': self.timeout,
        }

        # Apply any/all header over-rides defined
        headers.update(self.headers)

        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Set our schema
        schema = 'https' if self.secure else 'http'

        url = '%s://%s' % (schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        # Prepare our message URL
        url += self.fullpath.rstrip('/') + '/api/message'

        self.logger.debug('Enigma2 POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Enigma2 Parameters: %s' % str(params))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.get(
                url,
                params=params,
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyEnigma2.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Enigma2 notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            # We were able to post our message; now lets evaluate the response
            try:
                # Acquire our result
                result = loads(r.content).get('result', False)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None

                # We could not parse JSON response.
                result = False

            if not result:
                self.logger.warning(
                    'Failed to send Enigma2 notification: '
                    'There was no server acknowledgement.')
                self.logger.debug('Response Details:\r\n{}'.format(r.content))
                # Return; we're done
                return False

            self.logger.info('Sent Enigma2 notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Enigma2 '
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

        """
        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set
        results['headers'] = results['qsd-']
        results['headers'].update(results['qsd+'])

        # Tidy our header entries by unquoting them
        results['headers'] = {
            NotifyEnigma2.unquote(x): NotifyEnigma2.unquote(y)
            for x, y in results['headers'].items()}

        # Save timeout value (if specified)
        if 'timeout' in results['qsd'] and len(results['qsd']['timeout']):
            results['timeout'] = results['qsd']['timeout']

        return results
