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

import six
import re
import copy

from os import listdir
from os.path import dirname
from os.path import abspath

# Used for testing
from . import NotifyEmail as NotifyEmailBase

# Required until re-factored into base code
from .NotifyPushjet import pushjet
from .NotifyGrowl import gntp

# NotifyBase object is passed in as a module not class
from . import NotifyBase

from ..common import NotifyImageSize
from ..common import NOTIFY_IMAGE_SIZES
from ..common import NotifyType
from ..common import NOTIFY_TYPES
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _
from ..AppriseLocale import LazyTranslation

# Maintains a mapping of all of the Notification services
SCHEMA_MAP = {}

__all__ = [
    # Reference
    'NotifyImageSize', 'NOTIFY_IMAGE_SIZES', 'NotifyType', 'NOTIFY_TYPES',
    'NotifyBase',

    # NotifyEmail Base Module (used for NotifyEmail testing)
    'NotifyEmailBase',

    # gntp (used for NotifyGrowl Testing)
    'gntp',

    # pushjet (used for NotifyPushjet Testing)
    'pushjet',
]

# we mirror our base purely for the ability to reset everything; this
# is generally only used in testing and should not be used by developers
MODULE_MAP = {}


# Load our Lookup Matrix
def __load_matrix(path=abspath(dirname(__file__)), name='apprise.plugins'):
    """
    Dynamically load our schema map; this allows us to gracefully
    skip over modules we simply don't have the dependencies for.

    """
    # Used for the detection of additional Notify Services objects
    # The .py extension is optional as we support loading directories too
    module_re = re.compile(r'^(?P<name>Notify[a-z0-9]+)(\.py)?$', re.I)

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

        elif plugin_name in MODULE_MAP:
            # we're already handling this object
            continue

        # Add our plugin name to our module map
        MODULE_MAP[plugin_name] = {
            'plugin': plugin,
            'module': module,
        }

        # Add our module name to our __all__
        __all__.append(plugin_name)

        # Load our module into memory so it's accessible to all
        globals()[plugin_name] = plugin

        # Load protocol(s) if defined
        proto = getattr(plugin, 'protocol', None)
        if isinstance(proto, six.string_types):
            if proto not in SCHEMA_MAP:
                SCHEMA_MAP[proto] = plugin

        elif isinstance(proto, (set, list, tuple)):
            # Support iterables list types
            for p in proto:
                if p not in SCHEMA_MAP:
                    SCHEMA_MAP[p] = plugin

        # Load secure protocol(s) if defined
        protos = getattr(plugin, 'secure_protocol', None)
        if isinstance(protos, six.string_types):
            if protos not in SCHEMA_MAP:
                SCHEMA_MAP[protos] = plugin

        if isinstance(protos, (set, list, tuple)):
            # Support iterables list types
            for p in protos:
                if p not in SCHEMA_MAP:
                    SCHEMA_MAP[p] = plugin

    return SCHEMA_MAP


# Reset our Lookup Matrix
def __reset_matrix():
    """
    Restores the Lookup matrix to it's base setting. This is only used through
    testing and should not be directly called.
    """

    # Reset our schema map
    SCHEMA_MAP.clear()

    # Iterate over our module map so we can clear out our __all__ and globals
    for plugin_name in MODULE_MAP.keys():
        # Clear out globals
        del globals()[plugin_name]

        # Remove element from plugins
        __all__.remove(plugin_name)

    # Clear out our module map
    MODULE_MAP.clear()


# Dynamically build our schema base
__load_matrix()


def _sanitize_token(tokens, default_delimiter):
    """
    This is called by the details() function and santizes the output by
    populating expected and consistent arguments if they weren't otherwise
    specified.

    """

    # Iterate over our tokens
    for key in tokens.keys():

        for element in tokens[key].keys():
            # Perform translations (if detected to do so)
            if isinstance(tokens[key][element], LazyTranslation):
                tokens[key][element] = str(tokens[key][element])

        if 'alias_of' in tokens[key]:
            # Do not touch this field
            continue

        if 'map_to' not in tokens[key]:
            # Default type to key
            tokens[key]['map_to'] = key

        if 'type' not in tokens[key]:
            # Default type to string
            tokens[key]['type'] = 'string'

        elif tokens[key]['type'].startswith('list') \
                and 'delim' not in tokens[key]:
            # Default list delimiter (if not otherwise specified)
            tokens[key]['delim'] = default_delimiter

        elif tokens[key]['type'].startswith('choice') \
                and 'default' not in tokens[key] \
                and 'values' in tokens[key] \
                and len(tokens[key]['values']) == 1:
            # If there is only one choice; then make it the default
            tokens[key]['default'] = \
                tokens[key]['values'][0]

        if 'regex' in tokens[key]:
            # Verify that we are a tuple; convert strings to tuples
            if isinstance(tokens[key]['regex'], six.string_types):
                # Default tuple setup
                tokens[key]['regex'] = \
                    (tokens[key]['regex'], None)

            elif not isinstance(tokens[key]['regex'], (list, tuple)):
                # Invalid regex
                del tokens[key]['regex']

        if 'required' not in tokens[key]:
            # Default required is False
            tokens[key]['required'] = False

        if 'private' not in tokens[key]:
            # Private flag defaults to False if not set
            tokens[key]['private'] = False
    return


def details(plugin):
    """
    Provides templates that can be used by developers to build URLs
    dynamically.

    If a list of templates is provided, then they will be used over
    the default value.

    If a list of tokens are provided, then they will over-ride any
    additional settings built from this script and/or will be appended
    to them afterwards.
    """

    # Our unique list of parsing will be based on the provided templates
    # if none are provided we will use our own
    templates = tuple(plugin.templates)

    # The syntax is simple
    #   {
    #       # The token_name must tie back to an entry found in the
    #       # templates list.
    #       'token_name': {
    #
    #            # types can be 'string', 'int', 'choice', 'list, 'float'
    #            # both choice and list may additionally have a : identify
    #            # what the list/choice type is comprised of; the default
    #            # is string.
    #            'type': 'choice:string',
    #
    #            # values will only exist the type must be a fixed
    #            # list of inputs (generated from type choice for example)
    #
    #            # If this is a choice:bool then you should ALWAYS define
    #            # this list as a (True, False) such as ('Yes, 'No') or
    #            # ('Enabled', 'Disabled'), etc
    #            'values': [ 'http', 'https' ],
    #
    #            # Identifies if the entry specified is required or not
    #            'required': True,
    #
    #            # Identify a default value
    #            'default': 'http',
    #
    #            # Optional Verification Entries min and max are for floats
    #            # and/or integers
    #            'min': 4,
    #            'max': 5,
    #
    #            # A list will always identify a delimiter.  If this is
    #            # part of a path, this may be a '/', or it could be a
    #            # comma and/or space. delimiters are always in a list
    #            #  eg (if space and/or comma is a delimiter the entry
    #            #      would look like: 'delim': [',' , ' ' ]
    #            'delim': None,
    #
    #            # Use regex if you want to share the regular expression
    #            # required to validate the field. The regex will never
    #            # accomodate the prefix (if one is specified).  That is
    #            # up to the user building the URLs to include the prefix
    #            # on the URL when constructing it.
    #            # The format is ('regex', 'reg options')
    #            'regex': (r'[A-Z0-9]+', 'i'),
    #
    #            # A Prefix is always a string, to differentiate between
    #            # multiple arguments, sometimes content is prefixed.
    #            'prefix': '@',
    #
    #            # By default the key of this object is to be interpreted
    #            # as the argument to the notification in question. However
    #            # To accomodate cases where there are multiple types that
    #            # all map to the same entry, one can find a map_to value.
    #            'map_to': 'function_arg',
    #
    #            # Some arguments act as an alias_of an already defined object
    #            # This plays a role more with configuration file generation
    #            # since yaml files allow you to define different argumuments
    #            # in line to simplify things.  If this directive is set, then
    #            # it should be treated exactly the same as the object it is
    #            # an alias of
    #            'alias_of': 'function_arg',
    #
    #            # Advise developers to consider the potential sensitivity
    #            # of this field owned by the user. This is for passwords,
    #            # and api keys, etc...
    #            'private': False,
    #       },
    #   }

    # Template tokens identify the arguments required to initialize the
    # plugin itself.  It identifies all of the tokens and provides some
    # details on their use.  Each token defined should in some way map
    # back to at least one URL {token} defined in the templates

    # Since we nest a dictionary within a dictionary, a simple copy isn't
    # enough. a deepcopy allows us to manipulate this object in this
    # funtion without obstructing the original.
    template_tokens = copy.deepcopy(plugin.template_tokens)

    # Arguments and/or Options either have a default value and/or are
    # optional to be set.
    #
    # Since we nest a dictionary within a dictionary, a simple copy isn't
    # enough. a deepcopy allows us to manipulate this object in this
    # funtion without obstructing the original.
    template_args = copy.deepcopy(plugin.template_args)

    # Our template keyword arguments ?+key=value&-key=value
    # Basically the user provides both the key and the value. this is only
    # possibly by identifying the key prefix required for them to be
    # interpreted hence the +/- keys are built into apprise by default for easy
    # reference. In these cases, entry might look like '+' being the prefix:
    #   {
    #      'arg_name': {
    #          'name': 'label',
    #          'prefix': '+',
    #       }
    #   }
    #
    # Since we nest a dictionary within a dictionary, a simple copy isn't
    # enough. a deepcopy allows us to manipulate this object in this
    # funtion without obstructing the original.
    template_kwargs = copy.deepcopy(plugin.template_kwargs)

    # We automatically create a schema entry
    template_tokens['schema'] = {
        'name': _('Schema'),
        'type': 'choice:string',
        'required': True,
        'values': parse_list(plugin.secure_protocol, plugin.protocol)
    }

    # Sanitize our tokens
    _sanitize_token(template_tokens, default_delimiter=('/', ))
    # Delimiter(s) are space and/or comma
    _sanitize_token(template_args, default_delimiter=(',', ' '))
    _sanitize_token(template_kwargs, default_delimiter=(',', ' '))

    # Argument/Option Handling
    for key in list(template_args.keys()):

        # _lookup_default looks up what the default value
        if '_lookup_default' in template_args[key]:
            template_args[key]['default'] = getattr(
                plugin, template_args[key]['_lookup_default'])

            # Tidy as we don't want to pass this along in response
            del template_args[key]['_lookup_default']

        # _exists_if causes the argument to only exist IF after checking
        # the return of an internal variable requiring a check
        if '_exists_if' in template_args[key]:
            if not getattr(plugin,
                           template_args[key]['_exists_if']):
                # Remove entire object
                del template_args[key]

            else:
                # We only nee to remove this key
                del template_args[key]['_exists_if']

    return {
        'templates': templates,
        'tokens': template_tokens,
        'args': template_args,
        'kwargs': template_kwargs,
    }
