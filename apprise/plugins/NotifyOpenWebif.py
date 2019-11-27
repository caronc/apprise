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
# - https://github.com/E2OpenPlugins/e2openplugin-OpenWebif
# - https://github.com/E2OpenPlugins/e2openplugin-OpenWebif/wiki/\
#       OpenWebif-API-documentation#message
#
import six
import requests
from json import dumps
from json import loads

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..AppriseLocale import gettext_lazy as _


class OpenWebifMessageType(object):
    # Defines the OpenWebif notification types Apprise can map to
    INFO = 1
    WARNING = 2
    ERROR = 3


# If a mapping fails, the default of OpenWebifMessageType.INFO is used
MESSAGE_MAPPING = {
    NotifyType.INFO: OpenWebifMessageType.INFO,
    NotifyType.SUCCESS: OpenWebifMessageType.INFO,
    NotifyType.WARNING: OpenWebifMessageType.WARNING,
    NotifyType.FAILURE: OpenWebifMessageType.ERROR,
}


class NotifyOpenWebif(NotifyBase):
    """
    A wrapper for OpenWebif Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'OpenWebif'

    # The services URL
    service_url = 'https://github.com/E2OpenPlugins/e2openplugin-OpenWebif'

    # The default protocol
    protocol = 'owebif'

    # The default secure protocol
    secure_protocol = 'owebifs'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_openwebif'

    # OpenWebif does not support a title
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
            'min': 5,
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
        Initialize OpenWebif Object

        headers can be a dictionary of key/value pairs that you want to
        additionally include as part of the server headers to post with
        """
        super(NotifyOpenWebif, self).__init__(**kwargs)

        try:
            self.timeout = int(timeout)

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
                user=NotifyOpenWebif.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyOpenWebif.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}{fullpath}/?{args}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=NotifyOpenWebif.quote(self.host, safe=''),
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            fullpath=NotifyOpenWebif.quote(self.fullpath, safe='/'),
            args=NotifyOpenWebif.urlencode(args),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform OpenWebif Notification
        """

        # prepare OpenWebif Object
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        payload = {
            'text': body,
            'type': MESSAGE_MAPPING.get(
                notify_type, OpenWebifMessageType.INFO)
        }

        if self.timeout:
            # Default timeout value if one is specified
            payload['timeout'] = self.timeout

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
        url += self.fullpath + '/api/message'

        self.logger.debug('OpenWebif POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('OpenWebif Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyOpenWebif.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send OpenWebif notification: '
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
                    'Failed to send OpenWebif notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))
                # Return; we're done
                return False

            self.logger.info('Sent OpenWebif notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending OpenWebif '
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
            NotifyOpenWebif.unquote(x): NotifyOpenWebif.unquote(y)
            for x, y in results['headers'].items()}

        return results
