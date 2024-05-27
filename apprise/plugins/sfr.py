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

# For this to work correctly you need to have a valid SFR DMC service account
# to whicthe API password can be generated. A "space" is also necessary
# (space = a logical separation between clients), which will give you a
# specific spaceId
#
# Expected credentials looks a little like this:
# serviceId: 84920958892    - Random numbers
# servicePassword: XxXXxXXx - Random characters
# spaceId: 984348           - Random numbers
#
# 1. Visit https://www.sfr.fr/
#
# 2. Url will look like this
#    https://www.dmc.sfr-sh.fr/DmcWS/1.5.8/JsonService/<apiGroup>/<apicall>

import requests
import json
from typing import Any
from urllib.parse import unquote

from .base import NotifyBase
from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils import is_phone_no
from ..url import PrivacyMode


class NotifySFR(NotifyBase):
    """
    A wrapper for SFR French Telecom DMC API
    """

    # The default descriptive name associated with the Notification
    service_name = _('SFR Notification')

    # The services URL
    service_url = 'https://www.sfr.fr/'

    # The default protocol
    protocol = 'sfr'

    # The default secure protocol
    secure_protocol = 'sfrs'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_sfr'

    # SFR api
    notify_url = (
        'https://www.dmc.sfr-sh.fr/DmcWS/1.5.8/JsonService/'
        'MessagesUnitairesWS/addSingleCall'  # this is the actual api call
    )

    # Define object templates
    templates = (
        '{schema}://{user}:{password}@{space_id}/{to}',
    )

    # Define our tokens
    template_tokens = dict(
        NotifyBase.template_tokens, **{
            'user': {
                'name': _('Service ID'),
                'type': 'string',
                'required': True,
            },
            'password': {
                'name': _('Service Password'),
                'type': 'string',
                'private': True,
                'required': True,
            },
            'space_id': {
                'name': _('Space ID'),
                'type': 'string',
                'required': True,
            },
            'to': {
                'name': _('Recipient Phone Number'),
                'type': 'string',
                'required': True,
                'regex': (r'^\+?[0-9\s)(+-]+$', 'i'),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args, **{
            'media': {
                'name': _('Media Type'),
                'type': 'string',
                'required': False,
                'values': ['SMS', 'SMSLong', 'SMSUnicode', 'SMSUnicodeLong'],
            },
            'from': {
                'name': _('Sender Name'),
                'type': 'string',
                'required': False,
            },
            'timeout': {
                'name': _('Timeout'),
                'type': 'int',
                'default': 2880,
                'required': False,
            },
            'ttsVoice': {
                'name': _('TTS Voice'),
                'type': 'string',
                'default': 'claire08s',
                'required': False,
            },
            'lang': {
                'name': _('Language'),
                'type': 'string',
                'default': 'fr_FR',
                'required': False,
            },
        },
    )

    def __init__(
        self, user: str, password: str, space_id: str,
        to: str, **kwargs: Any,
    ) -> None:
        """
        Initialize SFR Object
        """
        super().__init__(**kwargs)

        # Initialize your SFR-specific attributes
        self.user = user
        self.password = password

        if not (self.user and self.password):
            msg = 'A SFR user (serviceId) and password (servicePassword) ' \
                  'combination was not provided.'
            self.logger.warning(msg)
            raise TypeError(msg)

        self.space_id = space_id
        if not (self.space_id):
            msg = 'A SFR spaceId ' \
                  'is required.'
            self.logger.warning(msg)
            raise TypeError(msg)

        self.to = to
        if not (self.to):
            msg = 'A receiver phone number ' \
                  'is required.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not is_phone_no(self.to):
            msg = 'An invalid SFR Source Phone No ' \
                  '({}) was provided.'.format(to)
            self.logger.warning(msg)
            raise TypeError(msg)

        # self.space_id = kwargs.get('space_id', -1)
        # self.to = kwargs.get('to', '')
        self.media = kwargs.get('media')
        self.sender = kwargs.get('from')
        self.timeout = kwargs.get('timeout')
        self.tts_voice = kwargs.get('ttsVoice')
        self.lang = kwargs.get('lang')

    def _format_params(self, body: str, title: str = '') -> dict[str, str]:
        """
        Generate paramameter format
        """

        # Construct the authentication JSON
        auth_creds = {
            'serviceId': self.user,
            'servicePassword': self.password,
            'spaceId': self.space_id,
            'lang': self.lang,
        }
        authenticate = json.dumps(auth_creds)

        single_message = {
            'media': self.media,         # Can be 'SMSLong', 'SMS'
            'textMsg': body,    # Content of the message
            'to': self.to,               # Receiver's phone number
            'from': self.sender,         # Optional, default to ''
            'timeout': self.timeout,     # Optional, default 2880 minutes
            'ttsVoice': self.tts_voice,  # Optional, default to French voice
        }

        # Construct the content of the singleMessage
        # ensure_ascii to keep the unicode characters
        single_message = json.dumps(single_message, ensure_ascii=False)

        # Return the parameters for the AddSingleCall
        return {'authenticate': authenticate,
                'messageUnitaire': single_message}

    def send(
        self, body: str, title: str = '',
        notify_type: NotifyType = NotifyType.INFO, **kwargs: Any,
    ) -> bool:
        """
        Perform the SFR notification
        """
        params = self._format_params(body, title)

        try:
            response = requests.post(
                self.notify_url,
                params=params,
            )

            # Always call throttle before any remote server i/o is made
            self.throttle()

            # Check if the request was successfull
            if response.status_code not in (
                    requests.codes.ok,
                    requests.codes.no_content,
            ):

                # We had a problem
                error_code = \
                    NotifyBase.http_response_code_lookup(response.status_code)

                self.logger.warning(
                    'Failed to get SFR notification: '
                    '{}{}error={}.'.format(
                        error_code, ', ' if error_code else '',
                        response.status_code,
                    ),
                )
                # Return; we're done
                return False
            else:

                if not response.content:
                    return False
                # We need to actually check if the sucess flag is returned
                # Since SFR send back a status_code==200 even if the
                # authentication failed, or a parameter is not correctly
                # formatted
                r = response.json()
                if r.get('success', ''):
                    self.logger.info('Sent SFR notification.')
                else:
                    self.logger.error(
                        'Could not send SFR Notification.'
                        'success: {}, reason: {}'.format(
                            r.get('success', False), r.get(
                                'errorCode', "UNKOWN ERROR"),
                        ),
                    )

                    # Return; we're done
                    return False

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending SFR '
                'notification.',
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """
        Returns the URL built dynamically based on specified arguments.
        """
        # Define any URL parameters
        params = {
            # 'to': self.to,
            # 'space_id': self.space_id,
            'from': self.sender,
            'timeout': self.timeout,
            'ttsVoice': self.tts_voice,
            'lang': self.lang,
            'media': self.media,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{user}:{password}@{space_id}/{to}?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            user=self.user,
            password=self.pprint(
                self.password,
                privacy,
                mode=PrivacyMode.Secret,
                safe='',
            ),
            space_id=self.space_id,
            to=self.to,
            params=self.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> dict[str, Any]:
        """
        Parse the URL and return arguments required to initialize this plugin
        """
        # NotifyBase.parse_url() will make the initial parsing of your string
        # very easy to use. It will tokenize the entire URL for you.  The
        # tokens are then passed into your __init__() function you defined to
        # generate you're object

        results = NotifyBase.parse_url(url, verify_host=False)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Extract user and password
        results['space_id'] = results.get('host', '')
        results['to'] = unquote(results.get('query', ''))
        results['host'] = \
            'www.dmc.sfr-sh.fr/DmcWS/1.5.8/JsonService/' \
            'MessagesUnitairesWS/addSingleCall'

        # Extract additional parameters
        results['from'] = results.get('qsd', {}).get('from', '')
        results['timeout'] = int(results.get('qsd', {}).get('timeout', 2880))
        results['ttsVoice'] = results.get('qsd', {}).get(
            'ttsVoice', 'claire08s')
        results['lang'] = results.get('qsd', {}).get('lang', 'fr_FR')
        results['media'] = results.get('qsd', {}).get('media', 'SMSUnicode')

        return results
