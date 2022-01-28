# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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
# 1. Visit https://www.reddit.com/prefs/apps and scroll to the bottom
# 2. Click on the button that reads 'are you a developer? create an app...'
# 3. Set the mode to `script`,
# 4. Provide a `name`, `description`, `redirect uri` and save it.
# 5. Once the bot is saved, you'll be given a ID (next to the the bot name)
#    and a Secret.

# The App ID will look something like this: YWARPXajkk645m
# The App Secret will look something like this: YZGKc5YNjq3BsC-bf7oBKalBMeb1xA
# The App will also have a location where you can identify the users
# who have access (identified as Developers) to the app itself. You will
# additionally need these credentials authenticate with.

# With this information you'll be able to form the URL:
# reddit://{user}:{password}@{app_id}/{app_secret}

# All of the documentation needed to work with the Reddit API can be found
# here:
#   - https://www.reddit.com/dev/api/
#   - https://www.reddit.com/dev/api/#POST_api_submit
#   - https://github.com/reddit-archive/reddit/wiki/API
import six
import requests
from json import loads
from datetime import timedelta
from datetime import datetime

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_list
from ..utils import parse_bool
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _
from .. import __title__, __version__

# Extend HTTP Error Messages
REDDIT_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token',
}


class RedditMessageKind(object):
    """
    Define the kinds of messages supported
    """
    # Attempt to auto-detect the type prior to passing along the message to
    # Reddit
    AUTO = 'auto'

    # A common message
    SELF = 'self'

    # A Hyperlink
    LINK = 'link'


REDDIT_MESSAGE_KINDS = (
    RedditMessageKind.AUTO,
    RedditMessageKind.SELF,
    RedditMessageKind.LINK,
)


class NotifyReddit(NotifyBase):
    """
    A wrapper for Notify Reddit Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Reddit'

    # The services URL
    service_url = 'https://reddit.com'

    # The default secure protocol
    secure_protocol = 'reddit'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_reddit'

    # The maximum size of the message
    body_maxlen = 6000

    # Maximum title length as defined by the Reddit API
    title_maxlen = 300

    # Default to markdown
    notify_format = NotifyFormat.MARKDOWN

    # The default Notification URL to use
    auth_url = 'https://www.reddit.com/api/v1/access_token'
    submit_url = 'https://oauth.reddit.com/api/submit'

    # Reddit is kind enough to return how many more requests we're allowed to
    # continue to make within it's header response as:
    # X-RateLimit-Reset: The epoc time (in seconds) we can expect our
    #                    rate-limit to be reset.
    # X-RateLimit-Remaining: an integer identifying how many requests we're
    #                        still allow to make.
    request_rate_per_sec = 0

    # For Tracking Purposes
    ratelimit_reset = datetime.utcnow()

    # Default to 1.0
    ratelimit_remaining = 1.0

    # Taken right from google.auth.helpers:
    clock_skew = timedelta(seconds=10)

    # 1 hour in seconds (the lifetime of our token)
    access_token_lifetime_sec = timedelta(seconds=3600)

    # Define object templates
    templates = (
        '{schema}://{user}:{password}@{app_id}/{app_secret}/{targets}',
    )

    # Define our template arguments
    template_tokens = dict(NotifyBase.template_tokens, **{
        'user': {
            'name': _('User Name'),
            'type': 'string',
            'required': True,
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'app_id': {
            'name': _('Application ID'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[a-z0-9_-]+$', 'i'),
        },
        'app_secret': {
            'name': _('Application Secret'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[a-z0-9_-]+$', 'i'),
        },
        'target_subreddit': {
            'name': _('Target Subreddit'),
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
        'kind': {
            'name': _('Kind'),
            'type': 'choice:string',
            'values': REDDIT_MESSAGE_KINDS,
            'default': RedditMessageKind.AUTO,
        },
        'flair_id': {
            'name': _('Flair ID'),
            'type': 'string',
            'map_to': 'flair_id',
        },
        'flair_text': {
            'name': _('Flair Text'),
            'type': 'string',
            'map_to': 'flair_text',
        },
        'nsfw': {
            'name': _('NSFW'),
            'type': 'bool',
            'default': False,
            'map_to': 'nsfw',
        },
        'ad': {
            'name': _('Is Ad?'),
            'type': 'bool',
            'default': False,
            'map_to': 'advertisement',
        },
        'replies': {
            'name': _('Send Replies'),
            'type': 'bool',
            'default': True,
            'map_to': 'sendreplies',
        },
        'spoiler': {
            'name': _('Is Spoiler'),
            'type': 'bool',
            'default': False,
            'map_to': 'spoiler',
        },
        'resubmit': {
            'name': _('Resubmit Flag'),
            'type': 'bool',
            'default': False,
            'map_to': 'resubmit',
        },
    })

    def __init__(self, app_id=None, app_secret=None, targets=None,
                 kind=None, nsfw=False, sendreplies=True, resubmit=False,
                 spoiler=False, advertisement=False,
                 flair_id=None, flair_text=None, **kwargs):
        """
        Initialize Notify Reddit Object
        """
        super(NotifyReddit, self).__init__(**kwargs)

        # Initialize subreddit list
        self.subreddits = set()

        # Not Safe For Work Flag
        self.nsfw = nsfw

        # Send Replies Flag
        self.sendreplies = sendreplies

        # Is Spoiler Flag
        self.spoiler = spoiler

        # Resubmit Flag
        self.resubmit = resubmit

        # Is Ad?
        self.advertisement = advertisement

        # Flair details
        self.flair_id = flair_id
        self.flair_text = flair_text

        # Our keys we build using the provided content
        self.__refresh_token = None
        self.__access_token = None
        self.__access_token_expiry = datetime.utcnow()

        self.kind = kind.strip().lower() \
            if isinstance(kind, six.string_types) \
            else self.template_args['kind']['default']

        if self.kind not in REDDIT_MESSAGE_KINDS:
            msg = 'An invalid Reddit message kind ({}) was specified'.format(
                kind)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.user = validate_regex(self.user)
        if not self.user:
            msg = 'An invalid Reddit User ID ' \
                  '({}) was specified'.format(self.user)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.password = validate_regex(self.password)
        if not self.password:
            msg = 'An invalid Reddit Password ' \
                  '({}) was specified'.format(self.password)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.client_id = validate_regex(
            app_id, *self.template_tokens['app_id']['regex'])
        if not self.client_id:
            msg = 'An invalid Reddit App ID ' \
                  '({}) was specified'.format(app_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.client_secret = validate_regex(
            app_secret, *self.template_tokens['app_secret']['regex'])
        if not self.client_secret:
            msg = 'An invalid Reddit App Secret ' \
                  '({}) was specified'.format(app_secret)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Build list of subreddits
        self.subreddits = [
            sr.lstrip('#') for sr in parse_list(targets) if sr.lstrip('#')]

        if not self.subreddits:
            self.logger.warning(
                'No subreddits were identified to be notified')
        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'kind': self.kind,
            'ad': 'yes' if self.advertisement else 'no',
            'nsfw': 'yes' if self.nsfw else 'no',
            'resubmit': 'yes' if self.resubmit else 'no',
            'replies': 'yes' if self.sendreplies else 'no',
            'spoiler': 'yes' if self.spoiler else 'no',
        }

        # Flair support
        if self.flair_id:
            params['flair_id'] = self.flair_id

        if self.flair_text:
            params['flair_text'] = self.flair_text

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{user}:{password}@{app_id}/{app_secret}' \
            '/{targets}/?{params}'.format(
                schema=self.secure_protocol,
                user=NotifyReddit.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
                app_id=self.pprint(
                    self.client_id, privacy, mode=PrivacyMode.Secret, safe=''),
                app_secret=self.pprint(
                    self.client_secret, privacy, mode=PrivacyMode.Secret,
                    safe=''),
                targets='/'.join(
                    [NotifyReddit.quote(x, safe='') for x in self.subreddits]),
                params=NotifyReddit.urlencode(params),
            )

    def login(self):
        """
        A simple wrapper to authenticate with the Reddit Server
        """

        # Prepare our payload
        payload = {
            'grant_type': 'password',
            'username': self.user,
            'password': self.password,
        }

        # Enforce a False flag setting before calling _fetch()
        self.__access_token = False

        # Send Login Information
        postokay, response = self._fetch(
            self.auth_url,
            payload=payload,
        )

        if not postokay or not response:
            # Setting this variable to False as a way of letting us know
            # we failed to authenticate on our last attempt
            self.__access_token = False
            return False

        # Our response object looks like this (content has been altered for
        # presentation purposes):
        # {
        #     "access_token": Your access token,
        #     "token_type": "bearer",
        #     "expires_in": Unix Epoch Seconds,
        #     "scope": A scope string,
        #     "refresh_token": Your refresh token
        # }

        # Acquire our token
        self.__access_token = response.get('access_token')

        # Handle other optional arguments we can use
        if 'expires_in' in response:
            delta = timedelta(seconds=int(response['expires_in']))
            self.__access_token_expiry = \
                delta + datetime.utcnow() - self.clock_skew
        else:
            self.__access_token_expiry = self.access_token_lifetime_sec + \
                datetime.utcnow() - self.clock_skew

        # The Refresh Token
        self.__refresh_token = response.get(
            'refresh_token', self.__refresh_token)

        if self.__access_token:
            self.logger.info('Authenticated to Reddit as {}'.format(self.user))
            return True

        self.logger.warning(
            'Failed to authenticate to Reddit as {}'.format(self.user))

        # Mark our failure
        return False

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Reddit Notification
        """

        # error tracking (used for function return)
        has_error = False

        if not self.__access_token and not self.login():
            # We failed to authenticate - we're done
            return False

        if not len(self.subreddits):
            # We have nothing to notify; we're done
            self.logger.warning('There are no Reddit targets to notify')
            return False

        # Prepare our Message Type/Kind
        if self.kind == RedditMessageKind.AUTO:
            parsed = NotifyBase.parse_url(body)
            # Detect a link
            if parsed and parsed.get('schema', '').startswith('http') \
                    and parsed.get('host'):
                kind = RedditMessageKind.LINK

            else:
                kind = RedditMessageKind.SELF
        else:
            kind = self.kind

        # Create a copy of the subreddits list
        subreddits = list(self.subreddits)
        while len(subreddits) > 0:
            # Retrieve our subreddit
            subreddit = subreddits.pop()

            # Prepare our payload
            payload = {
                'ad': True if self.advertisement else False,
                'api_type': 'json',
                'extension': 'json',
                'sr': subreddit,
                'title': title if title else self.app_desc,
                'kind': kind,
                'nsfw': True if self.nsfw else False,
                'resubmit': True if self.resubmit else False,
                'sendreplies': True if self.sendreplies else False,
                'spoiler': True if self.spoiler else False,
            }

            if self.flair_id:
                payload['flair_id'] = self.flair_id

            if self.flair_text:
                payload['flair_text'] = self.flair_text

            if kind == RedditMessageKind.LINK:
                payload.update({
                    'url': body,
                })
            else:
                payload.update({
                    'text': body,
                })

            postokay, response = self._fetch(self.submit_url, payload=payload)
            # only toggle has_error flag if we had an error
            if not postokay:
                # Mark our failure
                has_error = True
                continue

            # If we reach here, we were successful
            self.logger.info(
                'Sent Reddit notification to {}'.format(
                    subreddit))

        return not has_error

    def _fetch(self, url, payload=None):
        """
        Wrapper to Reddit API requests object
        """

        # use what was specified, otherwise build headers dynamically
        headers = {
            'User-Agent': '{} v{}'.format(__title__, __version__)
        }

        if self.__access_token:
            # Set our token
            headers['Authorization'] = 'Bearer {}'.format(self.__access_token)

        # Prepare our url
        url = self.submit_url if self.__access_token else self.auth_url

        # Some Debug Logging
        self.logger.debug('Reddit POST URL: {} (cert_verify={})'.format(
            url, self.verify_certificate))
        self.logger.debug('Reddit Payload: %s' % str(payload))

        # By default set wait to None
        wait = None

        if self.ratelimit_remaining <= 0.0:
            # Determine how long we should wait for or if we should wait at
            # all. This isn't fool-proof because we can't be sure the client
            # time (calling this script) is completely synced up with the
            # Gitter server.  One would hope we're on NTP and our clocks are
            # the same allowing this to role smoothly:

            now = datetime.utcnow()
            if now < self.ratelimit_reset:
                # We need to throttle for the difference in seconds
                wait = abs(
                    (self.ratelimit_reset - now + self.clock_skew)
                    .total_seconds())

        # Always call throttle before any remote server i/o is made;
        self.throttle(wait=wait)

        # Initialize a default value for our content value
        content = {}

        # acquire our request mode
        try:
            r = requests.post(
                url,
                data=payload,
                auth=None if self.__access_token
                else (self.client_id, self.client_secret),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            #  We attempt to login again and retry the original request
            #  if we aren't in the process of handling a login already
            if r.status_code != requests.codes.ok \
                    and self.__access_token and url != self.auth_url:

                # We had a problem
                status_str = \
                    NotifyReddit.http_response_code_lookup(
                        r.status_code, REDDIT_HTTP_ERROR_MAP)

                self.logger.debug(
                    'Taking countermeasures after failed to send to Reddit '
                    '{}: {}error={}'.format(
                        url,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # We failed to authenticate with our token; login one more
                # time and retry this original request
                if not self.login():
                    return (False, {})

                # Try again
                r = requests.post(
                    url,
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout
                )

            # Get our JSON content if it's possible
            try:
                content = loads(r.content)

            except (TypeError, ValueError, AttributeError):
                # TypeError = r.content is not a String
                # ValueError = r.content is Unparsable
                # AttributeError = r.content is None

                # We had a problem
                status_str = \
                    NotifyReddit.http_response_code_lookup(
                        r.status_code, REDDIT_HTTP_ERROR_MAP)

                # Reddit always returns a JSON response
                self.logger.warning(
                    'Failed to send to Reddit after countermeasures {}: '
                    '{}error={}'.format(
                        url,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))
                return (False, {})

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyReddit.http_response_code_lookup(
                        r.status_code, REDDIT_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send to Reddit {}: '
                    '{}error={}'.format(
                        url,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                return (False, content)

            errors = [] if not content else \
                content.get('json', {}).get('errors', [])
            if errors:
                self.logger.warning(
                    'Failed to send to Reddit {}: '
                    '{}'.format(
                        url,
                        str(errors)))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                return (False, content)

            try:
                # Store our rate limiting (if provided)
                self.ratelimit_remaining = \
                    float(r.headers.get(
                        'X-RateLimit-Remaining'))
                self.ratelimit_reset = datetime.utcfromtimestamp(
                    int(r.headers.get('X-RateLimit-Reset')))

            except (TypeError, ValueError):
                # This is returned if we could not retrieve this information
                # gracefully accept this state and move on
                pass

        except requests.RequestException as e:
            self.logger.warning(
                'Exception received when sending Reddit to {}'.
                format(url))
            self.logger.debug('Socket Exception: %s' % str(e))

            # Mark our failure
            return (False, content)

        return (True, content)

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

        # Acquire our targets
        results['targets'] = NotifyReddit.split_path(results['fullpath'])

        # Kind override
        if 'kind' in results['qsd'] and results['qsd']['kind']:
            results['kind'] = NotifyReddit.unquote(
                results['qsd']['kind'].strip().lower())
        else:
            results['kind'] = RedditMessageKind.AUTO

        # Is an Ad?
        results['ad'] = \
            parse_bool(results['qsd'].get('ad', False))

        # Get Not Safe For Work (NSFW) Flag
        results['nsfw'] = \
            parse_bool(results['qsd'].get('nsfw', False))

        # Send Replies Flag
        results['replies'] = \
            parse_bool(results['qsd'].get('replies', True))

        # Resubmit Flag
        results['resubmit'] = \
            parse_bool(results['qsd'].get('resubmit', False))

        # Is Spoiler Flag
        results['spoiler'] = \
            parse_bool(results['qsd'].get('spoiler', False))

        if 'flair_text' in results['qsd']:
            results['flair_text'] = \
                NotifyReddit.unquote(results['qsd']['flair_text'])

        if 'flair_id' in results['qsd']:
            results['flair_id'] = \
                NotifyReddit.unquote(results['qsd']['flair_id'])

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyReddit.parse_list(results['qsd']['to'])

        if 'app_id' in results['qsd']:
            results['app_id'] = \
                NotifyReddit.unquote(results['qsd']['app_id'])
        else:
            # The App/Bot ID is the hostname
            results['app_id'] = NotifyReddit.unquote(results['host'])

        if 'app_secret' in results['qsd']:
            results['app_secret'] = \
                NotifyReddit.unquote(results['qsd']['app_secret'])
        else:
            # The first target identified is the App secret
            results['app_secret'] = \
                None if not results['targets'] else results['targets'].pop(0)

        return results
