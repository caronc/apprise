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

import re
import requests
from json import dumps, loads
from itertools import chain
from datetime import datetime

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyImageSize
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _
from ..attachment.AttachBase import AttachBase


class NotifyMastodon(NotifyBase):
    """
    A wrapper for Notify Mastodon Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Mastodon'

    # The services URL
    service_url = 'https://joinmastodon.org'

    # The default protocol
    protocol = 'mastodon'

    # The default secure protocol
    secure_protocol = 'mastodons'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_mastodon'

    # Allows the user to specify the NotifyImageSize object; this is supported
    # through the webhook
    image_size = NotifyImageSize.XY_128

    # URL for posting media files
    mastodon_media = '/api/v1/media'

    # URL for posting status messages
    mastodon_toot = '/api/v1/statuses'

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
    ratelimit_reset = datetime.utcnow()

    # Default to 1000; users can send up to 1000 DM's and 2400 tweets a day
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
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
        },
        'token': {
            'name': _('Access Token'),
            'type': 'string',
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
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, token=None, targets=None, **kwargs):
        """
        Initialize Notify Mastodon Object
        """
        super().__init__(**kwargs)

        # Set our schema
        self.schema = 'https' if self.secure else 'http'

        # Prepare our URL
        self.api_url = '%s://%s' % (self.schema, self.host)

        if isinstance(self.port, int):
            self.api_url += ':%d' % self.port

        # Initialize channels list
        self.channels = list()

        # Initialize room list
        self.rooms = list()

        # Assign our access token
        self.token = token

        # Our target users
        self.targets = parse_list(targets)
        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {}

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        default_port = 443 if self.secure else 80

        return '{schema}://{token}@{host}{port}/{targets}/?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            token=self.pprint(
                self.token, privacy, mode=PrivacyMode.Secret, safe=''),
            # never encode hostname since we're expecting it to be a valid one
            host=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            targets='/'.join(
                [NotifyMastodon.quote(x, safe='') for x in chain(
                    # Users
                    ['@{}'.format(x) for x in self.targets],
                )]),
            params=NotifyMastodon.urlencode(params),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        wrapper to _send since we can alert more then one channel
        """

        # Build a list of our attachments
        attachments = []

        if attach:
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

                if not re.match(r'^image/.*', attachment.mimetype, re.I):
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
                    return False

                if not (isinstance(response, dict)
                        and response.get('id')):
                    self.logger.debug(
                        'Could not attach the file to Mastodon: %s (mime=%s)',
                        attachment.name, attachment.mimetype)
                    continue

                # If we get here, our output will look something like this:
                # {
                #  'id': '109315674515729186',
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
            'status': body,
        }

        if attachments:
            payload['media_ids'] = [x['id'] for x in attachments]

        postokay, response = self._request(self.mastodon_toot, payload)
        return postokay

    def _request(self, path, payload=None):
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
        self.logger.debug('Mastodon POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate))

        # Open our attachment path if required:
        if isinstance(payload, AttachBase):
            # prepare payload
            files = {
                'file': (payload.name, open(payload.path, 'rb'),
                         'application/octet-stream')}

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
            # Twitter server.  One would hope we're on NTP and our clocks are
            # the same allowing this to role smoothly:

            now = datetime.utcnow()
            if now < self.ratelimit_reset:
                # We need to throttle for the difference in seconds
                # We add 0.5 seconds to the end just to allow a grace
                # period.
                wait = (self.ratelimit_reset - now).total_seconds() + 0.5

        # Always call throttle before any remote server i/o is made;
        self.throttle(wait=wait)

        # acquire our request mode
        try:
            r = requests.post(
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

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyMastodon.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Mastodon POST to {}: '
                    '{}error={}.'.format(
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
                self.ratelimit_reset = datetime.utcfromtimestamp(
                    int(r.headers.get('X-RateLimit-Limit')))

            except (TypeError, ValueError):
                # This is returned if we could not retrieve this information
                # gracefully accept this state and move on
                pass

        except requests.RequestException as e:
            self.logger.warning(
                'Exception received when sending Mastodon POST to {}: '.
                format(url))
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

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyMastodon.parse_list(results['qsd']['to'])

        return results
