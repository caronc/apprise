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

from itertools import chain
from importlib import import_module, reload
from apprise.NotificationManager import NotificationManager
from apprise.AttachmentManager import AttachmentManager
import sys
import re

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()

# Grant access to our Attachment Manager Singleton
A_MGR = AttachmentManager()


def reload_plugin(name):
    """
    Reload built-in plugin module, e.g. `NotifyGnome`.

    Reloading plugin modules is needed when testing module-level code of
    notification plugins.

    See also https://stackoverflow.com/questions/31363311.
    """

    A_MGR.unload_modules()

    reload(sys.modules['apprise.attachment.AttachBase'])
    reload(sys.modules['apprise.AppriseAttachment'])
    new_apprise_attachment_mod = import_module('apprise.AppriseAttachment')
    reload(sys.modules['apprise.AttachmentManager'])

    module_pyname = '{}.{}'.format(N_MGR.module_name_prefix, name)
    if module_pyname in sys.modules:
        reload(sys.modules[module_pyname])
    new_notify_mod = import_module(module_pyname)

    reload(sys.modules['apprise.NotificationManager'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise.utils'])
    reload(sys.modules['apprise'])

    # Filter our keys
    tests = [k for k in sys.modules.keys() if re.match(r'^test_.+$', k)]
    for module_name in tests:
        possible_matches = \
            [m for m in dir(sys.modules[module_name])
             if re.match(r'^(?P<name>Notify[a-z0-9]+)$', m, re.I)]
        if not possible_matches:
            continue

        # Fix reference to new plugin class in given module.
        # Needed for updating the module-level import reference like
        # `from apprise.plugins.NotifyABCDE import NotifyABCDE`.
        #
        # We reload NotifyABCDE and place it back in its spot
        test_mod = import_module(module_name)
        setattr(test_mod, name, getattr(new_notify_mod, name))

    # Detect our Apprise Modules (include helpers)
    apprise_modules = \
        [k for k in sys.modules.keys()
         if re.match(r'^(apprise|helpers)(\.|.+)$', k)]

    for entry in A_MGR:
        reload(sys.modules[entry['path']])
        for module_pyname in chain(apprise_modules, tests):
            detect = re.compile(
                r'^(?P<name>(AppriseAttachment|AttachBase|' +
                entry['path'].split('.')[-1] + r'))$')

            possible_matches = \
                [m for m in dir(sys.modules[module_pyname]) if detect.match(m)]
            if not possible_matches:
                continue

            apprise_mod = import_module(module_pyname)
            # Fix reference to new plugin class in given module.
            # Needed for updating the module-level import reference
            # like `from apprise.<etc> import NotifyABCDE`.
            #
            # We reload NotifyABCDE and place it back in its spot
            # new_attach = import_module(entry['path'])
            for name in possible_matches:
                if name == 'AppriseAttachment':
                    setattr(
                        apprise_mod, name,
                        getattr(new_apprise_attachment_mod, name))

                else:
                    module_pyname = '{}.{}'.format(
                        A_MGR.module_name_prefix, name)
                    new_attach_mod = import_module(module_pyname)
                    setattr(apprise_mod, name, getattr(new_attach_mod, name))
