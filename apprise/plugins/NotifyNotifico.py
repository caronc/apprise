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

# Notifico allows you to relay notifications into IRC channels.
#
# 1. visit https://n.tkte.ch and sign up for an account
# 2. create a project; either manually or sync with github
# 3. from within the project, you can create a message hook
#
# the URL will look something like this:
#       https://n.tkte.ch/h/2144/uJmKaBW9WFk42miB146ci3Kj
#                            ^                ^
#                            |                |
#                         project id       message hook
#
# This plugin also supports taking the URL (as identified above) directly
# as well.

import re
import requests

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import parse_bool
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class NotificoFormat(object):
    # Resets all formating
    Reset = '\x0F'

    # Formatting
    Bold = '\x02'
    Italic = '\x1D'
    Underline = '\x1F'
    BGSwap = '\x16'


class NotificoColor(object):
    # Resets Color
    Reset = '\x03'

    # Colors
    White = '\x0300'
    Black = '\x0301'
    Blue = '\x0302'
    Green = '\x0303'
    Red = '\x0304'
    Brown = '\x0305'
    Purple = '\x0306'
    Orange = '\x0307'
    Yellow = '\x0308',
    LightGreen = '\x0309'
    Teal = '\x0310'
    LightCyan = '\x0311'
    LightBlue = '\x0312'
    Violet = '\x0313'
    Grey = '\x0314'
    LightGrey = '\x0315'


class NotifyNotifico(NotifyBase):
    """
    A wrapper for Notifico Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Notifico'

    # The services URL
    service_url = 'https://n.tkte.ch'

    # The default protocol
    protocol = 'notifico'

    # The default secure protocol
    secure_protocol = 'notifico'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_notifico'

    # Plain Text Notification URL
    notify_url = 'https://n.tkte.ch/h/{proj}/{hook}'

    # The title is not used
    title_maxlen = 0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 512

    # Define object templates
    templates = (
        '{schema}://{project_id}/{msghook}',
    )

    # Define our template arguments
    template_tokens = dict(NotifyBase.template_tokens, **{
        # The Project ID is found as the first part of the URL
        #  /1234/........................
        'project_id': {
            'name': _('Project ID'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[0-9]+$', ''),
        },
        # The Message Hook follows the Project ID
        #  /..../AbCdEfGhIjKlMnOpQrStUvWX
        'msghook': {
            'name': _('Message Hook'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[a-z0-9]+$', 'i'),
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        # You can optionally pass IRC colors into
        'color': {
            'name': _('IRC Colors'),
            'type': 'bool',
            'default': True,
        },

        # You can optionally pass IRC color into
        'prefix': {
            'name': _('Prefix'),
            'type': 'bool',
            'default': True,
        },
    })

    def __init__(self, project_id, msghook, color=True, prefix=True,
                 **kwargs):
        """
        Initialize Notifico Object
        """
        super(NotifyNotifico, self).__init__(**kwargs)

        # Assign our message hook
        self.project_id = validate_regex(
            project_id, *self.template_tokens['project_id']['regex'])
        if not self.project_id:
            msg = 'An invalid Notifico Project ID ' \
                  '({}) was specified.'.format(project_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Assign our message hook
        self.msghook = validate_regex(
            msghook, *self.template_tokens['msghook']['regex'])
        if not self.msghook:
            msg = 'An invalid Notifico Message Token ' \
                  '({}) was specified.'.format(msghook)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Prefix messages with a [?] where ? identifies the message type
        # such as if it's an error, warning, info, or success
        self.prefix = prefix

        # Send colors
        self.color = color

        # Prepare our notification URL now:
        self.api_url = self.notify_url.format(
            proj=self.project_id,
            hook=self.msghook,
        )
        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'color': 'yes' if self.color else 'no',
            'prefix': 'yes' if self.prefix else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{proj}/{hook}/?{params}'.format(
            schema=self.secure_protocol,
            proj=self.pprint(self.project_id, privacy, safe=''),
            hook=self.pprint(self.msghook, privacy, safe=''),
            params=NotifyNotifico.urlencode(params),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        wrapper to _send since we can alert more then one channel
        """

        # prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
        }

        # Prepare our IRC Prefix
        color = ''
        token = ''
        if notify_type == NotifyType.INFO:
            color = NotificoColor.Teal
            token = 'i'

        elif notify_type == NotifyType.SUCCESS:
            color = NotificoColor.LightGreen
            token = '✔'

        elif notify_type == NotifyType.WARNING:
            color = NotificoColor.Orange
            token = '!'

        elif notify_type == NotifyType.FAILURE:
            color = NotificoColor.Red
            token = '✗'

        if self.color:
            # Colors were specified, make sure we capture and correctly
            # allow them to exist inline in the message
            # \g<1> is less ambigious than \1
            body = re.sub(r'\\x03(\d{0,2})', '\x03\g<1>', body)

        else:
            # no colors specified, make sure we strip out any colors found
            # to make the string read-able
            body = re.sub(r'\\x03(\d{1,2}(,[0-9]{1,2})?)?', '', body)

        # Prepare our payload
        payload = {
            'payload': body if not self.prefix
            else '{}[{}]{} {}{}{}: {}{}'.format(
                # Token [?] at the head
                color if self.color else '',
                token,
                NotificoColor.Reset if self.color else '',
                # App ID
                NotificoFormat.Bold if self.color else '',
                self.app_id,
                NotificoFormat.Reset if self.color else '',
                # Message Body
                body,
                # Reset
                NotificoFormat.Reset if self.color else '',
            ),
        }

        self.logger.debug('Notifico GET URL: %s (cert_verify=%r)' % (
            self.api_url, self.verify_certificate))
        self.logger.debug('Notifico Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.get(
                self.api_url,
                params=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyNotifico.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Notifico notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Notifico notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Notifico '
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

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The first token is stored in the hostname
        results['project_id'] = NotifyNotifico.unquote(results['host'])

        # Get Message Hook
        try:
            results['msghook'] = NotifyNotifico.split_path(
                results['fullpath'])[0]

        except IndexError:
            results['msghook'] = None

        # Include Color
        results['color'] = \
            parse_bool(results['qsd'].get('color', True))

        # Include Prefix
        results['prefix'] = \
            parse_bool(results['qsd'].get('prefix', True))

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://n.tkte.ch/h/PROJ_ID/MESSAGE_HOOK/
        """

        result = re.match(
            r'^https?://n\.tkte\.ch/h/'
            r'(?P<proj>[0-9]+)/'
            r'(?P<hook>[A-Z0-9]+)/?'
            r'(?P<params>\?.+)?$', url, re.I)

        if result:
            return NotifyNotifico.parse_url(
                '{schema}://{proj}/{hook}/{params}'.format(
                    schema=NotifyNotifico.secure_protocol,
                    proj=result.group('proj'),
                    hook=result.group('hook'),
                    params='' if not result.group('params')
                    else result.group('params')))

        return None
