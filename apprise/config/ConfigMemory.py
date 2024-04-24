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

from .base import ConfigBase
from ..locale import gettext_lazy as _


class ConfigMemory(ConfigBase):
    """
    For information that was loaded from memory and does not
    persist anywhere.
    """

    # The default descriptive name associated with the service
    service_name = _('Memory')

    # The default protocol
    protocol = 'memory'

    def __init__(self, content, **kwargs):
        """
        Initialize Memory Object

        Memory objects just store the raw configuration in memory.  There is
        no external reference point. It's always considered cached.
        """
        super().__init__(**kwargs)

        # Store our raw config into memory
        self.content = content

        if self.config_format is None:
            # Detect our format if possible
            self.config_format = \
                ConfigMemory.detect_config_format(self.content)

        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        return 'memory://'

    def read(self, **kwargs):
        """
        Simply return content stored into memory
        """

        return self.content

    @staticmethod
    def parse_url(url):
        """
        Memory objects have no parseable URL

        """
        # These URLs can not be parsed
        return None
