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
import base64
from json import dumps

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyImageSize
from ..common import NotifyType
from ..AppriseLocale import gettext_lazy as _


class JSONPayloadField:
    """
    Identifies the fields available in the JSON Payload
    """
    VERSION = 'version'
    TITLE = 'title'
    MESSAGE = 'message'
    ATTACHMENTS = 'attachments'
    MESSAGETYPE = 'type'


# Defines the method to send the notification
METHODS = (
    'POST',
    'GET',
    'DELETE',
    'PUT',
    'HEAD',
    'PATCH'
)


class NotifyJSON(NotifyBase):
    """
    A wrapper for JSON Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'JSON'

    # The default protocol
    protocol = 'json'

    # The default secure protocol
    secure_protocol = 'jsons'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_Custom_JSON'

    # Support attachments
    attachment_support = True

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # Disable throttle rate for JSON requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # Define the JSON version to place in all payloads
    # Version: Major.Minor,  Major is only updated if the entire schema is
    # changed. If just adding new items (or removing old ones, only increment
    # the Minor!
    json_version = '1.0'

    # Define object templates
    templates = (
        '{schema}://{host}',
        '{schema}://{host}:{port}',
        '{schema}://{user}@{host}',
        '{schema}://{user}@{host}:{port}',
        '{schema}://{user}:{password}@{host}',
        '{schema}://{user}:{password}@{host}:{port}',
    )

    # Define our tokens; these are the minimum tokens required required to
    # be passed into this function (as arguments). The syntax appends any
    # previously defined in the base package and builds onto them
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

    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'method': {
            'name': _('Fetch Method'),
            'type': 'choice:string',
            'values': METHODS,
            'default': METHODS[0],
        },
    })

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('HTTP Header'),
            'prefix': '+',
        },
        'payload': {
            'name': _('Payload Extras'),
            'prefix': ':',
        },
        'params': {
            'name': _('GET Params'),
            'prefix': '-',
        },
    }

    def __init__(self, headers=None, method=None, payload=None, params=None,
                 **kwargs):
        """
        Initialize JSON Object

        headers can be a dictionary of key/value pairs that you want to
        additionally include as part of the server headers to post with

        """
        super().__init__(**kwargs)

        self.fullpath = kwargs.get('fullpath')
        if not isinstance(self.fullpath, str):
            self.fullpath = ''

        self.method = self.template_args['method']['default'] \
            if not isinstance(method, str) else method.upper()

        if self.method not in METHODS:
            msg = 'The method specified ({}) is invalid.'.format(method)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.params = {}
        if params:
            # Store our extra headers
            self.params.update(params)

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        self.payload_extras = {}
        if payload:
            # Store our extra payload entries
            self.payload_extras.update(payload)

        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'method': self.method,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Append our headers into our parameters
        params.update({'+{}'.format(k): v for k, v in self.headers.items()})

        # Append our GET params into our parameters
        params.update({'-{}'.format(k): v for k, v in self.params.items()})

        # Append our payload extra's into our parameters
        params.update(
            {':{}'.format(k): v for k, v in self.payload_extras.items()})

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyJSON.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyJSON.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}{fullpath}?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            fullpath=NotifyJSON.quote(self.fullpath, safe='/')
            if self.fullpath else '/',
            params=NotifyJSON.urlencode(params),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform JSON Notification
        """

        # Prepare HTTP Headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        # Apply any/all header over-rides defined
        headers.update(self.headers)

        # Track our potential attachments
        attachments = []
        if attach and self.attachment_support:
            for attachment in attach:
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                try:
                    with open(attachment.path, 'rb') as f:
                        # Output must be in a DataURL format (that's what
                        # PushSafer calls it):
                        attachments.append({
                            'filename': attachment.name,
                            'base64': base64.b64encode(f.read())
                            .decode('utf-8'),
                            'mimetype': attachment.mimetype,
                        })

                except (OSError, IOError) as e:
                    self.logger.warning(
                        'An I/O error occurred while reading {}.'.format(
                            attachment.name if attachment else 'attachment'))
                    self.logger.debug('I/O Exception: %s' % str(e))
                    return False

        # Prepare JSON Object
        payload = {
            JSONPayloadField.VERSION: self.json_version,
            JSONPayloadField.TITLE: title,
            JSONPayloadField.MESSAGE: body,
            JSONPayloadField.ATTACHMENTS: attachments,
            JSONPayloadField.MESSAGETYPE: notify_type,
        }

        for key, value in self.payload_extras.items():

            if key in payload:
                if not value:
                    # Do not store element in payload response
                    del payload[key]

                else:
                    # Re-map
                    payload[value] = payload[key]
                    del payload[key]

            else:
                # Append entry
                payload[key] = value

        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Set our schema
        schema = 'https' if self.secure else 'http'

        url = '%s://%s' % (schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        url += self.fullpath

        self.logger.debug('JSON POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('JSON Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        if self.method == 'GET':
            method = requests.get

        elif self.method == 'PUT':
            method = requests.put

        elif self.method == 'PATCH':
            method = requests.patch

        elif self.method == 'DELETE':
            method = requests.delete

        elif self.method == 'HEAD':
            method = requests.head

        else:  # POST
            method = requests.post

        try:
            r = method(
                url,
                data=dumps(payload),
                params=self.params,
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code < 200 or r.status_code >= 300:
                # We had a problem
                status_str = \
                    NotifyJSON.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send JSON %s notification: %s%serror=%s.',
                    self.method,
                    status_str,
                    ', ' if status_str else '',
                    str(r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent JSON %s notification.', self.method)

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending JSON '
                'notification to %s.' % self.host)
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
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # store any additional payload extra's defined
        results['payload'] = {NotifyJSON.unquote(x): NotifyJSON.unquote(y)
                              for x, y in results['qsd:'].items()}

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set and tidy entries by unquoting them
        results['headers'] = {NotifyJSON.unquote(x): NotifyJSON.unquote(y)
                              for x, y in results['qsd+'].items()}

        # Add our GET paramters in the event the user wants to pass these along
        results['params'] = {NotifyJSON.unquote(x): NotifyJSON.unquote(y)
                             for x, y in results['qsd-'].items()}

        # Set method if not otherwise set
        if 'method' in results['qsd'] and len(results['qsd']['method']):
            results['method'] = NotifyJSON.unquote(results['qsd']['method'])

        return results
