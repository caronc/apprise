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

# To use this plugin, you must have a ZulipChat bot defined; See here:
#  https://zulipchat.com/help/add-a-bot-or-integration
#
# At the time of writing this plugin the instructions were:
#    1. From your desktop, click on the gear icon in the upper right corner.
#    2. Select Settings.
#    3. On the left, click Your bots.
#    4. Click Add a new bot.
#    5. Fill out the fields, and click Create bot.

# If you know your organization {ID} (as it's part of the zulipchat.com url
# after you signup, then you can also access your bot information by visting:
#   https://ID.zulipchat.com/#settings/your-bots

# For example, I create an organization called apprise.  Thus my URL would be
#   https://apprise.zulipchat.com/#settings/your-bots

#  When you're done and have a bot, it's important to remember the username
#  you provided the bot and the API key generated.
#
#  If your {user} was   : goober-bot@apprise.zulipchat.com
#  and your {apikey} was: lqn6mpwpam6VZzbCW0o7olmk3hwbQSK
#
#  Then the following URLs would be accepted by Apprise:
#   - zulip://goober-bot@apprise.zulipchat.com/lqn6mpwpam6VZzbCW0o7olmk3hwbQSK
#   - zulip://goober-bot@apprise/lqn6mpwpam6VZzbCW0o7olmk3hwbQSK
#   - zulip://goober@apprise/lqn6mpwpam6VZzbCW0o7olmk3hwbQSK
#   - zulip://goober@apprise.zulipchat.com/lqn6mpwpam6VZzbCW0o7olmk3hwbQSK

# The API reference used to build this plugin was documented here:
#  https://zulipchat.com/api/send-message
#
import re
import requests

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import parse_list
from ..utils import validate_regex
from ..utils import is_email
from ..utils import remove_suffix
from ..AppriseLocale import gettext_lazy as _

# A Valid Bot Name
VALIDATE_BOTNAME = re.compile(r'(?P<name>[A-Z0-9_-]{1,32})', re.I)

# Organization required as part of the API request
VALIDATE_ORG = re.compile(
    r'(?P<org>[A-Z0-9_-]{1,32})(\.(?P<hostname>[^\s]+))?', re.I)

# Extend HTTP Error Messages
ZULIP_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
}

# Used to break path apart into list of streams
TARGET_LIST_DELIM = re.compile(r'[ \t\r\n,#\\/]+')

# Used to detect a streams
IS_VALID_TARGET_RE = re.compile(
    r'#?(?P<stream>[A-Z0-9_]{1,32})', re.I)


class NotifyZulip(NotifyBase):
    """
    A wrapper for Zulip Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Zulip'

    # The services URL
    service_url = 'https://zulipchat.com/'

    # The default secure protocol
    secure_protocol = 'zulip'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_zulip'

    # Zulip uses the http protocol with JSON requests
    notify_url = 'https://{org}.{hostname}/api/v1/messages'

    # The maximum allowable characters allowed in the title per message
    title_maxlen = 60

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 10000

    # Define object templates
    templates = (
        '{schema}://{botname}@{organization}/{token}',
        '{schema}://{botname}@{organization}/{token}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'botname': {
            'name': _('Bot Name'),
            'type': 'string',
            'regex': (r'^[A-Z0-9_-]{1,32}$', 'i'),
        },
        'organization': {
            'name': _('Organization'),
            'type': 'string',
            'required': True,
            'regex': (r'^[A-Z0-9_-]{1,32})$', 'i')
        },
        'token': {
            'name': _('Token'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[A-Z0-9]{32}$', 'i'),
        },
        'target_user': {
            'name': _('Target User'),
            'type': 'string',
            'map_to': 'targets',
        },
        'target_stream': {
            'name': _('Target Stream'),
            'type': 'string',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
    })

    # The default hostname to append to a defined organization
    # if one isn't defined in the apprise url
    default_hostname = 'zulipchat.com'

    # The default stream to notify if no targets are specified
    default_notification_stream = 'general'

    def __init__(self, botname, organization, token, targets=None, **kwargs):
        """
        Initialize Zulip Object
        """
        super(NotifyZulip, self).__init__(**kwargs)

        # our default hostname
        self.hostname = self.default_hostname

        try:
            match = VALIDATE_BOTNAME.match(botname.strip())
            if not match:
                # let outer exception handle this
                raise TypeError

            # The botname
            botname = match.group('name')
            botname = remove_suffix(botname, '-bot')
            self.botname = botname

        except (TypeError, AttributeError):
            msg = 'The Zulip botname specified ({}) is invalid.'\
                .format(botname)
            self.logger.warning(msg)
            raise TypeError(msg)

        try:
            match = VALIDATE_ORG.match(organization.strip())
            if not match:
                # let outer exception handle this
                raise TypeError

            # The organization
            self.organization = match.group('org')
            if match.group('hostname'):
                self.hostname = match.group('hostname')

        except (TypeError, AttributeError):
            msg = 'The Zulip organization specified ({}) is invalid.'\
                .format(organization)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.token = validate_regex(
            token, *self.template_tokens['token']['regex'])
        if not self.token:
            msg = 'The Zulip token specified ({}) is invalid.'\
                .format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.targets = parse_list(targets)
        if len(self.targets) == 0:
            # No streams identified, use default
            self.targets.append(self.default_notification_stream)

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Zulip Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
        }

        # error tracking (used for function return)
        has_error = False

        # Prepare our notification URL
        url = self.notify_url.format(
            org=self.organization,
            hostname=self.hostname,
        )

        # prepare JSON Object
        payload = {
            'subject': title,
            'content': body,
        }

        # Determine Authentication
        auth = (
            '{botname}-bot@{org}.{hostname}'.format(
                botname=self.botname,
                org=self.organization,
                hostname=self.hostname,
            ),
            self.token,
        )

        # Create a copy of the target list
        targets = list(self.targets)
        while len(targets):
            target = targets.pop(0)
            result = is_email(target)
            if result:
                # Send a private message
                payload['type'] = 'private'
            else:
                # Send a stream message
                payload['type'] = 'stream'

            # Set our target
            payload['to'] = target if not result else result['full_email']

            self.logger.debug('Zulip POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('Zulip Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    url,
                    data=payload,
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyZulip.http_response_code_lookup(
                            r.status_code, ZULIP_HTTP_ERROR_MAP)

                    self.logger.warning(
                        'Failed to send Zulip notification to {}: '
                        '{}{}error={}.'.format(
                            target,
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent Zulip notification to {}.'.format(target))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Zulip '
                    'notification to {}.'.format(target))
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # simplify our organization in our URL if we can
        organization = '{}{}'.format(
            self.organization,
            '.{}'.format(self.hostname)
            if self.hostname != self.default_hostname else '')

        return '{schema}://{botname}@{org}/{token}/' \
            '{targets}?{params}'.format(
                schema=self.secure_protocol,
                botname=NotifyZulip.quote(self.botname, safe=''),
                org=NotifyZulip.quote(organization, safe=''),
                token=self.pprint(self.token, privacy, safe=''),
                targets='/'.join(
                    [NotifyZulip.quote(x, safe='') for x in self.targets]),
                params=NotifyZulip.urlencode(params),
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

        # The botname
        results['botname'] = NotifyZulip.unquote(results['user'])

        # The first token is stored in the hostname
        results['organization'] = NotifyZulip.unquote(results['host'])

        # Now fetch the remaining tokens
        try:
            results['token'] = \
                NotifyZulip.split_path(results['fullpath'])[0]

        except IndexError:
            # no token
            results['token'] = None

        # Get unquoted entries
        results['targets'] = NotifyZulip.split_path(results['fullpath'])[1:]

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += [x for x in filter(
                bool, TARGET_LIST_DELIM.split(
                    NotifyZulip.unquote(results['qsd']['to'])))]

        return results
