# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
import pytest
import types

from apprise.NotificationManager import NotificationManager
from apprise.plugins.NotifyBase import NotifyBase

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()


def test_notification_manager():
    """
    N_MGR: Notification Manager General testing

    """
    # Clear our set so we can test init calls
    N_MGR.unload_modules()
    assert isinstance(N_MGR.schemas(), list)
    assert len(N_MGR.schemas()) > 0
    N_MGR.unload_modules(disable_native=True)
    assert isinstance(N_MGR.schemas(), list)
    assert len(N_MGR.schemas()) == 0

    N_MGR.unload_modules()
    assert len(N_MGR) > 0

    N_MGR.unload_modules()
    assert bool(N_MGR) is False
    assert len([x for x in iter(N_MGR)]) > 0
    assert bool(N_MGR) is True

    N_MGR.unload_modules()
    assert isinstance(N_MGR.plugins(), types.GeneratorType)
    assert len([x for x in N_MGR.plugins()]) > 0
    N_MGR.unload_modules(disable_native=True)
    assert isinstance(N_MGR.plugins(), types.GeneratorType)
    assert len([x for x in N_MGR.plugins()]) == 0
    N_MGR.unload_modules()
    assert isinstance(N_MGR['json'](host='localhost'), NotifyBase)
    N_MGR.unload_modules()
    assert 'json' in N_MGR

    # Define our good:// url
    class DisabledNotification(NotifyBase):
        # Always disabled
        enabled = False

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # Support url() function
            return ''

    # Define our good:// url
    class GoodNotification(NotifyBase):

        secure_protocol = ('good', 'goods')

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # Support url() function
            return ''

    N_MGR.unload_modules()
    with pytest.raises(KeyError):
        del N_MGR['good']
    N_MGR['good'] = GoodNotification
    del N_MGR['good']

    N_MGR.unload_modules()
    N_MGR['good'] = GoodNotification
    assert N_MGR['good'].enabled is True
    N_MGR.enable_only('json', 'xml')
    assert N_MGR['good'].enabled is False
    assert N_MGR['json'].enabled is True
    assert N_MGR['jsons'].enabled is True
    assert N_MGR['xml'].enabled is True
    assert N_MGR['xmls'].enabled is True
    N_MGR.enable_only('good')
    assert N_MGR['good'].enabled is True
    assert N_MGR['json'].enabled is False
    assert N_MGR['jsons'].enabled is False
    assert N_MGR['xml'].enabled is False
    assert N_MGR['xmls'].enabled is False

    N_MGR.unload_modules()
    N_MGR['disabled'] = DisabledNotification
    assert N_MGR['disabled'].enabled is False
    N_MGR.enable_only('disabled')
    # Can't enable items that aren't supposed to be:
    assert N_MGR['disabled'].enabled is False

    N_MGR['good'] = GoodNotification
    assert N_MGR['good'].enabled is True

    N_MGR.unload_modules()
    N_MGR.enable_only('form', 'xml')
    for schema in N_MGR.schemas(include_disabled=False):
        assert re.match(r'^(form|xml)s?$', schema, re.IGNORECASE) is not None

    N_MGR.unload_modules()
    assert N_MGR['form'].enabled is True
    assert N_MGR['xml'].enabled is True
    assert N_MGR['json'].enabled is True
    N_MGR.enable_only('form', 'xml')
    assert N_MGR['form'].enabled is True
    assert N_MGR['xml'].enabled is True
    assert N_MGR['json'].enabled is False

    N_MGR.disable('invalid', 'xml')
    assert N_MGR['form'].enabled is True
    assert N_MGR['xml'].enabled is False
    assert N_MGR['json'].enabled is False

    # Detect that our json object is enabled
    with pytest.raises(KeyError):
        # The below can not be indexed
        N_MGR['invalid']

    N_MGR.unload_modules()
    assert N_MGR['json'].enabled is True

    # Work with an empty module tree
    N_MGR.unload_modules(disable_native=True)
    with pytest.raises(KeyError):
        # The below can not be indexed
        N_MGR['good']

    N_MGR.unload_modules()
    N_MGR['good'] = GoodNotification

    N_MGR.unload_modules()
    N_MGR.remove('good', 'invalid')
    assert 'good' not in N_MGR
    assert 'goods' not in N_MGR
