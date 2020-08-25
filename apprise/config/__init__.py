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
import six
from os import listdir
from os.path import dirname
from os.path import abspath
from ..logger import logger

# Maintains a mapping of all of the configuration services
SCHEMA_MAP = {}

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
        try:
            schemas = set([]) if not callable(fn) else fn(plugin)

        except TypeError:
            # Python v2.x support where functions associated with classes
            # were considered bound to them and could not be called prior
            # to the classes initialization.  This code can be dropped
            # once Python v2.x support is dropped. The below code introduces
            # replication as it already exists and is tested in
            # URLBase.schemas()
            schemas = set([])
            for key in ('protocol', 'secure_protocol'):
                schema = getattr(plugin, key, None)
                if isinstance(schema, six.string_types):
                    schemas.add(schema)

                elif isinstance(schema, (set, list, tuple)):
                    # Support iterables list types
                    for s in schema:
                        if isinstance(s, six.string_types):
                            schemas.add(s)

        # map our schema to our plugin
        for schema in schemas:
            if schema in SCHEMA_MAP:
                logger.error(
                    "Config schema ({}) mismatch detected - {} to {}"
                    .format(schema, SCHEMA_MAP[schema], plugin))
                continue

            # Assign plugin
            SCHEMA_MAP[schema] = plugin

    return SCHEMA_MAP


# Dynamically build our schema base
__load_matrix()
