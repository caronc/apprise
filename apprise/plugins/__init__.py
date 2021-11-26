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

import os
import six
import re
import copy

from os.path import dirname
from os.path import abspath

# Used for testing
from . import NotifyEmail as NotifyEmailBase
from .NotifyXMPP import SliXmppAdapter

# NotifyBase object is passed in as a module not class
from . import NotifyBase

from ..common import NotifyImageSize
from ..common import NOTIFY_IMAGE_SIZES
from ..common import NotifyType
from ..common import NOTIFY_TYPES
from ..utils import parse_list
from ..utils import cwe312_url
from ..utils import GET_SCHEMA_RE
from ..logger import logger
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

    # Tokenizer
    'url_to_dict',

    # slixmpp access points (used for NotifyXMPP Testing)
    'SliXmppAdapter',
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

    for f in os.listdir(path):
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
                    "Notification schema ({}) mismatch detected - {} to {}"
                    .format(schema, SCHEMA_MAP[schema], plugin))
                continue

            # Assign plugin
            SCHEMA_MAP[schema] = plugin

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
            #  - support dictionaries too
            tokens[key]['default'] = tokens[key]['values'][0] \
                if not isinstance(tokens[key]['values'], dict) \
                else next(iter(tokens[key]['values']))

        if 'values' in tokens[key] and isinstance(tokens[key]['values'], dict):
            # Convert values into a list if it was defined as a dictionary
            tokens[key]['values'] = [k for k in tokens[key]['values'].keys()]

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

        if 'alias_of' in template_args[key]:
            # Check if the mapped reference is a list; if it is, then
            # we need to store a different delimiter
            alias_of = template_tokens.get(template_args[key]['alias_of'], {})
            if alias_of.get('type', '').startswith('list') \
                    and 'delim' not in template_args[key]:
                # Set a default delimiter of a comma and/or space if one
                # hasn't already been specified
                template_args[key]['delim'] = (',', ' ')

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


def requirements(plugin):
    """
    Provides a list of packages and its requirement details

    """
    requirements = {
        # Use the description to provide a human interpretable description of
        # what is required to make the plugin work. This is only nessisary
        # if there are package dependencies
        'details': '',

        # Define any required packages needed for the plugin to run.  This is
        # an array of strings that simply look like lines in the
        # `requirements.txt` file...
        #
        # A single string is perfectly acceptable:
        # 'packages_required' = 'cryptography'
        #
        # Multiple entries should look like the following
        # 'packages_required' = [
        #   'cryptography < 3.4`,
        # ]
        #
        'packages_required': [],

        # Recommended packages identify packages that are not required to make
        # your plugin work, but would improve it's use or grant it access to
        # full functionality (that might otherwise be limited).

        # Similar to `packages_required`, you would identify each entry in
        # the array as you would in a `requirements.txt` file.
        #
        #   - Do not re-provide entries already in the `packages_required`
        'packages_recommended': [],
    }

    # Populate our template differently if we don't find anything above
    if not (hasattr(plugin, 'requirements')
            and isinstance(plugin.requirements, dict)):
        # We're done early
        return requirements

    # Get our required packages
    _req_packages = plugin.requirements.get('packages_required')
    if isinstance(_req_packages, six.string_types):
        # Convert to list
        _req_packages = [_req_packages]

    elif not isinstance(_req_packages, (set, list, tuple)):
        # Allow one to set the required packages to None (as an example)
        _req_packages = []

    requirements['packages_required'] = [str(p) for p in _req_packages]

    # Get our recommended packages
    _opt_packages = plugin.requirements.get('packages_recommended')
    if isinstance(_opt_packages, six.string_types):
        # Convert to list
        _opt_packages = [_opt_packages]

    elif not isinstance(_opt_packages, (set, list, tuple)):
        # Allow one to set the recommended packages to None (as an example)
        _opt_packages = []

    requirements['packages_recommended'] = [str(p) for p in _opt_packages]

    # Get our package details
    _req_details = plugin.requirements.get('details')
    if not _req_details:
        if not (_req_packages or _opt_packages):
            _req_details = _('No dependencies.')

        elif _req_packages:
            _req_details = _('Packages are required to function.')

        else:  # opt_packages
            _req_details = \
                _('Packages are recommended to improve functionality.')
    else:
        # Store our details if defined
        requirements['details'] = _req_details

    # Return our compiled package requirements
    return requirements


def url_to_dict(url, secure_logging=True):
    """
    Takes an apprise URL and returns the tokens associated with it
    if they can be acquired based on the plugins available.

    None is returned if the URL could not be parsed, otherwise the
    tokens are returned.

    These tokens can be loaded into apprise through it's add()
    function.
    """

    # swap hash (#) tag values with their html version
    _url = url.replace('/#', '/%23')

    # CWE-312 (Secure Logging) Handling
    loggable_url = url if not secure_logging else cwe312_url(url)

    # Attempt to acquire the schema at the very least to allow our plugins to
    # determine if they can make a better interpretation of a URL geared for
    # them.
    schema = GET_SCHEMA_RE.match(_url)
    if schema is None:
        # Not a valid URL; take an early exit
        logger.error('Unsupported URL: {}'.format(loggable_url))
        return None

    # Ensure our schema is always in lower case
    schema = schema.group('schema').lower()
    if schema not in SCHEMA_MAP:
        # Give the user the benefit of the doubt that the user may be using
        # one of the URLs provided to them by their notification service.
        # Before we fail for good, just scan all the plugins that support the
        # native_url() parse function
        results = \
            next((r['plugin'].parse_native_url(_url)
                  for r in MODULE_MAP.values()
                  if r['plugin'].parse_native_url(_url) is not None),
                 None)

        if not results:
            logger.error('Unparseable URL {}'.format(loggable_url))
            return None

        logger.trace('URL {} unpacked as:{}{}'.format(
            url, os.linesep, os.linesep.join(
                ['{}="{}"'.format(k, v) for k, v in results.items()])))

    else:
        # Parse our url details of the server object as dictionary
        # containing all of the information parsed from our URL
        results = SCHEMA_MAP[schema].parse_url(_url)
        if not results:
            logger.error('Unparseable {} URL {}'.format(
                SCHEMA_MAP[schema].service_name, loggable_url))
            return None

        logger.trace('{} URL {} unpacked as:{}{}'.format(
            SCHEMA_MAP[schema].service_name, url,
            os.linesep, os.linesep.join(
                ['{}="{}"'.format(k, v) for k, v in results.items()])))

    # Return our results
    return results
