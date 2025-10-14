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
from .base import NotifyBase
from ..common import NotifyType
from ..utils import validate_regex
from ..utils import parse_bool
from ..utils import parse_list
from ..utils import parse_url
from ..utils import unquote
from ..utils import quote
from ..utils import is_exclusive_match
from ..logger import logger
from ..locale import gettext_lazy as _


class NotifyGitHubWorkflow(NotifyBase):
    """
    A wrapper for GitHub Actions workflow_call notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'GitHub Workflow'

    # The services URL
    service_url = 'https://github.com/features/actions'

    # The default secure protocol
    secure_protocol = 'github+workflow'

    # The default notify format
    notify_format = 'text'

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 10000

    # Define object templates
    templates = (
        '{schema}://{token}@{repository}/{workflow}',
    )

    # Define our template tokens
    template_tokens = {
        'schema': {
            'name': _('Schema'),
            'type': 'string',
            'required': True,
        },
        'token': {
            'name': _('Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'repository': {
            'name': _('Repository'),
            'type': 'string',
            'required': True,
        },
        'workflow': {
            'name': _('Workflow'),
            'type': 'string',
            'required': True,
        },
    }

    def __init__(self, token, repository, workflow, **kwargs):
        """
        Initialize GitHub Workflow Object
        """
        super().__init__(**kwargs)

        self.token = token
        self.repository = repository
        self.workflow = workflow

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform GitHub Workflow Notification
        """

        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
        }

        payload = {
            'ref': 'main',
            'inputs': {
                'title': title,
                'body': body,
            }
        }

        notify_url = f'https://api.github.com/repos/{self.repository}/actions/workflows/{self.workflow}/dispatches'

        self.logger.debug('GitHub Workflow POST URL: %s' % notify_url)
        self.logger.debug('GitHub Workflow Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                notify_url,
                json=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.no_content:
                # We had a problem
                status_str = \
                    NotifyGitHubWorkflow.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send GitHub Workflow notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # We failed
                return False

            else:
                self.logger.info('Sent GitHub Workflow notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending GitHub Workflow notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # We failed
            return False

        return True

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

        # Token
        results['token'] = unquote(results['user'])

        # Repository
        results['repository'] = unquote(results['host'])

        # Workflow
        results['workflow'] = unquote(results['fullpath'][1:])

        return results
