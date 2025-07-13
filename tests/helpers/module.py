# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

from importlib import import_module, reload
from itertools import chain
import re
import sys

from apprise import (
    AttachmentManager,
    ConfigurationManager,
    NotificationManager,
)

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()

# Grant access to our Attachment Manager Singleton
A_MGR = AttachmentManager()

# Grant access to our Configuration Manager Singleton
C_MGR = ConfigurationManager()

# For filtering our result when scanning a module
# Identify any items below we should match on that we can freely
# directly copy around between our modules.  This should only
# catch class/function/variables we want to allow explicity
# copy/paste access with
module_filter_re = re.compile(
    r"^(?P<name>(Notify|Config|Attach)[A-Za-z0-9]+)$"
)


def reload_plugin(name):
    """Reload built-in plugin module, e.g. `NotifyGnome`.

    Reloading plugin modules is needed when testing module-level code of
    notification plugins.

    See also
    https://stackoverflow.com/questions/31363311.
    """

    A_MGR.unload_modules()

    reload(sys.modules["apprise.apprise_attachment"])
    reload(sys.modules["apprise.attachment.base"])
    new_apprise_attachment_mod = import_module("apprise.apprise_attachment")
    new_apprise_attach_base_mod = import_module("apprise.attachment.base")
    reload(sys.modules["apprise.manager_attachment"])

    module_pyname = f"{N_MGR.module_name_prefix}.{name}"
    if module_pyname in sys.modules:
        reload(sys.modules[module_pyname])
    new_notify_mod = import_module(module_pyname)

    A_MGR.unload_modules()

    reload(sys.modules["apprise.apprise_config"])
    reload(sys.modules["apprise.config.base"])
    new_apprise_configuration_mod = import_module("apprise.apprise_config")
    new_apprise_config_base_mod = import_module("apprise.config.base")
    reload(sys.modules["apprise.manager_config"])

    C_MGR.unload_modules()

    module_pyname = f"{N_MGR.module_name_prefix}.{name}"
    if module_pyname in sys.modules:
        reload(sys.modules[module_pyname])
    new_notify_mod = import_module(module_pyname)

    # Detect our class object
    class_matches = {}
    for class_name in [
        obj for obj in dir(new_notify_mod) if module_filter_re.match(obj)
    ]:

        # Store our entry
        class_matches[class_name] = getattr(new_notify_mod, class_name)

    # the user running the tests did not correctly use reload_plugin() or
    # they did, but libraries around them have shifted.  We need to error out
    # so the test can be fixed
    if not class_matches:
        raise AttributeError(f"Module {name} has no URLBase defined in it!")

    reload(sys.modules["apprise.manager_plugins"])
    reload(sys.modules["apprise.apprise"])
    reload(sys.modules["apprise.utils"])
    reload(sys.modules["apprise.locale"])
    reload(sys.modules["apprise"])

    # Acquire all of the test files we have
    tests = [k for k in sys.modules if re.match(r"^test_.+$", k)]

    # Iterate over all of our test modules
    for module_name in tests:
        # Filter the test files by only those using the class_name we found
        # within our module
        possible_matches = [
            m
            for m in dir(sys.modules[module_name])
            if re.match(
                "^(?P<name>{})$".format("|".join(class_matches.keys())), m
            )
        ]
        if not possible_matches:
            continue

        # if we get here, we have test_ files that utilize the Class we just
        # reloaded

        # Fix reference to new plugin class in given module.
        # Needed for updating the module-level import reference like
        # `from apprise.plugins.NotifyABCDE import NotifyABCDE`.
        #
        # We reload NotifyABCDE and place it back in its spot
        test_mod = import_module(module_name)
        for class_name, class_plugin in class_matches.items():
            if hasattr(test_mod, class_name):
                setattr(test_mod, class_name, class_plugin)

    #
    # Detect our Apprise Modules (include helpers)
    #
    apprise_modules = sorted(
        [k for k in sys.modules if re.match(r"^(apprise|helpers)(\.|.+)$", k)],
        reverse=True,
    )

    #
    # This section below reloads our attachment classes
    #

    for entry in A_MGR:
        reload(sys.modules[entry["path"]])
        for module_pyname in chain(apprise_modules, tests):
            detect = re.compile(
                r"^(?P<name>(AppriseAttachment|AttachBase|"
                + entry["path"].split(".")[-1]
                + r"))$"
            )

            possible_matches = [
                m for m in dir(sys.modules[module_pyname]) if detect.match(m)
            ]
            if not possible_matches:
                continue

            apprise_mod = import_module(module_pyname)
            # Fix reference to new plugin class in given module.
            # Needed for updating the module-level import reference
            # like `from apprise.<etc> import AttachABCDE`.
            #
            # We reload NotifyABCDE and place it back in its spot
            # new_attach = import_module(entry['path'])
            for name in possible_matches:
                if name == "AppriseAttachment":
                    setattr(
                        apprise_mod,
                        name,
                        getattr(new_apprise_attachment_mod, name),
                    )

                elif name == "AttachBase":
                    setattr(
                        apprise_mod,
                        name,
                        getattr(new_apprise_attach_base_mod, name),
                    )

                else:
                    module_pyname = f"{A_MGR.module_name_prefix}.{name}"
                    new_attach_mod = import_module(module_pyname)

                    # Detect our class object
                    class_matches = {}
                    for class_name in [
                        obj
                        for obj in dir(new_attach_mod)
                        if module_filter_re.match(obj)
                    ]:

                        # Store our entry
                        class_matches[class_name] = getattr(
                            new_attach_mod, class_name
                        )

                    for class_name, class_plugin in class_matches.items():
                        if hasattr(apprise_mod, class_name):
                            setattr(apprise_mod, class_name, class_plugin)

    #
    # This section below reloads our configuration classes
    #

    for entry in C_MGR:
        reload(sys.modules[entry["path"]])
        for module_pyname in chain(apprise_modules, tests):
            detect = re.compile(
                r"^(?P<name>(AppriseConfig|ConfigBase|"
                + entry["path"].split(".")[-1]
                + r"))$"
            )

            possible_matches = [
                m for m in dir(sys.modules[module_pyname]) if detect.match(m)
            ]
            if not possible_matches:
                continue

            apprise_mod = import_module(module_pyname)
            # Fix reference to new plugin class in given module.
            # Needed for updating the module-level import reference
            # like `from apprise.<etc> import ConfigABCDE`.
            #
            # We reload NotifyABCDE and place it back in its spot
            # new_attach = import_module(entry['path'])
            for name in possible_matches:
                if name == "AppriseConfig":
                    setattr(
                        apprise_mod,
                        name,
                        getattr(new_apprise_configuration_mod, name),
                    )

                elif name == "ConfigBase":
                    setattr(
                        apprise_mod,
                        name,
                        getattr(new_apprise_config_base_mod, name),
                    )

                else:
                    module_pyname = f"{A_MGR.module_name_prefix}.{name}"
                    new_config_mod = import_module(module_pyname)

                    # Detect our class object
                    class_matches = {}
                    for class_name in [
                        obj
                        for obj in dir(new_config_mod)
                        if module_filter_re.match(obj)
                    ]:

                        # Store our entry
                        class_matches[class_name] = getattr(
                            new_config_mod, class_name
                        )

                    for class_name, class_plugin in class_matches.items():
                        if hasattr(apprise_mod, class_name):
                            setattr(apprise_mod, class_name, class_plugin)
