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
#
# All of the documentation needed to work with the Twist API can be found
# here: https://developer.twist.com/v3/

import re
import requests
from json import loads
from itertools import chain

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_list
from ..utils import GET_EMAIL_RE
from ..AppriseLocale import gettext_lazy as _


# A workspace can also be interpreted as a team name too!
IS_CHANNEL = re.compile(
    r'^#?(?P<name>((?P<workspace>[A-Za-z0-9_-]+):)?'
    r'(?P<channel>[^\s]{1,64}))$')

IS_CHANNEL_ID = re.compile(
    r'^(?P<name>((?P<workspace>[0-9]+):)?(?P<channel>[0-9]+))$')

# Used to break apart list of potential tags by their delimiter
# into a usable list.
LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')


class NotifyTwist(NotifyBase):
    """
    A wrapper for Notify Twist Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Twist'

    # The services URL
    service_url = 'https://twist.com'

    # The default secure protocol
    secure_protocol = 'twist'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_twist'

    # The maximum size of the message
    body_maxlen = 1000

    # Default to markdown
    notify_format = NotifyFormat.MARKDOWN

    # The default Notification URL to use
    api_url = 'https://api.twist.com/api/v3/'

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.2

    # The default channel to notify if no targets are specified
    default_notification_channel = 'general'

    # Define object templates
    templates = (
        '{schema}://{password}:{email}',
        '{schema}://{password}:{email}/{targets}',
    )

    # Define our template arguments
    template_tokens = dict(NotifyBase.template_tokens, **{
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
        },
        'email': {
            'name': _('Email'),
            'type': 'string',
        },
        'target_channel': {
            'name': _('Target Channel'),
            'type': 'string',
            'prefix': '#',
            'map_to': 'targets',
        },
        'target_channel_id': {
            'name': _('Target Channel ID'),
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

    def __init__(self, email=None, targets=None, **kwargs):
        """
        Initialize Notify Twist Object
        """
        super(NotifyTwist, self).__init__(**kwargs)

        # Initialize channels list
        self.channels = set()

        # Initialize Channel ID which are stored as:
        #   <workspace_id>:<channel_id>
        self.channel_ids = set()

        # Initialize our Email Object
        self.email = email if email else '{}@{}'.format(
            self.user,
            self.host,
        )

        # The token is None if we're not logged in and False if we
        # failed to log in.  Otherwise it is set to the actual token
        self.token = None

        # Our default workspace (associated with our token)
        self.default_workspace = None

        # A set of all of the available workspaces
        self._cached_workspaces = set()

        # A mapping of channel names, the layout is as follows:
        #  {
        #     <workspace_id>: {
        #          <channel_name>: <channel_id>,
        #          <channel_name>: <channel_id>,
        #          ...
        #     },
        #     <workspace2_id>: {
        #          <channel_name>: <channel_id>,
        #          <channel_name>: <channel_id>,
        #          ...
        #     },
        #  }
        self._cached_channels = dict()

        try:
            result = GET_EMAIL_RE.match(self.email)
            if not result:
                # let outer exception handle this
                raise TypeError

            if email:
                # Force user/host to be that of the defined email for
                # consistency. This is very important for those initializing
                # this object with the the email object would could potentially
                # cause inconsistency to contents in the NotifyBase() object
                self.user = result.group('fulluser')
                self.host = result.group('domain')

        except (TypeError, AttributeError):
            msg = 'The Twist Auth email specified ({}) is invalid.'\
                .format(self.email)
            self.logger.warning(msg)
            raise TypeError(msg)

        if not self.password:
            msg = 'No Twist password was specified with account: {}'\
                .format(self.email)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate recipients and drop bad ones:
        for recipient in parse_list(targets):
            result = IS_CHANNEL_ID.match(recipient)
            if result:
                # store valid channel id
                self.channel_ids.add(result.group('name'))
                continue

            result = IS_CHANNEL.match(recipient)
            if result:
                # store valid device
                self.channels.add(result.group('name').lower())
                continue

            self.logger.warning(
                'Dropped invalid channel/id '
                '({}) specified.'.format(recipient),
            )

        if len(self.channels) + len(self.channel_ids) == 0:
            # Notify our default channel
            self.channels.add(self.default_notification_channel)
            self.logger.warning(
                'Added default notification channel {}'.format(
                    self.default_notification_channel))
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
        }

        return '{schema}://{password}:{user}@{host}/{targets}/?{args}'.format(
            schema=self.secure_protocol,
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            user=self.quote(self.user, safe=''),
            host=self.host,
            targets='/'.join(
                [NotifyTwist.quote(x, safe='') for x in chain(
                    # Channels are prefixed with a pound/hashtag symbol
                    ['#{}'.format(x) for x in self.channels],
                    # Channel IDs
                    self.channel_ids,
                )]),
            args=NotifyTwist.urlencode(args),
        )

    def login(self):
        """
        A simple wrapper to authenticate with the Twist Server
        """

        # Prepare our payload
        payload = {
            'email': self.email,
            'password': self.password,
        }

        # Reset our default workspace
        self.default_workspace = None

        # Reset our cached objects
        self._cached_workspaces = set()
        self._cached_channels = dict()

        # Send Login Information
        postokay, response = self._fetch(
            'users/login',
            payload=payload,
            # We set this boolean so internal recursion doesn't take place.
            login=True,
        )

        if not postokay or not response:
            # Setting this variable to False as a way of letting us know
            # we failed to authenticate on our last attempt
            self.token = False
            return False

        # Our response object looks like this (content has been altered for
        # presentation purposes):
        # {
        #     "contact_info": null,
        #     "profession": null,
        #     "timezone": "UTC",
        #     "avatar_id": null,
        #     "id": 123456,
        #     "first_name": "Jordan",
        #     "comet_channel":
        #         "124371-34be423219130343030d4ec0a3dabbbbbe565eee",
        #     "restricted": false,
        #     "default_workspace": 92020,
        #     "snooze_dnd_end": null,
        #     "email": "user@example.com",
        #     "comet_server": "https://comet.twist.com",
        #     "snooze_until": null,
        #     "lang": "en",
        #     "feature_flags": [],
        #     "short_name": "Jordan P.",
        #     "away_mode": null,
        #     "time_format": "12",
        #     "client_id": "cb01f37e-a5b2-13e9-ba2a-023a33d10dc0",
        #     "removed": false,
        #     "emails": [
        #         {
        #             "connected": [],
        #             "email": "user@example.com",
        #             "primary": true
        #         }
        #     ],
        #     "scheduled_banners": [
        #         "threads_3",
        #         "threads_1",
        #         "notification_permissions",
        #         "search_1",
        #         "messages_1",
        #         "team_1",
        #         "inbox_2",
        #         "inbox_1"
        #     ],
        #     "snooze_dnd_start": null,
        #     "name": "Jordan Peterson",
        #     "off_days": [],
        #     "bot": false,
        #     "token": "2e82c1e4e8b0091fdaa34ff3972351821406f796",
        #     "snoozed": false,
        #     "setup_pending": false,
        #     "date_format": "MM/DD/YYYY"
        # }

        # Store our default workspace
        self.default_workspace = response.get('default_workspace')

        # Acquire our token
        self.token = response.get('token')

        self.logger.info('Authenticated to Twist as {}'.format(self.email))
        return True

    def logout(self):
        """
        A simple wrapper to log out of the server
        """

        if not self.token:
            # Nothing more to do
            return True

        # Send Logout Message
        postokay, response = self._fetch('users/logout')

        # reset our token
        self.token = None

        # There is no need to handling failed log out attempts at this time
        return True

    def get_workspaces(self):
        """
        Returns all workspaces associated with this user account as a set

        This returned object is either an empty dictionary or one that
        looks like this:
           {
             'workspace': <workspace_id>,
             'workspace': <workspace_id>,
             'workspace': <workspace_id>,
           }

        All workspaces are made lowercase for comparison purposes
        """
        if not self.token and not self.login():
            # Nothing more to do
            return dict()

        postokay, response = self._fetch('workspaces/get')
        if not postokay or not response:
            # We failed to retrieve
            return dict()

        # The response object looks like so:
        #   [
        #     {
        #       "created_ts": 1563044447,
        #       "name": "apprise",
        #       "creator": 123571,
        #       "color": 1,
        #       "default_channel": 13245,
        #       "plan": "free",
        #       "default_conversation": 63022,
        #       "id": 12345
        #     }
        #   ]

        # Knowing our response, we can iterate over each object and cache our
        # object
        result = {}
        for entry in response:
            result[entry.get('name', '').lower()] = entry.get('id', '')

        return result

    def get_channels(self, wid):
        """
        Simply returns the channel objects associated with the specified
        workspace id.

        This returned object is either an empty dictionary or one that
        looks like this:
           {
             'channel1': <channel_id>,
             'channel2': <channel_id>,
             'channel3': <channel_id>,
           }

        All channels are made lowercase for comparison purposes
        """
        if not self.token and not self.login():
            # Nothing more to do
            return {}

        payload = {'workspace_id': wid}
        postokay, response = self._fetch(
            'channels/get', payload=payload)

        if not postokay or not isinstance(response, list):
            # We failed to retrieve
            return {}

        # Response looks like this:
        #  [
        #    {
        #      "id": 123,
        #      "name": "General"
        #      "workspace_id": 12345,
        #      "color": 1,
        #      "description": "",
        #      "archived": false,
        #      "public": true,
        #      "user_ids": [
        #        8754
        #      ],
        #      "created_ts": 1563044447,
        #      "creator": 123571,
        #    }
        #  ]
        #
        # Knowing our response, we can iterate over each object and cache our
        # object
        result = {}
        for entry in response:
            result[entry.get('name', '').lower()] = entry.get('id', '')

        return result

    def _channel_migration(self):
        """
        A simple wrapper to get all of the current workspaces including
        the default one.  This plays a role in what channel(s) get notified
        and where.

        A cache lookup has overhead, and is only required to be preformed
        if the user specified channels by their string value
        """

        if not self.token and not self.login():
            # Nothing more to do
            return False

        if not len(self.channels):
            # Nothing to do; take an early exit
            return True

        if self.default_workspace \
                and self.default_workspace not in self._cached_channels:
            # Get our default workspace entries
            self._cached_channels[self.default_workspace] = \
                self.get_channels(self.default_workspace)

        # initialize our error tracking
        has_error = False

        while len(self.channels):
            # Pop our channel off of the stack
            result = IS_CHANNEL.match(self.channels.pop())

            # Populate our key variables
            workspace = result.group('workspace')
            channel = result.group('channel').lower()

            # Acquire our workspace_id if we can
            if workspace:
                # We always work with the workspace in it's lowercase form
                workspace = workspace.lower()

                # A workspace was defined
                if not len(self._cached_workspaces):
                    # cache our workspaces; this only needs to be done once
                    self._cached_workspaces = self.get_workspaces()

                if workspace not in self._cached_workspaces:
                    # not found
                    self.logger.warning(
                        'The Twist User {} is not associated with the '
                        'Team {}'.format(self.email, workspace))

                    # Toggle our return flag
                    has_error = True
                    continue

                # Store the workspace id
                workspace_id = self._cached_workspaces[workspace]

            else:
                # use default workspace
                workspace_id = self.default_workspace

            # Check to see if our channel exists in our default workspace
            if workspace_id in self._cached_channels \
                    and channel in self._cached_channels[workspace_id]:
                # Store our channel ID
                self.channel_ids.add('{}:{}'.format(
                    workspace_id,
                    self._cached_channels[workspace_id][channel],
                ))
                continue

            # if we reach here, we failed to add our channel
            self.logger.warning(
                'The Channel #{} was not found{}.'.format(
                    channel,
                    '' if not workspace
                    else ' with Team {}'.format(workspace),
                ))

            # Toggle our return flag
            has_error = True
            continue

        # There is no need to handling failed log out attempts at this time
        return not has_error

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Twist Notification
        """

        # error tracking (used for function return)
        has_error = False

        if not self.token and not self.login():
            # We failed to authenticate - we're done
            return False

        if len(self.channels) > 0:
            # Converts channels to their maped IDs if found; this is the only
            # way to send notifications to Twist
            self._channel_migration()

        if not len(self.channel_ids):
            # We have nothing to notify
            return False

        # Notify all of our identified channels
        ids = list(self.channel_ids)
        while len(ids) > 0:
            # Retrieve our Channel Object
            result = IS_CHANNEL_ID.match(ids.pop())

            # We need both the workspace/team id and channel id
            channel_id = int(result.group('channel'))

            # Prepare our payload
            payload = {
                'channel_id': channel_id,
                'title': title,
                'content': body,
            }

            postokay, response = self._fetch(
                'threads/add',
                payload=payload,
            )

            # only toggle has_error flag if we had an error
            if not postokay:
                # Mark our failure
                has_error = True
                continue

            # If we reach here, we were successful
            self.logger.info(
                'Sent Twist notification to {}.'.format(
                    result.group('name')))

        return not has_error

    def _fetch(self, url, payload=None, method='POST', login=False):
        """
        Wrapper to Twist API requests object
        """

        # use what was specified, otherwise build headers dynamically
        headers = {
            'User-Agent': self.app_id,
        }

        headers['Content-Type'] = \
            'application/x-www-form-urlencoded; charset=utf-8'

        if self.token:
            # Set our token
            headers['Authorization'] = 'Bearer {}'.format(self.token)

        # Prepare our api url
        api_url = '{}{}'.format(self.api_url, url)

        # Some Debug Logging
        self.logger.debug('Twist {} URL: {} (cert_verify={})'.format(
            method, api_url, self.verify_certificate))
        self.logger.debug('Twist Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made;
        self.throttle()

        # Initialize a default value for our content value
        content = {}

        # acquire our request mode
        fn = requests.post if method == 'POST' else requests.get
        try:
            r = fn(
                api_url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate)

            # Get our JSON content if it's possible
            try:
                content = loads(r.content)

            except (TypeError, ValueError, AttributeError):
                # TypeError = r.content is not a String
                # ValueError = r.content is Unparsable
                # AttributeError = r.content is None
                content = {}

            # handle authentication errors where our token has just simply
            # expired. The error response content looks like this:
            #  {
            #     "error_code": 200,
            #     "error_uuid": "af80bd0715434231a649f2258d7fb946",
            #     "error_extra": {},
            #     "error_string": "Invalid token"
            #  }
            #
            #  Authentication related codes:
            #    120 = You are not logged in
            #    200 = Invalid Token
            #
            #  Source: https://developer.twist.com/v3/#errors
            #
            #  We attempt to login again and retry the original request
            #  if we aren't in the process of handling a login already
            if r.status_code != requests.codes.ok and login is False \
                    and isinstance(content, dict) and \
                    content.get('error_code') in (120, 200):
                # We failed to authenticate with our token; login one more
                # time and retry this original request
                if self.login():
                    r = fn(
                        api_url,
                        data=payload,
                        headers=headers,
                        verify=self.verify_certificate)

                    # Get our JSON content if it's possible
                    try:
                        content = loads(r.content)

                    except (TypeError, ValueError, AttributeError):
                        # TypeError = r.content is not a String
                        # ValueError = r.content is Unparsable
                        # AttributeError = r.content is None
                        content = {}

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyTwist.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Twist {} to {}: '
                    '{}error={}.'.format(
                        method,
                        api_url,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                return (False, content)

        except requests.RequestException as e:
            self.logger.warning(
                'Exception received when sending Twist {} to {}: '.
                format(method, api_url))
            self.logger.debug('Socket Exception: %s' % str(e))

            # Mark our failure
            return (False, content)

        return (True, content)

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

        if not results.get('user'):
            # A username is required
            return None

        # Acquire our targets
        results['targets'] = NotifyTwist.split_path(results['fullpath'])

        if not results.get('password'):
            # Password is required; we will accept the very first entry on the
            # path as a password instead
            if len(results['targets']) == 0:
                # No targets to get our password from
                return None

            # We need to requote contents since this variable will get
            # unquoted later on in the process.  This step appears a bit
            # hacky, but it allows us to support the password in this location
            #   - twist://user@example.com/password
            results['password'] = NotifyTwist.quote(
                results['targets'].pop(0), safe='')

        else:
            # Now we handle our format:
            #    twist://password:email
            #
            # since URL logic expects
            #    schema://user:password@host
            #
            # you can see how this breaks. The colon at the front delmits
            #  passwords and you can see the twist:// url inverts what we
            #  expect:
            #    twist://password:user@example.com
            #
            # twist://abc123:bob@example.com using normal conventions would
            # have interpreted 'bob' as the password and 'abc123' as the user.
            # For the purpose of apprise simplifying this for us, we need to
            # swap these arguments when we prepare the email.

            _password = results['user']
            results['user'] = results['password']
            results['password'] = _password

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyTwist.parse_list(results['qsd']['to'])

        return results

    def __del__(self):
        """
        Deconstructor
        """
        try:
            self.logout()

        except LookupError:
            # Python v3.5 call to requests can sometimes throw the exception
            #   "/usr/lib64/python3.7/socket.py", line 748, in getaddrinfo
            #   LookupError: unknown encoding: idna
            #
            # This occurs every time when running unit-tests against Apprise:
            # LANG=C.UTF-8 PYTHONPATH=$(pwd) py.test-3.7
            #
            # There has been an open issue on this since Jan 2017.
            #   - https://bugs.python.org/issue29288
            #
            # A ~similar~ issue can be identified here in the requests
            # ticket system as unresolved and has provided work-arounds
            #   - https://github.com/kennethreitz/requests/issues/3578
            pass
