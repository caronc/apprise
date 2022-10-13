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

import re
import requests
import base64

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyImageSize
from ..common import NotifyType
from ..AppriseLocale import gettext_lazy as _


# Defines the method to send the notification
METHODS = (
    'POST',
    'GET',
    'DELETE',
    'PUT',
    'HEAD'
)


class NotifyXML(NotifyBase):
    """
    A wrapper for XML Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'XML'

    # The default protocol
    protocol = 'xml'

    # The default secure protocol
    secure_protocol = 'xmls'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_Custom_XML'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # Disable throttle rate for JSON requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # XSD Information
    xsd_ver = '1.1'
    xsd_url = 'https://raw.githubusercontent.com/caronc/apprise/master' \
        '/apprise/assets/NotifyXML-{version}.xsd'

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
        Initialize XML Object

        headers can be a dictionary of key/value pairs that you want to
        additionally include as part of the server headers to post with

        """
        super().__init__(**kwargs)

        self.payload = """<?xml version='1.0' encoding='utf-8'?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <soapenv:Body>
        <Notification xmlns:xsi="{{XSD_URL}}">
            {{CORE}}
            {{ATTACHMENTS}}
       </Notification>
    </soapenv:Body>
</soapenv:Envelope>"""

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
            # Store our extra payload entries (but tidy them up since they will
            # become XML Keys (they can't contain certain characters
            for k, v in payload.items():
                key = re.sub(r'[^A-Za-z0-9_-]*', '', k)
                if not key:
                    self.logger.warning(
                        'Ignoring invalid XML Stanza element name({})'
                        .format(k))
                    continue
                self.payload_extras[key] = v

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
                user=NotifyXML.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyXML.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}{fullpath}?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            fullpath=NotifyXML.quote(self.fullpath, safe='/')
            if self.fullpath else '/',
            params=NotifyXML.urlencode(params),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform XML Notification
        """

        # Prepare HTTP Headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/xml'
        }

        # Apply any/all header over-rides defined
        headers.update(self.headers)

        # Our XML Attachmement subsitution
        xml_attachments = ''

        # Our Payload Base
        payload_base = {
            'Version': self.xsd_ver,
            'Subject': NotifyXML.escape_html(title, whitespace=False),
            'MessageType': NotifyXML.escape_html(
                notify_type, whitespace=False),
            'Message': NotifyXML.escape_html(body, whitespace=False),
        }

        # Apply our payload extras
        payload_base.update(
            {k: NotifyXML.escape_html(v, whitespace=False)
                for k, v in self.payload_extras.items()})

        # Base Entres
        xml_base = ''.join(
            ['<{}>{}</{}>'.format(k, v, k) for k, v in payload_base.items()])

        attachments = []
        if attach:
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
                        # Prepare our Attachment in Base64
                        entry = \
                            '<Attachment filename="{}" mimetype="{}">'.format(
                                NotifyXML.escape_html(
                                    attachment.name, whitespace=False),
                                NotifyXML.escape_html(
                                    attachment.mimetype, whitespace=False))
                        entry += base64.b64encode(f.read()).decode('utf-8')
                        entry += '</Attachment>'
                        attachments.append(entry)

                except (OSError, IOError) as e:
                    self.logger.warning(
                        'An I/O error occurred while reading {}.'.format(
                            attachment.name if attachment else 'attachment'))
                    self.logger.debug('I/O Exception: %s' % str(e))
                    return False

            # Update our xml_attachments record:
            xml_attachments = \
                '<Attachments format="base64">' + \
                ''.join(attachments) + '</Attachments>'

        re_map = {
            '{{XSD_URL}}': self.xsd_url.format(version=self.xsd_ver),
            '{{ATTACHMENTS}}': xml_attachments,
            '{{CORE}}': xml_base,
        }

        # Iterate over above list and store content accordingly
        re_table = re.compile(
            r'(' + '|'.join(re_map.keys()) + r')',
            re.IGNORECASE,
        )

        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Set our schema
        schema = 'https' if self.secure else 'http'

        url = '%s://%s' % (schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        url += self.fullpath
        payload = re_table.sub(lambda x: re_map[x.group()], self.payload)

        self.logger.debug('XML POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))

        self.logger.debug('XML Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        if self.method == 'GET':
            method = requests.get

        elif self.method == 'PUT':
            method = requests.put

        elif self.method == 'DELETE':
            method = requests.delete

        elif self.method == 'HEAD':
            method = requests.head

        else:  # POST
            method = requests.post

        try:
            r = method(
                url,
                data=payload,
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code < 200 or r.status_code >= 300:
                # We had a problem
                status_str = \
                    NotifyXML.http_response_code_lookup(r.status_code)

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
                self.logger.info('Sent XML %s notification.', self.method)

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending XML '
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
        results['payload'] = {NotifyXML.unquote(x): NotifyXML.unquote(y)
                              for x, y in results['qsd:'].items()}

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set and tidy entries by unquoting them
        results['headers'] = {NotifyXML.unquote(x): NotifyXML.unquote(y)
                              for x, y in results['qsd+'].items()}

        # Add our GET paramters in the event the user wants to pass these along
        results['params'] = {NotifyXML.unquote(x): NotifyXML.unquote(y)
                             for x, y in results['qsd-'].items()}

        # Set method if not otherwise set
        if 'method' in results['qsd'] and len(results['qsd']['method']):
            results['method'] = NotifyXML.unquote(results['qsd']['method'])

        return results
