# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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
#
# API Source:
#   https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
#
# 1. Register a developer account with Meta:
#  https://developers.facebook.com/docs/whatsapp/cloud-api/get-started
# 2. Enable 2 Factor Authentication (2FA) with your account (if not done
#  already)
# 3. Create a App using WhatsApp Product.  There are 2 to create an app from
#   Do NOT chose the WhatsApp Webhook one (choose the other)
#
#  When you click on the API Setup section of your new app you need to record
#  both the access token and the From Phone Number ID.  Note that this not the
#  from phone number itself, but it's ID.  It's displayed below and contains
#  way more numbers then your typical phone number

import re
import requests
from json import loads, dumps
from .base import NotifyBase
from ..common import NotifyType
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from ..locale import gettext_lazy as _


class NotifyWhatsApp(NotifyBase):
    """
    A wrapper for WhatsApp Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'WhatsApp'

    # The services URL
    service_url = \
        'https://developers.facebook.com/docs/whatsapp/cloud-api/get-started'

    # All notification requests are secure
    secure_protocol = 'whatsapp'

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # Facebook Graph version
    fb_graph_version = 'v17.0'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_whatsapp'

    # WhatsApp Message Notification URL
    notify_url = 'https://graph.facebook.com/{fb_ver}/{phone_id}/messages'

    # The maximum length of the body
    body_maxlen = 1024

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{token}@{from_phone_id}/{targets}',
        '{schema}://{template}:{token}@{from_phone_id}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'token': {
            'name': _('Access Token'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[a-z0-9]+$', 'i'),
        },
        'template': {
            'name': _('Template Name'),
            'type': 'string',
            'required': False,
            'regex': (r'^[^\s]+$', 'i'),
        },
        'from_phone_id': {
            'name': _('From Phone ID'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[0-9]+$', 'i'),
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
        },
        'language': {
            'name': _('Language'),
            'type': 'string',
            'default': 'en_US',
            'regex': (r'^[^0-9\s]+$', 'i'),
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'from': {
            'alias_of': 'from_phone_id',
        },
        'token': {
            'alias_of': 'token',
        },
        'template': {
            'alias_of': 'template',
        },
        'lang': {
            'alias_of': 'language',
        },
    })

    # Our supported mappings and component keys
    component_key_re = re.compile(
        r'(?P<key>((?P<id>[1-9][0-9]*)|(?P<map>body|type)))', re.IGNORECASE)

    # Define any kwargs we're using
    template_kwargs = {
        'template_mapping': {
            'name': _('Template Mapping'),
            'prefix': ':',
        },
    }

    def __init__(self, token, from_phone_id, template=None, targets=None,
                 language=None, template_mapping=None, **kwargs):
        """
        Initialize WhatsApp Object
        """
        super().__init__(**kwargs)

        # The Access Token associated with the account
        self.token = validate_regex(
            token, *self.template_tokens['token']['regex'])
        if not self.token:
            msg = 'An invalid WhatsApp Access Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The From Phone ID associated with the account
        self.from_phone_id = validate_regex(
            from_phone_id, *self.template_tokens['from_phone_id']['regex'])
        if not self.from_phone_id:
            msg = 'An invalid WhatsApp From Phone ID ' \
                  '({}) was specified.'.format(from_phone_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The template to associate with the message
        if template:
            self.template = validate_regex(
                template, *self.template_tokens['template']['regex'])
            if not self.template:
                msg = 'An invalid WhatsApp Template Name ' \
                      '({}) was specified.'.format(template)
                self.logger.warning(msg)
                raise TypeError(msg)

            # The Template language Code to use
            if language:
                self.language = validate_regex(
                    language, *self.template_tokens['language']['regex'])
                if not self.language:
                    msg = 'An invalid WhatsApp Template Language Code ' \
                          '({}) was specified.'.format(language)
                    self.logger.warning(msg)
                    raise TypeError(msg)
            else:
                self.language = self.template_tokens['language']['default']
        else:
            #
            # Message Mode
            #
            self.template = None

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
            self.targets.append('+{}'.format(result['full']))

        self.template_mapping = {}
        if template_mapping:
            # Store our extra payload entries
            self.template_mapping.update(template_mapping)

        # Validate Mapping and prepare Components
        self.components = dict()
        self.component_keys = list()
        for key, val in self.template_mapping.items():
            matched = self.component_key_re.match(key)
            if not matched:
                msg = 'An invalid Template Component ID ' \
                      '({}) was specified.'.format(key)
                self.logger.warning(msg)
                raise TypeError(msg)

            if matched.group('id'):
                #
                # Manual Component Assigment (by id)
                #
                index = matched.group('id')
                map_to = {
                    "type": "text",
                    "text": val,
                }

            else:  # matched.group('map')
                map_to = matched.group('map').lower()
                matched = self.component_key_re.match(val)
                if not (matched and matched.group('id')):
                    msg = 'An invalid Template Component Mapping ' \
                        '(:{}={}) was specified.'.format(key, val)
                    self.logger.warning(msg)
                    raise TypeError(msg)
                index = matched.group('id')

            if index in self.components:
                msg = 'The Template Component index ' \
                      '({}) was already assigned.'.format(key)
                self.logger.warning(msg)
                raise TypeError(msg)

            self.components[index] = map_to
            self.component_keys = self.components.keys()
            # Adjust sorting and assume that the user put the order correctly;
            # if not Facebook just won't be very happy and will reject the
            # message
            sorted(self.component_keys)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform WhatsApp Notification
        """

        if not self.targets:
            self.logger.warning(
                'There are no valid WhatsApp targets to notify.')
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our URL
        url = self.notify_url.format(
            fb_ver=self.fb_graph_version,
            phone_id=self.from_phone_id,
        )

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}',
        }

        payload = {
            'messaging_product': 'whatsapp',
            # The To gets populated in the loop below
            'to': None,
        }

        if not self.template:
            #
            # Send Message
            #
            payload.update({
                'recipient_type': "individual",
                'type': 'text',
                'text': {"body": body},
            })

        else:
            #
            # Send Template
            #
            payload.update({
                'type': 'template',
                "template": {
                    "name": self.template,
                    "language": {"code": self.language},
                },
            })

            if self.components:
                payload['template']['components'] = [
                    {
                        "type": "body",
                        "parameters": [],
                    }
                ]
                for key in self.component_keys:
                    if isinstance(self.components[key], dict):
                        # Manual Assignment
                        payload['template']['components'][0]["parameters"]\
                            .append(self.components[key])
                        continue

                    # Mapping of body and/or notify type
                    payload['template']['components'][0]["parameters"].append({
                        "type": "text",
                        "text": body if self.components[key] == 'body'
                        else notify_type,
                    })

        # Create a copy of the targets list
        targets = list(self.targets)

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our user
            payload['to'] = target

            # Some Debug Logging
            self.logger.debug('WhatsApp POST URL: {} (cert_verify={})'.format(
                url, self.verify_certificate))
            self.logger.debug('WhatsApp Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code not in (
                        requests.codes.created, requests.codes.ok):
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(r.status_code)

                    # set up our status code to use
                    status_code = r.status_code

                    try:
                        # Update our status response if we can
                        json_response = loads(r.content)
                        status_code = \
                            json_response['error'].get('code', status_code)
                        status_str = \
                            json_response['error'].get('message', status_str)

                    except (AttributeError, TypeError, ValueError, KeyError):
                        # KeyError = r.content is parseable but does not
                        #            contain 'error'
                        # ValueError = r.content is Unparsable
                        # TypeError = r.content is None
                        # AttributeError = r is None

                        # We could not parse JSON response.
                        # We will just use the status we already have.
                        pass

                    self.logger.warning(
                        'Failed to send WhatsApp notification to {}: '
                        '{}{}error={}.'.format(
                            target,
                            status_str,
                            ', ' if status_str else '',
                            status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent WhatsApp notification to {}.'.format(target))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending WhatsApp:%s ' % (
                        target) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.from_phone_id, self.token)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {}
        if self.template:
            # Add language to our URL
            params['lang'] = self.language

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Payload body extras prefixed with a ':' sign
        # Append our payload extras into our parameters
        params.update(
            {':{}'.format(k): v for k, v in self.template_mapping.items()})

        return '{schema}://{template}{token}@{from_id}/{targets}/?{params}'\
            .format(
                schema=self.secure_protocol,
                from_id=self.pprint(
                    self.from_phone_id, privacy, safe=''),
                token=self.pprint(self.token, privacy, safe=''),
                template='' if not self.template
                else '{}:'.format(
                    NotifyWhatsApp.quote(self.template, safe='')),
                targets='/'.join(
                    [NotifyWhatsApp.quote(x, safe='') for x in self.targets]),
                params=NotifyWhatsApp.urlencode(params))

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
        results['targets'] = NotifyWhatsApp.split_path(results['fullpath'])

        # The hostname is our From Phone ID
        results['from_phone_id'] = NotifyWhatsApp.unquote(results['host'])

        # Determine if we have a Template, otherwise load our token
        if results['password']:
            #
            # Template Mode
            #
            results['template'] = NotifyWhatsApp.unquote(results['user'])
            results['token'] = NotifyWhatsApp.unquote(results['password'])

        else:
            #
            # Message Mode
            #
            results['token'] = NotifyWhatsApp.unquote(results['user'])

        # Access token
        if 'token' in results['qsd'] and len(results['qsd']['token']):
            # Extract the account sid from an argument
            results['token'] = \
                NotifyWhatsApp.unquote(results['qsd']['token'])

        # Template
        if 'template' in results['qsd'] and len(results['qsd']['template']):
            results['template'] = results['qsd']['template']

        # Template Language
        if 'lang' in results['qsd'] and len(results['qsd']['lang']):
            results['language'] = results['qsd']['lang']

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['from_phone_id'] = \
                NotifyWhatsApp.unquote(results['qsd']['from'])
        if 'source' in results['qsd'] and \
                len(results['qsd']['source']):
            results['from_phone_id'] = \
                NotifyWhatsApp.unquote(results['qsd']['source'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyWhatsApp.parse_phone_no(results['qsd']['to'])

        # store any additional payload extra's defined
        results['template_mapping'] = {
            NotifyWhatsApp.unquote(x): NotifyWhatsApp.unquote(y)
            for x, y in results['qsd:'].items()
        }

        return results
