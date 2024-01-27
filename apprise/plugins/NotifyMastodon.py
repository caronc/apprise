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
from copy import deepcopy
from json import dumps, loads
from datetime import datetime
from datetime import timezone

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyImageSize
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_list
from ..utils import parse_bool
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _
from ..attachment.AttachBase import AttachBase

# Accept:
# - @username
# - username
# - username@host.com
# - @username@host.com
IS_USER = re.compile(
    r'^\s*@?(?P<user>[A-Z0-9_]+(?:@(?P<host>[A-Z0-9_.-]+))?)$', re.I)

USER_DETECTION_RE = re.compile(
    r'(@[A-Z0-9_]+(?:@[A-Z0-9_.-]+)?)(?=$|[\s,.&()\[\]]+)', re.I)


class MastodonMessageVisibility:
    """
    The visibility of any status message made
    """
    # post visibility defaults to the accounts default-visibilty setting
    DEFAULT = 'default'

    # post will be visible only to mentioned users
    # similar to a Twitter DM
    DIRECT = 'direct'

    # post will be visible only to followers
    PRIVATE = 'private'

    # post will be public but not appear on the public timeline
    UNLISTED = 'unlisted'

    # post will be public
    PUBLIC = 'public'


# Define the types in a list for validation purposes
MASTODON_MESSAGE_VISIBILITIES = (
    MastodonMessageVisibility.DEFAULT,
    MastodonMessageVisibility.DIRECT,
    MastodonMessageVisibility.PRIVATE,
    MastodonMessageVisibility.UNLISTED,
    MastodonMessageVisibility.PUBLIC,
)


class NotifyMastodon(NotifyBase):
    """
    A wrapper for Notify Mastodon Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Mastodon'

    # The services URL
    service_url = 'https://joinmastodon.org'

    # The default protocol
    protocol = ('mastodon', 'toot')

    # The default secure protocol
    secure_protocol = ('mastodons', 'toots')

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_mastodon'

    # Support attachments
    attachment_support = True

    # Allows the user to specify the NotifyImageSize object
    # Allows the user to specify the NotifyImageSize object; this is supported
    # through the webhook
    image_size = NotifyImageSize.XY_128

    # it is documented on the site that the maximum images per toot
    # is 4 (unless it's a GIF, then it's only 1)
    __toot_non_gif_images_batch = 4

    # Mastodon API Reference To Acquire Current Users Information
    # See: https://docs.joinmastodon.org/methods/accounts/
    # Requires Scope Element: read:accounts
    mastodon_whoami = '/api/v1/accounts/verify_credentials'

    # URL for posting media files
    mastodon_media = '/api/v1/media'

    # URL for posting status messages
    mastodon_toot = '/api/v1/statuses'

    # URL for posting direct messages
    mastodon_dm = '/api/v1/dm'

    # The title is not used
    title_maxlen = 0

    # The maximum size of the message
    body_maxlen = 500

    # Default to text
    notify_format = NotifyFormat.TEXT

    # Mastodon is kind enough to return how many more requests we're allowed to
    # continue to make within it's header response as:
    # X-Rate-Limit-Reset: The epoc time (in seconds) we can expect our
    #                    rate-limit to be reset.
    # X-Rate-Limit-Remaining: an integer identifying how many requests we're
    #                        still allow to make.
    request_rate_per_sec = 0

    # For Tracking Purposes
    ratelimit_reset = datetime.now(timezone.utc).replace(tzinfo=None)

    # Default to 1000; users can send up to 1000 DM's and 2400 toot a day
    # This value only get's adjusted if the server sets it that way
    ratelimit_remaining = 1

    # Define object templates
    templates = (
        '{schema}://{token}@{host}',
        '{schema}://{token}@{host}:{port}',
        '{schema}://{token}@{host}/{targets}',
        '{schema}://{token}@{host}:{port}/{targets}',
    )

    # Define our template arguments
    template_tokens = dict(NotifyBase.template_tokens, **{
        'host': {
            'name': _('Hostname'),
            'type': 'string',
            'required': True,
        },
        'token': {
            'name': _('Access Token'),
            'type': 'string',
            'required': True,
        },
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
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
        'token': {
            'alias_of': 'token',
        },
        'visibility': {
            'name': _('Visibility'),
            'type': 'choice:string',
            'values': MASTODON_MESSAGE_VISIBILITIES,
            'default': MastodonMessageVisibility.DEFAULT,
        },
        'cache': {
            'name': _('Cache Results'),
            'type': 'bool',
            'default': True,
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': True,
        },
        'sensitive': {
            'name': _('Sensitive Attachments'),
            'type': 'bool',
            'default': False,
        },
        'spoiler': {
            'name': _('Spoiler Text'),
            'type': 'string',
        },
        'key': {
            'name': _('Idempotency-Key'),
            'type': 'string',
        },
        'language': {
            'name': _('Language Code'),
            'type': 'string',
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, token=None, targets=None, batch=True,
                 sensitive=None, spoiler=None, visibility=None, cache=True,
                 key=None, language=None, **kwargs):
        """
        Initialize Notify Mastodon Object
        """
        super().__init__(**kwargs)

        # Set our schema
        self.schema = 'https' if self.secure else 'http'

        # Initialize our cache value
        self._whoami_cache = None

        self.token = validate_regex(token)
        if not self.token:
            msg = 'An invalid Mastodon Access Token was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if visibility:
            # Input is a string; attempt to get the lookup from our
            # sound mapping
            vis = 'invalid' if not isinstance(visibility, str) \
                else visibility.lower().strip()

            # This little bit of black magic allows us to match against
            # against multiple versions of the same string
            # ... etc
            self.visibility = \
                next((v for v in MASTODON_MESSAGE_VISIBILITIES
                      if v.startswith(vis)), None)

            if self.visibility not in MASTODON_MESSAGE_VISIBILITIES:
                msg = 'The Mastodon visibility specified ({}) is invalid.' \
                    .format(visibility)
                self.logger.warning(msg)
                raise TypeError(msg)

        else:
            self.visibility = \
                self.template_args['visibility']['default']

        # Prepare our URL
        self.api_url = '%s://%s' % (self.schema, self.host)

        if isinstance(self.port, int):
            self.api_url += ':%d' % self.port

        # Set Cache Flag
        self.cache = cache

        # Prepare Image Batch Mode Flag
        self.batch = self.template_args['batch']['default'] \
            if batch is None else batch

        # Images to be marked sensitive
        self.sensitive = self.template_args['sensitive']['default'] \
            if sensitive is None else sensitive

        # Text marked as being a spoiler
        self.spoiler = spoiler if isinstance(spoiler, str) else None

        # Idempotency Key
        self.idempotency_key = key if isinstance(key, str) else None

        # Over-ride default language (ISO 639) (e.g: en, fr, es, etc)
        self.language = language if isinstance(language, str) else None

        # Our target users
        self.targets = []

        # Track any errors
        has_error = False

        # Identify our targets
        for target in parse_list(targets):
            match = IS_USER.match(target)
            if match and match.group('user'):
                self.targets.append('@' + match.group('user'))
                continue

            has_error = True
            self.logger.warning(
                'Dropped invalid Mastodon user ({}) specified.'.format(target),
            )

        if has_error and not self.targets:
            # We have specified that we want to notify one or more individual
            # and we failed to load any of them.  Since it's also valid to
            # notify no one at all (which means we notify ourselves), it's
            # important we don't switch from the users original intentions
            msg = 'No Mastodon targets to notify.'
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'visibility': self.visibility,
            'batch': 'yes' if self.batch else 'no',
            'sensitive': 'yes' if self.sensitive else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.spoiler:
            # Our Spoiler if one was specified
            params['spoiler'] = self.spoiler

        if self.idempotency_key:
            # Our Idempotency Key
            params['key'] = self.idempotency_key

        if self.language:
            # Override Language
            params['language'] = self.language

        default_port = 443 if self.secure else 80

        return '{schema}://{token}@{host}{port}/{targets}?{params}'.format(
            schema=self.secure_protocol[0]
            if self.secure else self.protocol[0],
            token=self.pprint(
                self.token, privacy, mode=PrivacyMode.Secret, safe=''),
            # never encode hostname since we're expecting it to be a valid one
            host=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            targets='/'.join(
                [NotifyMastodon.quote(x, safe='@') for x in self.targets]),
            params=NotifyMastodon.urlencode(params),
        )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        targets = len(self.targets)
        return targets if targets > 0 else 1

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        wrapper to _send since we can alert more then one channel
        """

        # Build a list of our attachments
        attachments = []

        # Smart Target Detection for Direct Messages; this prevents us from
        # adding @user entries that were already placed in the message body
        users = set(USER_DETECTION_RE.findall(body))
        targets = users - set(self.targets.copy())
        if not self.targets and self.visibility == \
                MastodonMessageVisibility.DIRECT:

            result = self._whoami()
            if not result:
                # Could not access our status
                return False

            myself = '@' + next(iter(result.keys()))
            if myself in users:
                targets.remove(myself)

            else:
                targets.add(myself)

        if attach and self.attachment_support:
            # We need to upload our payload first so that we can source it
            # in remaining messages
            for attachment in attach:
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                #
                # Images (PNG, JPG, GIF) up to 8MB.
                #  - Images will be downscaled to 1.6 megapixels (enough for a
                #    1280x1280 image).
                #  -  Up to 4 images can be attached.
                #  -  Animated GIFs are converted to soundless MP4s like on
                #     Imgur/Gfycat (GIFV).
                #  - You can also upload soundless MP4 and WebM, which will
                #     be handled the same way.
                # Videos (MP4, M4V, MOV, WebM) up to 40MB.
                #  - Video will be transcoded to H.264 MP4 with a maximum
                #     bitrate of 1300kbps and framerate of 60fps.
                # Audio (MP3, OGG, WAV, FLAC, OPUS, AAC, M4A, 3GP) up to 40MB.
                #  - Audio will be transcoded to MP3 using V2 VBR (roughly
                #      192kbps).
                if not re.match(r'^(image|video|audio)/.*',
                                attachment.mimetype, re.I):
                    # Only support images at this time
                    self.logger.warning(
                        'Ignoring unsupported Mastodon attachment {}.'.format(
                            attachment.url(privacy=True)))
                    continue

                self.logger.debug(
                    'Preparing Mastodon attachment {}'.format(
                        attachment.url(privacy=True)))

                # Upload our image and get our id associated with it
                postokay, response = self._request(
                    self.mastodon_media,
                    payload=attachment,
                )

                if not postokay:
                    # We can't post our attachment
                    if response and 'authorized scopes' \
                            in response.get('error', ''):
                        self.logger.warning(
                            'Failed to Send Attachment to Mastodon: '
                            'missing scope: write:media')

                    # All other failures should cause us to abort
                    return False

                if not (isinstance(response, dict)
                        and response.get('id')):
                    self.logger.debug(
                        'Could not attach the file to Mastodon: %s (mime=%s)',
                        attachment.name, attachment.mimetype)
                    continue

                # If we get here, our output will look something like this:
                # {
                #  'id': '12345',
                #  'type': 'image',
                #  'url': 'https://.../6dad4663a.jpeg',
                #  'preview_url': 'https://.../adde6dad4663a.jpeg',
                #  'remote_url': None,
                #  'preview_remote_url': None,
                #  'text_url': None,
                #  'meta': {
                #     'original': {
                #       'width': 640,
                #       'height': 640,
                #       'size': '640x640',
                #       'aspect': 1.0
                #      },
                #     'small': {
                #       'width': 400,
                #       'height': 400,
                #       'size': '400x400',
                #       'aspect': 1.0
                #      }
                #  },
                #  'description': None,
                #  'blurhash': 'UmIsdJnT^mX4V@XQofnQ~Ebq%4o3ofnQjZbt'
                # }
                response.update({
                    # Update our response to additionally include the
                    # attachment details
                    'file_name': attachment.name,
                    'file_mime': attachment.mimetype,
                    'file_path': attachment.path,
                })

                # Save our pre-prepared payload for attachment posting
                attachments.append(response)

        payload = {
            'status': '{} {}'.format(' '.join(targets), body)
            if targets else body,
            'sensitive': self.sensitive,
        }

        # Handle Visibility Flag
        if self.visibility != MastodonMessageVisibility.DEFAULT:
            payload['visibility'] = self.visibility

        # Set Spoiler text (if set)
        if self.spoiler:
            payload['spoiler_text'] = self.spoiler

        # Set Idempotency-Key (if set)
        if self.idempotency_key:
            payload['Idempotency-Key'] = self.idempotency_key

        # Set Language
        if self.language:
            payload['language'] = self.language

        payloads = []
        if not attachments:
            payloads.append(payload)

        else:
            # Group our images if batch is set to do so
            batch_size = 1 if not self.batch \
                else self.__toot_non_gif_images_batch

            # Track our batch control in our message generation
            batches = []
            batch = []
            for attachment in attachments:
                batch.append(attachment['id'])
                # Mastodon supports batching images together.  This allows
                # the batching of multiple images together.  Mastodon also
                # makes it clear that you can't batch `gif` files; they need
                # to be separate.  So the below preserves the ordering that
                # a user passed their attachments in.  if 4-non-gif images
                # are passed, they are all part of a single message.
                #
                # however, if they pass in image, gif, image, gif.  The
                # gif's inbetween break apart the batches so this would
                # produce 4 separate toots.
                #
                # If you passed in, image, image, gif, image. <- This would
                # produce 3 images (as the first 2 images could be lumped
                # together as a batch)
                if not re.match(
                        r'^image/(png|jpe?g)', attachment['file_mime'], re.I) \
                        or len(batch) >= batch_size:
                    batches.append(batch)
                    batch = []

            if batch:
                batches.append(batch)

            for no, media_ids in enumerate(batches):
                _payload = deepcopy(payload)
                _payload['media_ids'] = media_ids

                if no or not body:
                    # strip text and replace it with the image representation
                    _payload['status'] = \
                        '{:02d}/{:02d}'.format(no + 1, len(batches))
                    # No longer sensitive information
                    _payload['sensitive'] = False
                    if self.idempotency_key:
                        # Support multiposts while a Idempotency Key has been
                        # defined
                        _payload['Idempotency-Key'] = '{}-part{:02d}'.format(
                            self.idempotency_key, no)
                payloads.append(_payload)

        # Error Tracking
        has_error = False

        for no, payload in enumerate(payloads, start=1):
            postokay, response = self._request(self.mastodon_toot, payload)
            if not postokay:
                # Track our error
                has_error = True

                # We can't post our attachment
                if response and 'authorized scopes' \
                        in response.get('error', ''):
                    self.logger.warning(
                        'Failed to Send Status to Mastodon: '
                        'missing scope: write:statuses')

                continue

            # Example Attachment Output:
            # {
            #    "id":"109315796435904505",
            #    "created_at":"2022-11-09T20:44:39.017Z",
            #    "in_reply_to_id":null,
            #    "in_reply_to_account_id":null,
            #    "sensitive":false,
            #    "spoiler_text":"",
            #    "visibility":"public",
            #    "language":"en",
            #    "uri":"https://host/users/caronc/statuses/109315796435904505",
            #    "url":"https://host/@caronc/109315796435904505",
            #    "replies_count":0,
            #    "reblogs_count":0,
            #    "favourites_count":0,
            #    "edited_at":null,
            #    "favourited":false,
            #    "reblogged":false,
            #    "muted":false,
            #    "bookmarked":false,
            #    "pinned":false,
            #    "content":"<p>test</p>",
            #    "reblog":null,
            #    "application":{
            #       "name":"Apprise Notifications",
            #       "website":"https://github.com/caronc/apprise"
            #    },
            #    "account":{
            #       "id":"109310334138718878",
            #       "username":"caronc",
            #       "acct":"caronc",
            #       "display_name":"Chris",
            #       "locked":false,
            #       "bot":false,
            #       "discoverable":false,
            #       "group":false,
            #       "created_at":"2022-11-08T00:00:00.000Z",
            #       "note":"content",
            #       "url":"https://host/@caronc",
            #       "avatar":"https://host/path/file.png",
            #       "avatar_static":"https://host/path/file.png",
            #       "header":"https://host/headers/original/missing.png",
            #       "header_static":"https://host/path/missing.png",
            #       "followers_count":0,
            #       "following_count":0,
            #       "statuses_count":15,
            #       "last_status_at":"2022-11-09",
            #       "emojis":[
            #
            #       ],
            #       "fields":[
            #
            #       ]
            #    },
            #    "media_attachments":[
            #       {
            #          "id":"109315796405707501",
            #          "type":"image",
            #          "url":"https://host/path/file.jpeg",
            #          "preview_url":"https://host/path/file.jpeg",
            #          "remote_url":null,
            #          "preview_remote_url":null,
            #          "text_url":null,
            #          "meta":{
            #             "original":{
            #                "width":640,
            #                "height":640,
            #                "size":"640x640",
            #                "aspect":1.0
            #             },
            #             "small":{
            #                "width":400,
            #                "height":400,
            #                "size":"400x400",
            #                "aspect":1.0
            #             }
            #          },
            #          "description":null,
            #          "blurhash":"UmIsdJnT^mX4V@XQofnQ~Ebq%4o3ofnQjZbt"
            #       }
            #    ],
            #    "mentions":[
            #
            #    ],
            #    "tags":[
            #
            #    ],
            #    "emojis":[
            #
            #    ],
            #    "card":null,
            #    "poll":null
            # }

            try:
                url = '{}/web/@{}'.format(
                    self.api_url,
                    response['account']['username'])

            except (KeyError, TypeError):
                url = 'unknown'

            self.logger.debug(
                'Mastodon [%.2d/%.2d] (%d attached) delivered to %s',
                no, len(payloads), len(payload.get('media_ids', [])), url)

            self.logger.info(
                'Sent [%.2d/%.2d] Mastodon notification as public toot.',
                no, len(payloads))

        return not has_error

    def _whoami(self, lazy=True):
        """
        Looks details of current authenticated user

        """

        if lazy and self._whoami_cache is not None:
            # Use cached response
            return self._whoami_cache

        # Send Mastodon Whoami request
        postokay, response = self._request(
            self.mastodon_whoami,
            method='GET',
        )

        if postokay:
            # Sample Response:
            # {
            #   'id': '12345',
            #   'username': 'caronc',
            #   'acct': 'caronc',
            #   'display_name': 'Chris',
            #   'locked': False,
            #   'bot': False,
            #   'discoverable': False,
            #   'group': False,
            #   'created_at': '2022-11-08T00:00:00.000Z',
            #   'note': 'details',
            #   'url': 'https://noc.social/@caronc',
            #   'avatar': 'https://host/path/image.png',
            #   'avatar_static': 'https://host/path/image.png',
            #   'header': 'https://host/path/missing.png',
            #   'header_static': 'https://host/path/missing.png',
            #   'followers_count': 0,
            #   'following_count': 0,
            #   'statuses_count': 2,
            #   'last_status_at': '2022-11-09',
            #   'source': {
            #     'privacy': 'public',
            #     'sensitive': False,
            #     'language': None,
            #     'note': 'details',
            #     'fields': [],
            #     'follow_requests_count': 0
            #   },
            #   'emojis': [],
            #   'fields': []
            # }
            try:
                # Cache our response for future references
                self._whoami_cache = {
                    response['username']: response['id']}

            except (TypeError, KeyError):
                pass

        elif response and 'authorized scopes' in response.get('error', ''):
            self.logger.warning(
                'Failed to lookup Mastodon Auth details; '
                'missing scope: read:accounts')

        return self._whoami_cache if postokay else {}

    def _request(self, path, payload=None, method='POST'):
        """
        Wrapper to Mastodon API requests object
        """

        headers = {
            'User-Agent': self.app_id,
            'Authorization': f'Bearer {self.token}',
        }

        data = None
        files = None

        # Prepare our message
        url = '{}{}'.format(self.api_url, path)

        # Some Debug Logging
        self.logger.debug('Mastodon {} URL: {} (cert_verify={})'.format(
            method, url, self.verify_certificate))

        # Open our attachment path if required:
        if isinstance(payload, AttachBase):
            # prepare payload
            files = {
                'file': (payload.name, open(payload.path, 'rb'),
                         'application/octet-stream')}

            # Provide a description
            data = {
                'description': payload.name,
            }

        else:
            headers['Content-Type'] = 'application/json'
            data = dumps(payload)
            self.logger.debug('Mastodon Payload: %s' % str(payload))

        # Default content response object
        content = {}

        # By default set wait to None
        wait = None

        if self.ratelimit_remaining == 0:
            # Determine how long we should wait for or if we should wait at
            # all. This isn't fool-proof because we can't be sure the client
            # time (calling this script) is completely synced up with the
            # Mastodon server.  One would hope we're on NTP and our clocks are
            # the same allowing this to role smoothly:

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if now < self.ratelimit_reset:
                # We need to throttle for the difference in seconds
                # We add 0.5 seconds to the end just to allow a grace
                # period.
                wait = (self.ratelimit_reset - now).total_seconds() + 0.5

        # Always call throttle before any remote server i/o is made;
        self.throttle(wait=wait)

        # acquire our request mode
        fn = requests.post if method == 'POST' else requests.get

        try:
            r = fn(
                url,
                data=data,
                files=files,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

            if r.status_code not in (
                    requests.codes.ok, requests.codes.created,
                    requests.codes.accepted):

                # We had a problem
                status_str = \
                    NotifyMastodon.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Mastodon {} to {}: '
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
                # Capture rate limiting if possible
                self.ratelimit_remaining = \
                    int(r.headers.get('X-RateLimit-Remaining'))
                self.ratelimit_reset = datetime.fromtimestamp(
                    int(r.headers.get('X-RateLimit-Limit')), timezone.utc
                ).replace(tzinfo=None)

            except (TypeError, ValueError):
                # This is returned if we could not retrieve this information
                # gracefully accept this state and move on
                pass

        except requests.RequestException as e:
            self.logger.warning(
                'Exception received when sending Mastodon {} to {}: '.
                format(method, url))
            self.logger.debug('Socket Exception: %s' % str(e))

            # Mark our failure
            return (False, content)

        except (OSError, IOError) as e:
            self.logger.warning(
                'An I/O error occurred while handling {}.'.format(
                    payload.name if isinstance(payload, AttachBase)
                    else payload))
            self.logger.debug('I/O Exception: %s' % str(e))
            return (False, content)

        finally:
            # Close our file (if it's open) stored in the second element
            # of our files tuple (index 1)
            if files:
                files['file'][1].close()

        return (True, content)

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

        if 'token' in results['qsd'] and len(results['qsd']['token']):
            results['token'] = NotifyMastodon.unquote(results['qsd']['token'])

        elif not results['password'] and results['user']:
            results['token'] = NotifyMastodon.unquote(results['user'])

        # Apply our targets
        results['targets'] = NotifyMastodon.split_path(results['fullpath'])

        # The defined Mastodon visibility
        if 'visibility' in results['qsd'] and \
                len(results['qsd']['visibility']):
            # Simplified version
            results['visibility'] = \
                NotifyMastodon.unquote(results['qsd']['visibility'])

        elif results['schema'].startswith('toot'):
            results['visibility'] = MastodonMessageVisibility.PUBLIC

        # Get Idempotency Key (if specified)
        if 'key' in results['qsd'] and len(results['qsd']['key']):
            results['key'] = \
                NotifyMastodon.unquote(results['qsd']['key'])

        # Get Spoiler Text
        if 'spoiler' in results['qsd'] and len(results['qsd']['spoiler']):
            results['spoiler'] = \
                NotifyMastodon.unquote(results['qsd']['spoiler'])

        # Get Language (if specified)
        if 'language' in results['qsd'] and len(results['qsd']['language']):
            results['language'] = \
                NotifyMastodon.unquote(results['qsd']['language'])

        # Get Sensitive Flag (for Attachments)
        results['sensitive'] = \
            parse_bool(results['qsd'].get(
                'sensitive',
                NotifyMastodon.template_args['sensitive']['default']))

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get(
                'batch', NotifyMastodon.template_args['batch']['default']))

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyMastodon.parse_list(results['qsd']['to'])

        return results
