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

import requests
from json import dumps
from json import loads

from .base import NotifyBase
from ..utils import is_email
from ..common import NotifyType
from ..utils import parse_list
from ..utils import validate_regex
from ..locale import gettext_lazy as _
from ..attachment.base import AttachBase

# Flag used as a placeholder to sending to all devices
PUSHBULLET_SEND_TO_ALL = 'ALL_DEVICES'

# Provide some known codes Pushbullet uses and what they translate to:
PUSHBULLET_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
}


class NotifyPushBullet(NotifyBase):
    """
    A wrapper for PushBullet Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Pushbullet'

    # The services URL
    service_url = 'https://www.pushbullet.com/'

    # The default secure protocol
    secure_protocol = 'pbul'

    # Allow 50 requests per minute (Tier 2).
    # 60/50 = 0.2
    request_rate_per_sec = 1.2

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pushbullet'

    # PushBullet uses the http protocol with JSON requests
    notify_url = 'https://api.pushbullet.com/v2/{}'

    # Support attachments
    attachment_support = True

    # Define object templates
    templates = (
        '{schema}://{accesstoken}',
        '{schema}://{accesstoken}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'accesstoken': {
            'name': _('Access Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_device': {
            'name': _('Target Device'),
            'type': 'string',
            'map_to': 'targets',
        },
        'target_channel': {
            'name': _('Target Channel'),
            'type': 'string',
            'prefix': '#',
            'map_to': 'targets',
        },
        'target_email': {
            'name': _('Target Email'),
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

    def __init__(self, accesstoken, targets=None, **kwargs):
        """
        Initialize PushBullet Object
        """
        super().__init__(**kwargs)

        # Access Token (associated with project)
        self.accesstoken = validate_regex(accesstoken)
        if not self.accesstoken:
            msg = 'An invalid PushBullet Access Token ' \
                  '({}) was specified.'.format(accesstoken)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.targets = parse_list(targets)
        if len(self.targets) == 0:
            self.targets = (PUSHBULLET_SEND_TO_ALL, )

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform PushBullet Notification
        """

        # error tracking (used for function return)
        has_error = False

        # Build a list of our attachments
        attachments = []

        if attach and self.attachment_support:
            # We need to upload our payload first so that we can source it
            # in remaining messages
            for no, attachment in enumerate(attach, start=1):

                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                self.logger.debug(
                    'Preparing PushBullet attachment {}'.format(
                        attachment.url(privacy=True)))

                # prepare payload
                payload = {
                    'file_name': attachment.name
                    if attachment.name else f'file{no:03}.dat',
                    'file_type': attachment.mimetype,
                }
                # First thing we need to do is make a request so that we can
                # get a URL to post our request to.
                # see: https://docs.pushbullet.com/#upload-request
                okay, response = self._send(
                    self.notify_url.format('upload-request'), payload)
                if not okay:
                    # We can't post our attachment
                    return False

                # If we get here, our output will look something like this:
                # {
                #   "file_name": "cat.jpg",
                #   "file_type": "image/jpeg",
                #   "file_url": "https://dl.pushb.com/abc/cat.jpg",
                #   "upload_url": "https://upload.pushbullet.com/abcd123"
                # }

                # - The file_url is where the file will be available after it
                #    is uploaded.
                # - The upload_url is where to POST the file to. The file must
                #    be posted using multipart/form-data encoding.

                # Prepare our attachment payload; we'll use this if we
                # successfully upload the content below for later on.
                try:
                    # By placing this in a try/except block we can validate
                    # our response at the same time as preparing our payload
                    payload = {
                        # PushBullet v2/pushes file type:
                        'type': 'file',
                        'file_name': response['file_name'],
                        'file_type': response['file_type'],
                        'file_url': response['file_url'],
                    }

                    if response['file_type'].startswith('image/'):
                        # Allow image to be displayed inline (if image type)
                        payload['image_url'] = response['file_url']

                    upload_url = response['upload_url']

                except (KeyError, TypeError):
                    # A method of verifying our content exists
                    return False

                okay, response = self._send(upload_url, attachment)
                if not okay:
                    # We can't post our attachment
                    return False

                # Save our pre-prepared payload for attachment posting
                attachments.append(payload)

        # Create a copy of the targets list
        targets = list(self.targets)
        while len(targets):
            recipient = targets.pop(0)

            # prepare payload
            payload = {
                'type': 'note',
                'title': title,
                'body': body,
            }

            # Check if an email was defined
            match = is_email(recipient)
            if match:
                payload['email'] = match['full_email']
                self.logger.debug(
                    "PushBullet recipient {} parsed as an email address"
                    .format(recipient))

            elif recipient is PUSHBULLET_SEND_TO_ALL:
                # Send to all
                pass

            elif recipient[0] == '#':
                payload['channel_tag'] = recipient[1:]
                self.logger.debug(
                    "PushBullet recipient {} parsed as a channel"
                    .format(recipient))

            else:
                payload['device_iden'] = recipient
                self.logger.debug(
                    "PushBullet recipient {} parsed as a device"
                    .format(recipient))

            if body:
                okay, response = self._send(
                    self.notify_url.format('pushes'), payload)
                if not okay:
                    has_error = True
                    continue

                self.logger.info(
                    'Sent PushBullet notification to "%s".' % (recipient))

            for attach_payload in attachments:
                # Send our attachments to our same user (already prepared as
                # our payload object)
                okay, response = self._send(
                    self.notify_url.format('pushes'), attach_payload)
                if not okay:
                    has_error = True
                    continue

                self.logger.info(
                    'Sent PushBullet attachment ({}) to "{}".'.format(
                        attach_payload['file_name'], recipient))

        return not has_error

    def _send(self, url, payload, **kwargs):
        """
        Wrapper to the requests (post) object
        """

        headers = {
            'User-Agent': self.app_id,
        }

        # Some default values for our request object to which we'll update
        # depending on what our payload is
        files = None
        data = None

        if not isinstance(payload, AttachBase):
            # Send our payload as a JSON object
            headers['Content-Type'] = 'application/json'
            data = dumps(payload) if payload else None

        auth = (self.accesstoken, '')

        self.logger.debug('PushBullet POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('PushBullet Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # Default response type
        response = None

        try:
            # Open our attachment path if required:
            if isinstance(payload, AttachBase):
                files = {'file': (payload.name, open(payload.path, 'rb'))}

            r = requests.post(
                url,
                data=data,
                headers=headers,
                files=files,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            try:
                response = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None

                # Fall back to the existing unparsed value
                response = r.content

            if r.status_code not in (
                    requests.codes.ok, requests.codes.no_content):
                # We had a problem
                status_str = \
                    NotifyPushBullet.http_response_code_lookup(
                        r.status_code, PUSHBULLET_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to deliver payload to PushBullet:'
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                return False, response

            # otherwise we were successful
            return True, response

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred communicating with PushBullet.')
            self.logger.debug('Socket Exception: %s' % str(e))

            return False, response

        except (OSError, IOError) as e:
            self.logger.warning(
                'An I/O error occurred while handling {}.'.format(
                    payload.name if isinstance(payload, AttachBase)
                    else payload))
            self.logger.debug('I/O Exception: %s' % str(e))
            return False, response

        finally:
            # Close our file (if it's open) stored in the second element
            # of our files tuple (index 1)
            if files:
                files['file'][1].close()

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.accesstoken)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        targets = '/'.join([NotifyPushBullet.quote(x) for x in self.targets])
        if targets == PUSHBULLET_SEND_TO_ALL:
            # keyword is reserved for internal usage only; it's safe to remove
            # it from the recipients list
            targets = ''

        return '{schema}://{accesstoken}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            accesstoken=self.pprint(self.accesstoken, privacy, safe=''),
            targets=targets,
            params=NotifyPushBullet.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        return len(self.targets)

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

        # Fetch our targets
        results['targets'] = \
            NotifyPushBullet.split_path(results['fullpath'])

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyPushBullet.parse_list(results['qsd']['to'])

        # Setup the token; we store it in Access Token for global
        # plugin consistency with naming conventions
        results['accesstoken'] = NotifyPushBullet.unquote(results['host'])

        return results
