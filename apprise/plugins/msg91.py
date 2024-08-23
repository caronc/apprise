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

# Create an account https://msg91.com/ if you don't already have one
#
# Get your (authkey) from the dashboard here:
#   - https://world.msg91.com/user/index.php#api
#
# Note: You will need to define a template for this to work
#
# Get details on the API used in this plugin here:
#   - https://docs.msg91.com/reference/send-sms
import re
import requests
from json import dumps
from .base import NotifyBase
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import parse_phone_no, parse_bool
from ..utils import validate_regex
from ..locale import gettext_lazy as _


class MSG91PayloadField:
    """
    Identifies the fields available in the JSON Payload
    """
    BODY = 'body'
    MESSAGETYPE = 'type'


# Add entries here that are reserved
RESERVED_KEYWORDS = ('mobiles', )


class NotifyMSG91(NotifyBase):
    """
    A wrapper for MSG91 Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'MSG91'

    # The services URL
    service_url = 'https://msg91.com'

    # The default protocol
    secure_protocol = 'msg91'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_msg91'

    # MSG91 uses the http protocol with JSON requests
    notify_url = 'https://control.msg91.com/api/v5/flow/'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Our supported mappings and component keys
    component_key_re = re.compile(
        r'(?P<key>((?P<id>[a-z0-9_-])?|(?P<map>body|type)))', re.IGNORECASE)

    # Define object templates
    templates = (
        '{schema}://{template}@{authkey}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'template': {
            'name': _('Template ID'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[a-z0-9 _-]+$', 'i'),
        },
        'authkey': {
            'name': _('Authentication Key'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[a-z0-9]+$', 'i'),
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
        'short_url': {
            'name': _('Short URL'),
            'type': 'bool',
            'default': False,
        },
    })

    # Define any kwargs we're using
    template_kwargs = {
        'template_mapping': {
            'name': _('Template Mapping'),
            'prefix': ':',
        },
    }

    def __init__(self, template, authkey, targets=None, short_url=None,
                 template_mapping=None, **kwargs):
        """
        Initialize MSG91 Object
        """
        super().__init__(**kwargs)

        # Authentication Key (associated with project)
        self.authkey = validate_regex(
            authkey, *self.template_tokens['authkey']['regex'])
        if not self.authkey:
            msg = 'An invalid MSG91 Authentication Key ' \
                  '({}) was specified.'.format(authkey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Template ID
        self.template = validate_regex(
            template, *self.template_tokens['template']['regex'])
        if not self.template:
            msg = 'An invalid MSG91 Template ID ' \
                  '({}) was specified.'.format(template)
            self.logger.warning(msg)
            raise TypeError(msg)

        if short_url is None:
            self.short_url = self.template_args['short_url']['default']

        else:
            self.short_url = parse_bool(short_url)

        # Parse our targets
        self.targets = list()

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

        self.template_mapping = {}
        if template_mapping:
            # Store our extra payload entries
            self.template_mapping.update(template_mapping)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform MSG91 Notification
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning('There were no MSG91 targets to notify.')
            return False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'authkey': self.authkey,
        }

        # Base
        recipient_payload = {
            'mobiles': None,
            # Keyword Tokens
            MSG91PayloadField.BODY: body,
            MSG91PayloadField.MESSAGETYPE: notify_type,
        }

        # Prepare Recipient Payload Object
        for key, value in self.template_mapping.items():

            if key in RESERVED_KEYWORDS:
                self.logger.warning(
                    'Ignoring MSG91 custom payload entry %s', key)
                continue

            if key in recipient_payload:
                if not value:
                    # Do not store element in payload response
                    del recipient_payload[key]

                else:
                    # Re-map
                    recipient_payload[value] = recipient_payload[key]
                    del recipient_payload[key]

            else:
                # Append entry
                recipient_payload[key] = value

        # Prepare our recipients
        recipients = []
        for target in self.targets:
            recipient = recipient_payload.copy()
            recipient['mobiles'] = target
            recipients.append(recipient)

        # Prepare our payload
        payload = {
            'template_id': self.template,
            'short_url': 1 if self.short_url else 0,
            # target phone numbers are sent with a comma delimiter
            'recipients': recipients,
        }

        # Some Debug Logging
        self.logger.debug('MSG91 POST URL: {} (cert_verify={})'.format(
            self.notify_url, self.verify_certificate))
        self.logger.debug('MSG91 Payload: {}' .format(payload))

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
                    NotifyMSG91.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send MSG91 notification to {}: '
                    '{}{}error={}.'.format(
                        ','.join(self.targets),
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))
                return False

            else:
                self.logger.info(
                    'Sent MSG91 notification to %s.' % ','.join(self.targets))

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending MSG91:%s '
                'notification.' % ','.join(self.targets)
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            return False

        return True

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.template, self.authkey)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'short_url': str(self.short_url),
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Payload body extras prefixed with a ':' sign
        # Append our payload extras into our parameters
        params.update(
            {':{}'.format(k): v for k, v in self.template_mapping.items()})

        return '{schema}://{template}@{authkey}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            template=self.pprint(self.template, privacy, safe=''),
            authkey=self.pprint(self.authkey, privacy, safe=''),
            targets='/'.join(
                [NotifyMSG91.quote(x, safe='') for x in self.targets]),
            params=NotifyMSG91.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        targets = len(self.targets)
        return targets if targets > 0 else 1

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

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = NotifyMSG91.split_path(results['fullpath'])

        # The hostname is our authentication key
        results['authkey'] = NotifyMSG91.unquote(results['host'])

        # The template id is kept in the user field
        results['template'] = NotifyMSG91.unquote(results['user'])

        if 'short_url' in results['qsd'] and len(results['qsd']['short_url']):
            results['short_url'] = parse_bool(results['qsd']['short_url'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyMSG91.parse_phone_no(results['qsd']['to'])

        # store any additional payload extra's defined
        results['template_mapping'] = {
            NotifyMSG91.unquote(x): NotifyMSG91.unquote(y)
            for x, y in results['qsd:'].items()
        }

        return results
