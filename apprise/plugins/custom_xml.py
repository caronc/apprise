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

import re
import requests

from .. import exception
from .base import NotifyBase
from ..url import PrivacyMode
from ..common import NotifyImageSize
from ..common import NotifyType
from ..locale import gettext_lazy as _


class XMLPayloadField:
    """
    Identifies the fields available in the JSON Payload
    """
    VERSION = 'Version'
    TITLE = 'Subject'
    MESSAGE = 'Message'
    MESSAGETYPE = 'MessageType'


# Defines the method to send the notification
METHODS = (
    'POST',
    'GET',
    'DELETE',
    'PUT',
    'HEAD',
    'PATCH'
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

    # Support attachments
    attachment_support = True

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # Disable throttle rate for JSON requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # XSD Information
    xsd_ver = '1.1'
    xsd_default_url = \
        'https://raw.githubusercontent.com/caronc/apprise/master' \
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
        <Notification{{XSD_URL}}>
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

        # A payload map allows users to over-ride the default mapping if
        # they're detected with the :overide=value.  Normally this would
        # create a new key and assign it the value specified.  However
        # if the key you specify is actually an internally mapped one,
        # then a re-mapping takes place using the value
        self.payload_map = {
            XMLPayloadField.VERSION: XMLPayloadField.VERSION,
            XMLPayloadField.TITLE: XMLPayloadField.TITLE,
            XMLPayloadField.MESSAGE: XMLPayloadField.MESSAGE,
            XMLPayloadField.MESSAGETYPE: XMLPayloadField.MESSAGETYPE,
        }

        self.params = {}
        if params:
            # Store our extra headers
            self.params.update(params)

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        self.payload_overrides = {}
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

                # Any values set in the payload to alter a system related one
                # alters the system key.  Hence :message=msg maps the 'message'
                # variable that otherwise already contains the payload to be
                # 'msg' instead (containing the payload)
                if key in self.payload_map:
                    self.payload_map[key] = v
                    self.payload_overrides[key] = v

                else:
                    self.payload_extras[key] = v

        # Set our xsd url
        self.xsd_url = None if self.payload_overrides or self.payload_extras \
            else self.xsd_default_url.format(version=self.xsd_ver)

        return

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

        payload_base = {}

        for key, value in (
                (XMLPayloadField.VERSION, self.xsd_ver),
                (XMLPayloadField.TITLE, NotifyXML.escape_html(
                    title, whitespace=False)),
                (XMLPayloadField.MESSAGE, NotifyXML.escape_html(
                    body, whitespace=False)),
                (XMLPayloadField.MESSAGETYPE, NotifyXML.escape_html(
                    notify_type, whitespace=False))):

            if not self.payload_map[key]:
                # Do not store element in payload response
                continue
            payload_base[self.payload_map[key]] = value

        # Apply our payload extras
        payload_base.update(
            {k: NotifyXML.escape_html(v, whitespace=False)
                for k, v in self.payload_extras.items()})

        # Base Entres
        xml_base = ''.join(
            ['<{}>{}</{}>'.format(k, v, k) for k, v in payload_base.items()])

        attachments = []
        if attach and self.attachment_support:
            for no, attachment in enumerate(attach, start=1):
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access Custom XML attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                try:
                    # Prepare our Attachment in Base64
                    entry = \
                        '<Attachment filename="{}" mimetype="{}">'.format(
                            NotifyXML.escape_html(
                                attachment.name if attachment.name
                                else f'file{no:03}.dat', whitespace=False),
                            NotifyXML.escape_html(
                                attachment.mimetype, whitespace=False))
                    entry += attachment.base64()
                    entry += '</Attachment>'
                    attachments.append(entry)

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access Custom XML attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                self.logger.debug(
                    'Appending Custom XML attachment {}'.format(
                        attachment.url(privacy=True)))

            # Update our xml_attachments record:
            xml_attachments = \
                '<Attachments format="base64">' + \
                ''.join(attachments) + '</Attachments>'

        re_map = {
            '{{XSD_URL}}':
            f' xmlns:xsi="{self.xsd_url}"' if self.xsd_url else '',
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

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user, self.password, self.host,
            self.port if self.port else (443 if self.secure else 80),
            self.fullpath.rstrip('/'),
        )

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
        params.update(
            {':{}'.format(k): v for k, v in self.payload_overrides.items()})

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
