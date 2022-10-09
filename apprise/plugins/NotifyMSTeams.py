# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

# To use this plugin, you need to create a webhook; you can read more about
# this here:
#    https://dev.outlook.com/Connectors/\
#       GetStarted#creating-messages-through-office-365-connectors-\
#           in-microsoft-teams
#
# More details are here on API Construction:
#    https://docs.microsoft.com/en-ca/outlook/actionable-messages/\
#        message-card-reference
#
# I personally created a free account at teams.microsoft.com and then
# went to the store (bottom left hand side of slack like interface).
#
# From here you can search for 'Incoming Webhook'. Once you click on it,
# you can associate the webhook with your team. At this point, you can
# optionally also assign it a name, an avatar.  Finally you'll have to
# assign it a channel it will notify.
#
# When you've completed this, it will generate you a (webhook) URL that
# looks like:
#   https://team-name.webhook.office.com/webhookb2/ \
#       abcdefgf8-2f4b-4eca-8f61-225c83db1967@abcdefg2-5a99-4849-8efc-\
#        c9e78d28e57d/IncomingWebhook/291289f63a8abd3593e834af4d79f9fe/\
#          a2329f43-0ffb-46ab-948b-c9abdad9d643
#
# Yes... The URL is that big... But it looks like this (greatly simplified):
# https://TEAM-NAME.webhook.office.com/webhookb2/ABCD/IncomingWebhook/DEFG/HIJK
#             ^                                   ^                    ^    ^
#             |                                   |                    |    |
#  These are important <--------------------------^--------------------^----^
#

# The Legacy format didn't have the team name identified and reads 'outlook'
# While this still works, consider that Microsoft will be dropping support
# for this soon, so you may need to update your IncomingWebhook. Here is
# what a legacy URL looked like:
# https://outlook.office.com/webhook/ABCD/IncomingWebhook/DEFG/HIJK
#           ^                         ^                    ^    ^
#           |                         |                    |    |
#   legacy team reference: 'outlook'  |                    |    |
#                                     |                    |    |
#  These are important <--------------^--------------------^----^
#

# You'll notice that the first token is actually 2 separated by an @ symbol
# But lets just ignore that and assume it's one great big token instead.
#
# These 3 tokens need to be placed in the URL after the Team
#   msteams://TEAM/ABCD/DEFG/HIJK
#
import re
import requests
import json
from json.decoder import JSONDecodeError

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType
from ..common import NotifyFormat
from ..utils import parse_bool
from ..utils import validate_regex
from ..utils import apply_template
from ..utils import TemplateType
from ..AppriseAttachment import AppriseAttachment
from ..AppriseLocale import gettext_lazy as _


class NotifyMSTeams(NotifyBase):
    """
    A wrapper for Microsoft Teams Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'MSTeams'

    # The services URL
    service_url = 'https://teams.micrsoft.com/'

    # The default secure protocol
    secure_protocol = 'msteams'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_msteams'

    # MSTeams uses the http protocol with JSON requests
    notify_url_v1 = 'https://outlook.office.com/webhook/' \
        '{token_a}/IncomingWebhook/{token_b}/{token_c}'

    # New MSTeams webhook (as of April 11th, 2021)
    notify_url_v2 = 'https://{team}.webhook.office.com/webhookb2/' \
        '{token_a}/IncomingWebhook/{token_b}/{token_c}'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    # Default Notification Format
    notify_format = NotifyFormat.MARKDOWN

    # There is no reason we should exceed 35KB when reading in a JSON file.
    # If it is more than this, then it is not accepted
    max_msteams_template_size = 35000

    # Define object templates
    templates = (
        # New required format
        '{schema}://{team}/{token_a}/{token_b}/{token_c}',

        # Deprecated
        '{schema}://{token_a}/{token_b}/{token_c}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        # The Microsoft Team Name
        'team': {
            'name': _('Team Name'),
            'type': 'string',
            'required': True,
            'regex': (r'^[A-Z0-9_-]+$', 'i'),
        },
        # Token required as part of the API request
        #  /AAAAAAAAA@AAAAAAAAA/........./.........
        'token_a': {
            'name': _('Token A'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[A-Z0-9-]+@[A-Z0-9-]+$', 'i'),
        },
        # Token required as part of the API request
        #  /................../BBBBBBBBB/..........
        'token_b': {
            'name': _('Token B'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[a-z0-9]+$', 'i'),
        },
        # Token required as part of the API request
        #  /........./........./CCCCCCCCCCCCCCCCCCCCCCCC
        'token_c': {
            'name': _('Token C'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[a-z0-9-]+$', 'i'),
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': False,
            'map_to': 'include_image',
        },
        'version': {
            'name': _('Version'),
            'type': 'choice:int',
            'values': (1, 2),
            'default': 2,
        },
        'template': {
            'name': _('Template Path'),
            'type': 'string',
            'private': True,
        },
    })

    # Define our token control
    template_kwargs = {
        'tokens': {
            'name': _('Template Tokens'),
            'prefix': ':',
        },
    }

    def __init__(self, token_a, token_b, token_c, team=None, version=None,
                 include_image=True, template=None, tokens=None, **kwargs):
        """
        Initialize Microsoft Teams Object

        You can optional specify a template and identify arguments you
        wish to populate your template with when posting.  Some reserved
        template arguments that can not be over-ridden are:
           `body`, `title`, and `type`.
        """
        super().__init__(**kwargs)

        try:
            self.version = int(version)

        except TypeError:
            # None was specified... take on default
            self.version = self.template_args['version']['default']

        except ValueError:
            # invalid content was provided; let this get caught in the next
            # validation check for the version
            self.version = None

        if self.version not in self.template_args['version']['values']:
            msg = 'An invalid MSTeams Version ' \
                  '({}) was specified.'.format(version)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.team = validate_regex(team)
        if not self.team:
            NotifyBase.logger.deprecate(
                "Apprise requires you to identify your Microsoft Team name as "
                "part of the URL. e.g.: "
                "msteams://TEAM-NAME/{token_a}/{token_b}/{token_c}")

            # Fallback
            self.team = 'outlook'

        self.token_a = validate_regex(
            token_a, *self.template_tokens['token_a']['regex'])
        if not self.token_a:
            msg = 'An invalid MSTeams (first) Token ' \
                  '({}) was specified.'.format(token_a)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.token_b = validate_regex(
            token_b, *self.template_tokens['token_b']['regex'])
        if not self.token_b:
            msg = 'An invalid MSTeams (second) Token ' \
                  '({}) was specified.'.format(token_b)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.token_c = validate_regex(
            token_c, *self.template_tokens['token_c']['regex'])
        if not self.token_c:
            msg = 'An invalid MSTeams (third) Token ' \
                  '({}) was specified.'.format(token_c)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Place a thumbnail image inline with the message body
        self.include_image = include_image

        # Our template object is just an AppriseAttachment object
        self.template = AppriseAttachment(asset=self.asset)
        if template:
            # Add our definition to our template
            self.template.add(template)
            # Enforce maximum file size
            self.template[0].max_file_size = self.max_msteams_template_size

        # Template functionality
        self.tokens = {}
        if isinstance(tokens, dict):
            self.tokens.update(tokens)

        elif tokens:
            msg = 'The specified MSTeams Template Tokens ' \
                  '({}) are not identified as a dictionary.'.format(tokens)
            self.logger.warning(msg)
            raise TypeError(msg)

        # else:  NoneType - this is okay
        return

    def gen_payload(self, body, title='', notify_type=NotifyType.INFO,
                    **kwargs):
        """
        This function generates our payload whether it be the generic one
        Apprise generates by default, or one provided by a specified
        external template.
        """

        # Acquire our to-be footer icon if configured to do so
        image_url = None if not self.include_image \
            else self.image_url(notify_type)

        if not self.template:
            # By default we use a generic working payload if there was
            # no template specified
            payload = {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "summary": self.app_desc,
                "themeColor": self.color(notify_type),
                "sections": [
                    {
                        "activityImage": None,
                        "activityTitle": title,
                        "text": body,
                    },
                ]
            }

            if image_url:
                payload['sections'][0]['activityImage'] = image_url

            return payload

        # If our code reaches here, then we generate ourselves the payload
        template = self.template[0]
        if not template:
            # We could not access the attachment
            self.logger.error(
                'Could not access MSTeam template {}.'.format(
                    template.url(privacy=True)))
            return False

        # Take a copy of our token dictionary
        tokens = self.tokens.copy()

        # Apply some defaults template values
        tokens['app_body'] = body
        tokens['app_title'] = title
        tokens['app_type'] = notify_type
        tokens['app_id'] = self.app_id
        tokens['app_desc'] = self.app_desc
        tokens['app_color'] = self.color(notify_type)
        tokens['app_image_url'] = image_url
        tokens['app_url'] = self.app_url

        # Enforce Application mode
        tokens['app_mode'] = TemplateType.JSON

        try:
            with open(template.path, 'r') as fp:
                content = json.loads(apply_template(fp.read(), **tokens))

        except (OSError, IOError):
            self.logger.error(
                'MSTeam template {} could not be read.'.format(
                    template.url(privacy=True)))
            return None

        except JSONDecodeError as e:
            self.logger.error(
                'MSTeam template {} contains invalid JSON.'.format(
                    template.url(privacy=True)))
            self.logger.debug('JSONDecodeError: {}'.format(e))
            return None

        # Load our JSON data (if valid)
        has_error = False
        if '@type' not in content:
            self.logger.error(
                'MSTeam template {} is missing @type kwarg.'.format(
                    template.url(privacy=True)))
            has_error = True

        if '@context' not in content:
            self.logger.error(
                'MSTeam template {} is missing @context kwarg.'.format(
                    template.url(privacy=True)))
            has_error = True

        return content if not has_error else None

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Microsoft Teams Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        notify_url = self.notify_url_v2.format(
            team=self.team,
            token_a=self.token_a,
            token_b=self.token_b,
            token_c=self.token_c,
        ) if self.version > 1 else \
            self.notify_url_v1.format(
                token_a=self.token_a,
                token_b=self.token_b,
                token_c=self.token_c)

        # Generate our payload if it's possible
        payload = self.gen_payload(
            body=body, title=title, notify_type=notify_type, **kwargs)
        if not payload:
            # No need to present a reason; that will come from the
            # gen_payload() function itself
            return False

        self.logger.debug('MSTeams POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('MSTeams Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                notify_url,
                data=json.dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyMSTeams.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send MSTeams notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # We failed
                return False

            else:
                self.logger.info('Sent MSTeams notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending MSTeams notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # We failed
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

        if self.version != self.template_args['version']['default']:
            params['version'] = str(self.version)

        if self.template:
            params['template'] = NotifyMSTeams.quote(
                self.template[0].url(), safe='')

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))
        # Store any template entries if specified
        params.update({':{}'.format(k): v for k, v in self.tokens.items()})

        if self.version > 1:
            return '{schema}://{team}/{token_a}/{token_b}/{token_c}/'\
                '?{params}'.format(
                    schema=self.secure_protocol,
                    team=NotifyMSTeams.quote(self.team, safe=''),
                    token_a=self.pprint(self.token_a, privacy, safe=''),
                    token_b=self.pprint(self.token_b, privacy, safe=''),
                    token_c=self.pprint(self.token_c, privacy, safe=''),
                    params=NotifyMSTeams.urlencode(params),
                )

        else:  # Version 1
            return '{schema}://{token_a}/{token_b}/{token_c}/'\
                '?{params}'.format(
                    schema=self.secure_protocol,
                    token_a=self.pprint(self.token_a, privacy, safe='@'),
                    token_b=self.pprint(self.token_b, privacy, safe=''),
                    token_c=self.pprint(self.token_c, privacy, safe=''),
                    params=NotifyMSTeams.urlencode(params),
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

        # Get unquoted entries
        entries = NotifyMSTeams.split_path(results['fullpath'])

        # Deprecated mode (backwards compatibility)
        if results.get('user'):
            # If a user was found, it's because it's still part of the first
            # token, so we concatinate them
            results['token_a'] = '{}@{}'.format(
                NotifyMSTeams.unquote(results['user']),
                NotifyMSTeams.unquote(results['host']),
            )

        else:
            # Get the Team from the hostname
            results['team'] = NotifyMSTeams.unquote(results['host'])

            # Get the token from the path
            results['token_a'] = None if not entries \
                else NotifyMSTeams.unquote(entries.pop(0))

        results['token_b'] = None if not entries \
            else NotifyMSTeams.unquote(entries.pop(0))
        results['token_c'] = None if not entries \
            else NotifyMSTeams.unquote(entries.pop(0))

        # Get Image
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        # Get Team name if defined
        if 'team' in results['qsd'] and results['qsd']['team']:
            results['team'] = \
                NotifyMSTeams.unquote(results['qsd']['team'])

        # Template Handling
        if 'template' in results['qsd'] and results['qsd']['template']:
            results['template'] = \
                NotifyMSTeams.unquote(results['qsd']['template'])

        # Override version if defined
        if 'version' in results['qsd'] and results['qsd']['version']:
            results['version'] = \
                NotifyMSTeams.unquote(results['qsd']['version'])

        else:
            # Set our version if not otherwise set
            results['version'] = 1 if not results.get('team') else 2

        # Store our tokens
        results['tokens'] = results['qsd:']

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Legacy Support:
            https://outlook.office.com/webhook/ABCD/IncomingWebhook/DEFG/HIJK

        New Hook Support:
            https://team-name.office.com/webhook/ABCD/IncomingWebhook/DEFG/HIJK
        """

        # We don't need to do incredibly details token matching as the purpose
        # of this is just to detect that were dealing with an msteams url
        # token parsing will occur once we initialize the function
        result = re.match(
            r'^https?://(?P<team>[^.]+)(?P<v2a>\.webhook)?\.office\.com/'
            r'webhook(?P<v2b>b2)?/'
            r'(?P<token_a>[A-Z0-9-]+@[A-Z0-9-]+)/'
            r'IncomingWebhook/'
            r'(?P<token_b>[A-Z0-9]+)/'
            r'(?P<token_c>[A-Z0-9-]+)/?'
            r'(?P<params>\?.+)?$', url, re.I)

        if result:
            if result.group('v2a'):
                # Version 2 URL
                return NotifyMSTeams.parse_url(
                    '{schema}://{team}/{token_a}/{token_b}/{token_c}'
                    '/{params}'.format(
                        schema=NotifyMSTeams.secure_protocol,
                        team=result.group('team'),
                        token_a=result.group('token_a'),
                        token_b=result.group('token_b'),
                        token_c=result.group('token_c'),
                        params='' if not result.group('params')
                        else result.group('params')))
            else:
                # Version 1 URLs
                # team is also set to 'outlook' in this case
                return NotifyMSTeams.parse_url(
                    '{schema}://{token_a}/{token_b}/{token_c}'
                    '/{params}'.format(
                        schema=NotifyMSTeams.secure_protocol,
                        token_a=result.group('token_a'),
                        token_b=result.group('token_b'),
                        token_c=result.group('token_c'),
                        params='' if not result.group('params')
                        else result.group('params')))
        return None
