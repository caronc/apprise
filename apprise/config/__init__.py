# -*- coding: utf-8 -*-
# BSD 3-Clause License
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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
from os import listdir
from os.path import dirname
from os.path import abspath
from ..logger import logger
from ..common import CONFIG_SCHEMA_MAP

__all__ = []


# Load our Lookup Matrix
def __load_matrix(path=abspath(dirname(__file__)), name='apprise.config'):
    """
    Dynamically load our schema map; this allows us to gracefully
    skip over modules we simply don't have the dependencies for.

    """
    # Used for the detection of additional Configuration Services objects
    # The .py extension is optional as we support loading directories too
    module_re = re.compile(r'^(?P<name>Config[a-z0-9]+)(\.py)?$', re.I)

    for f in listdir(path):
        match = module_re.match(f)
        if not match:
            # keep going
            continue

        # Store our notification/plugin name:
        plugin_name = match.group('name')
        try:
            module = __import__(
                '{}.{}'.format(name, plugin_name),
                globals(), locals(),
                fromlist=[plugin_name])

        except ImportError:
            # No problem, we can't use this object
            continue

        if not hasattr(module, plugin_name):
            # Not a library we can load as it doesn't follow the simple rule
            # that the class must bear the same name as the notification
            # file itself.
            continue

        # Get our plugin
        plugin = getattr(module, plugin_name)
        if not hasattr(plugin, 'app_id'):
            # Filter out non-notification modules
            continue

        elif plugin_name in __all__:
            # we're already handling this object
            continue

        # Add our module name to our __all__
        __all__.append(plugin_name)

        # Ensure we provide the class as the reference to this directory and
        # not the module:
        globals()[plugin_name] = plugin

        fn = getattr(plugin, 'schemas', None)
        schemas = set([]) if not callable(fn) else fn(plugin)

        # map our schema to our plugin
        for schema in schemas:
            if schema in CONFIG_SCHEMA_MAP:
                logger.error(
                    "Config schema ({}) mismatch detected - {} to {}"
                    .format(schema, CONFIG_SCHEMA_MAP[schema], plugin))
                continue

            # Assign plugin
            CONFIG_SCHEMA_MAP[schema] = plugin

    return CONFIG_SCHEMA_MAP


# Dynamically build our schema base
__load_matrix()
