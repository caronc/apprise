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

# See https://developer.twitter.com/en/docs/direct-messages/\
#           sending-and-receiving/api-reference/new-event.html
import re
import six
import requests
from datetime import datetime
from requests_oauthlib import OAuth1
from json import dumps
from json import loads
from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import parse_list
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _

IS_USER = re.compile(r'^\s*@?(?P<user>[A-Z0-9_]+)$', re.I)


class TwitterMessageMode(object):
    """
    Twitter Message Mode
    """
    # DM (a Direct Message)
    DM = 'dm'

    # A Public Tweet
    TWEET = 'tweet'


# Define the types in a list for validation purposes
TWITTER_MESSAGE_MODES = (
    TwitterMessageMode.DM,
    TwitterMessageMode.TWEET,
)


class NotifyTwitter(NotifyBase):
    """
    A wrapper to Twitter Notifications

    """

    # The default descriptive name associated with the Notification
    service_name = 'Twitter'

    # The services URL
    service_url = 'https://twitter.com/'

    # The default secure protocol is twitter.  'tweet' is left behind
    # for backwards compatibility of older apprise usage
    secure_protocol = ('twitter', 'tweet')

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_twitter'

    # Do not set body_maxlen as it is set in a property value below
    # since the length varies depending if we are doing a direct message
    # or a tweet
    # body_maxlen = see below @propery defined

    # Twitter does have titles when creating a message
    title_maxlen = 0

    # Twitter API
    twitter_api = 'api.twitter.com'

    # Twitter API Reference To Acquire Someone's Twitter ID
    twitter_lookup = 'https://api.twitter.com/1.1/users/lookup.json'

    # Twitter API Reference To Acquire Current Users Information
    twitter_whoami = \
        'https://api.twitter.com/1.1/account/verify_credentials.json'

    # Twitter API Reference To Send A Private DM
    twitter_dm = 'https://api.twitter.com/1.1/direct_messages/events/new.json'

    # Twitter API Reference To Send A Public Tweet
    twitter_tweet = 'https://api.twitter.com/1.1/statuses/update.json'

    # Twitter is kind enough to return how many more requests we're allowed to
    # continue to make within it's header response as:
    # X-Rate-Limit-Reset: The epoc time (in seconds) we can expect our
    #                    rate-limit to be reset.
    # X-Rate-Limit-Remaining: an integer identifying how many requests we're
    #                        still allow to make.
    request_rate_per_sec = 0

    # For Tracking Purposes
    ratelimit_reset = datetime.utcnow()

    # Default to 1000; users can send up to 1000 DM's and 2400 tweets a day
    # This value only get's adjusted if the server sets it that way
    ratelimit_remaining = 1

    templates = (
        '{schema}://{ckey}/{csecret}/{akey}/{asecret}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'ckey': {
            'name': _('Consumer Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'csecret': {
            'name': _('Consumer Secret'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'akey': {
            'name': _('Access Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'asecret': {
            'name': _('Access Secret'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_user': {
            'name': _('Target User'),
            'type': 'string',
            'prefix': '@',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'mode': {
            'name': _('Message Mode'),
            'type': 'choice:string',
            'values': TWITTER_MESSAGE_MODES,
            'default': TwitterMessageMode.DM,
        },
        'cache': {
            'name': _('Cache Results'),
            'type': 'bool',
            'default': True,
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, ckey, csecret, akey, asecret, targets=None,
                 mode=TwitterMessageMode.DM, cache=True, **kwargs):
        """
        Initialize Twitter Object

        """
        super(NotifyTwitter, self).__init__(**kwargs)

        if not ckey:
            msg = 'An invalid Consumer API Key was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not csecret:
            msg = 'An invalid Consumer Secret API Key was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not akey:
            msg = 'An invalid Access Token API Key was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not asecret:
            msg = 'An invalid Access Token Secret API Key was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our webhook mode
        self.mode = None \
            if not isinstance(mode, six.string_types) else mode.lower()

        # Set Cache Flag
        self.cache = cache

        if self.mode not in TWITTER_MESSAGE_MODES:
            msg = 'The Twitter message mode specified ({}) is invalid.' \
                .format(mode)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Identify our targets
        self.targets = []
        for target in parse_list(targets):
            match = IS_USER.match(target)
            if match and match.group('user'):
                self.targets.append(match.group('user'))
                continue

            self.logger.warning(
                'Dropped invalid user ({}) specified.'.format(target),
            )

        # Store our data
        self.ckey = ckey
        self.csecret = csecret
        self.akey = akey
        self.asecret = asecret

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Twitter Notification
        """

        # Call the _send_ function applicable to whatever mode we're in
        # - calls _send_tweet if the mode is set so
        # - calls _send_dm (direct message) otherwise
        return getattr(self, '_send_{}'.format(self.mode))(
            body=body, title=title, notify_type=notify_type, **kwargs)

    def _send_tweet(self, body, title='', notify_type=NotifyType.INFO,
                    **kwargs):
        """
        Twitter Public Tweet
        """

        payload = {
            'status': body,
        }

        # Send Tweet
        postokay, response = self._fetch(
            self.twitter_tweet,
            payload=payload,
            json=False,
        )

        if postokay:
            self.logger.info(
                'Sent Twitter notification as public tweet.')

        return postokay

    def _send_dm(self, body, title='', notify_type=NotifyType.INFO,
                 **kwargs):
        """
        Twitter Direct Message
        """

        # Error Tracking
        has_error = False

        payload = {
            'event': {
                'type': 'message_create',
                'message_create': {
                    'target': {
                        # This gets assigned
                        'recipient_id': None,
                    },
                    'message_data': {
                        'text': body,
                    }
                }
            }
        }

        # Lookup our users
        targets = self._whoami(lazy=self.cache) if not len(self.targets) \
            else self._user_lookup(self.targets, lazy=self.cache)

        if not targets:
            # We failed to lookup any users
            self.logger.warning(
                'Failed to acquire user(s) to Direct Message via Twitter')
            return False

        for screen_name, user_id in targets.items():
            # Assign our user
            payload['event']['message_create']['target']['recipient_id'] = \
                user_id

            # Send Twitter DM
            postokay, response = self._fetch(
                self.twitter_dm,
                payload=payload,
            )

            if not postokay:
                # Track our error
                has_error = True
                continue

            self.logger.info(
                'Sent Twitter DM notification to @{}.'.format(screen_name))

        return not has_error

    def _whoami(self, lazy=True):
        """
        Looks details of current authenticated user

        """

        # Prepare a whoami key; this is to prevent conflict with other
        # NotifyTwitter declarations that may or may not use a different
        # set of authentication keys
        whoami_key = '{}{}{}{}'.format(
            self.ckey, self.csecret, self.akey, self.asecret)

        if lazy and hasattr(NotifyTwitter, '_whoami_cache') \
                and whoami_key in getattr(NotifyTwitter, '_whoami_cache'):
            # Use cached response
            return getattr(NotifyTwitter, '_whoami_cache')[whoami_key]

        # Contains a mapping of screen_name to id
        results = {}

        # Send Twitter DM
        postokay, response = self._fetch(
            self.twitter_whoami,
            method='GET',
            json=False,
        )

        if postokay:
            try:
                results[response['screen_name']] = response['id']

                if lazy:
                    # Cache our response for future references
                    if not hasattr(NotifyTwitter, '_whoami_cache'):
                        setattr(
                            NotifyTwitter, '_whoami_cache',
                            {whoami_key: results})
                    else:
                        getattr(NotifyTwitter, '_whoami_cache')\
                            .update({whoami_key: results})

                    # Update our user cache as well
                    if not hasattr(NotifyTwitter, '_user_cache'):
                        setattr(NotifyTwitter, '_user_cache', results)
                    else:
                        getattr(NotifyTwitter, '_user_cache').update(results)

            except (TypeError, KeyError):
                pass

        return results

    def _user_lookup(self, screen_name, lazy=True):
        """
        Looks up a screen name and returns the user id

        the screen_name can be a list/set/tuple as well
        """

        # Contains a mapping of screen_name to id
        results = {}

        # Build a unique set of names
        names = parse_list(screen_name)

        if lazy and hasattr(NotifyTwitter, '_user_cache'):
            # Use cached response
            results = {k: v for k, v in getattr(
                NotifyTwitter, '_user_cache').items() if k in names}

            # limit our names if they already exist in our cache
            names = [name for name in names if name not in results]

        if not len(names):
            # They're is nothing further to do
            return results

        # Twitters API documents that it can lookup to 100
        # results at a time.
        # https://developer.twitter.com/en/docs/accounts-and-users/\
        #     follow-search-get-users/api-reference/get-users-lookup
        for i in range(0, len(names), 100):
            # Send Twitter DM
            postokay, response = self._fetch(
                self.twitter_lookup,
                payload={
                    'screen_name': names[i:i + 100],
                },
                json=False,
            )

            if not postokay or not isinstance(response, list):
                # Track our error
                continue

            # Update our user index
            for entry in response:
                try:
                    results[entry['screen_name']] = entry['id']

                except (TypeError, KeyError):
                    pass

        # Cache our response for future use; this saves on un-nessisary extra
        # hits against the Twitter API when we already know the answer
        if lazy:
            if not hasattr(NotifyTwitter, '_user_cache'):
                setattr(NotifyTwitter, '_user_cache', results)
            else:
                getattr(NotifyTwitter, '_user_cache').update(results)

        return results

    def _fetch(self, url, payload=None, method='POST', json=True):
        """
        Wrapper to Twitter API requests object
        """

        headers = {
            'Host': self.twitter_api,
            'User-Agent': self.app_id,
        }

        if json:
            headers['Content-Type'] = 'application/json'
            payload = dumps(payload)

        auth = OAuth1(
            self.ckey,
            client_secret=self.csecret,
            resource_owner_key=self.akey,
            resource_owner_secret=self.asecret,
        )

        # Some Debug Logging
        self.logger.debug('Twitter {} URL: {} (cert_verify={})'.format(
            method, url, self.verify_certificate))
        self.logger.debug('Twitter Payload: %s' % str(payload))

        # By default set wait to None
        wait = None

        if self.ratelimit_remaining == 0:
            # Determine how long we should wait for or if we should wait at
            # all. This isn't fool-proof because we can't be sure the client
            # time (calling this script) is completely synced up with the
            # Gitter server.  One would hope we're on NTP and our clocks are
            # the same allowing this to role smoothly:

            now = datetime.utcnow()
            if now < self.ratelimit_reset:
                # We need to throttle for the difference in seconds
                # We add 0.5 seconds to the end just to allow a grace
                # period.
                wait = (self.ratelimit_reset - now).total_seconds() + 0.5

        # Default content response object
        content = {}

        # Always call throttle before any remote server i/o is made;
        self.throttle(wait=wait)

        # acquire our request mode
        fn = requests.post if method == 'POST' else requests.get
        try:
            r = fn(
                url,
                data=payload,
                headers=headers,
                auth=auth,
                verify=self.verify_certificate)

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyTwitter.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Twitter {} to {}: '
                    '{}error={}.'.format(
                        method,
                        url,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                return (False, content)

            try:
                content = loads(r.content)

            except (TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                content = {}

            try:
                # Capture rate limiting if possible
                self.ratelimit_remaining = \
                    int(r.headers.get('x-rate-limit-remaining'))
                self.ratelimit_reset = datetime.utcfromtimestamp(
                    int(r.headers.get('x-rate-limit-reset')))

            except (TypeError, ValueError):
                # This is returned if we could not retrieve this information
                # gracefully accept this state and move on
                pass

        except requests.RequestException as e:
            self.logger.warning(
                'Exception received when sending Twitter {} to {}: '.
                format(method, url))
            self.logger.debug('Socket Exception: %s' % str(e))

            # Mark our failure
            return (False, content)

        return (True, content)

    @property
    def body_maxlen(self):
        """
        The maximum allowable characters allowed in the body per message
        This is used during a Private DM Message Size (not Public Tweets
        which are limited to 280 characters)
        """
        return 10000 if self.mode == TwitterMessageMode.DM else 280

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'mode': self.mode,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        if len(self.targets) > 0:
            args['to'] = ','.join([NotifyTwitter.quote(x, safe='')
                                   for x in self.targets])

        return '{schema}://{ckey}/{csecret}/{akey}/{asecret}' \
            '/{targets}/?{args}'.format(
                schema=self.secure_protocol[0],
                ckey=NotifyTwitter.quote(self.ckey, safe=''),
                asecret=NotifyTwitter.quote(self.csecret, safe=''),
                akey=NotifyTwitter.quote(self.akey, safe=''),
                csecret=NotifyTwitter.quote(self.asecret, safe=''),
                targets='/'.join(
                    [NotifyTwitter.quote('@{}'.format(target), safe='')
                     for target in self.targets]),
                args=NotifyTwitter.urlencode(args))

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # The first token is stored in the hostname
        consumer_key = NotifyTwitter.unquote(results['host'])

        # Acquire remaining tokens
        tokens = NotifyTwitter.split_path(results['fullpath'])

        # Now fetch the remaining tokens
        try:
            consumer_secret, access_token_key, access_token_secret = \
                tokens[0:3]

        except (ValueError, AttributeError, IndexError):
            # Force some bad values that will get caught
            # in parsing later
            consumer_secret = None
            access_token_key = None
            access_token_secret = None

        results['ckey'] = consumer_key
        results['csecret'] = consumer_secret
        results['akey'] = access_token_key
        results['asecret'] = access_token_secret

        # The defined twitter mode
        if 'mode' in results['qsd'] and len(results['qsd']['mode']):
            results['mode'] = \
                NotifyTwitter.unquote(results['qsd']['mode'])

        results['targets'] = []

        # if a user has been defined, add it to the list of targets
        if results.get('user'):
            results['targets'].append(results.get('user'))

        # Store any remaining items as potential targets
        results['targets'].extend(tokens[3:])

        if 'cache' in results['qsd'] and len(results['qsd']['cache']):
            results['cache'] = \
                parse_bool(results['qsd']['cache'], True)

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyTwitter.parse_list(results['qsd']['to'])

        if results.get('schema', 'twitter').lower() == 'tweet':
            # Deprication Notice issued for v0.7.9
            NotifyTwitter.logger.deprecate(
                'tweet:// has been replaced by twitter://')

        return results
