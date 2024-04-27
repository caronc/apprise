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
# Import namespace so the class won't conflict with the actual Notify object
from . import discord


class NotifyGuilded(discord.NotifyDiscord):
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
