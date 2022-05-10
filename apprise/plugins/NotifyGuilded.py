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

# For this to work correctly you need to create a webhook. To do this just
# click on the little gear icon next to the channel you're part of. From
# here you'll be able to access the Webhooks menu and create a new one.
#
#  When you've completed, you'll get a URL that looks a little like this:
#  https://media.guilded.gg/webhooks/417429632418316298/\
#         JHZ7lQml277CDHmQKMHI8qBe7bk2ZwO5UKjCiOAF7711o33MyqU344Qpgv7YTpadV_js
#
#  Simplified, it looks like this:
#     https://media.guilded.gg/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
#
#  This plugin will simply work using the url of:
#     guilded://WEBHOOK_ID/WEBHOOK_TOKEN
#
# API Documentation on Webhooks:
#    - https://discord.com/developers/docs/resources/webhook
#

import re
from .NotifyDiscord import NotifyDiscord


class NotifyGuilded(NotifyDiscord):
    """
    A wrapper to Guilded Notifications

    """

    # The default descriptive name associated with the Notification
    service_name = 'Guilded'

    # The services URL
    service_url = 'https://guilded.gg/'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_guilded'

    # The default secure protocol
    secure_protocol = 'guilded'

    # Guilded Webhook
    notify_url = 'https://media.guilded.gg/webhooks'

    @staticmethod
    def parse_native_url(url):
        """
        Support https://media.guilded.gg/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
        """

        result = re.match(
            r'^https?://(media\.)?guilded\.gg/webhooks/'
            # a UUID, but we do we really need to be _that_ picky?
            r'(?P<webhook_id>[-0-9a-f]+)/'
            r'(?P<webhook_token>[A-Z0-9_-]+)/?'
            r'(?P<params>\?.+)?$', url, re.I)

        if result:
            return NotifyGuilded.parse_url(
                '{schema}://{webhook_id}/{webhook_token}/{params}'.format(
                    schema=NotifyGuilded.secure_protocol,
                    webhook_id=result.group('webhook_id'),
                    webhook_token=result.group('webhook_token'),
                    params='' if not result.group('params')
                    else result.group('params')))

        return None
