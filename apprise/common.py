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

# we mirror our base purely for the ability to reset everything; this
# is generally only used in testing and should not be used by developers
# It is also used as a means of preventing a module from being reloaded
# in the event it already exists
NOTIFY_MODULE_MAP = {}

# Maintains a mapping of all of the Notification services
NOTIFY_SCHEMA_MAP = {}

# This contains a mapping of all plugins dynamicaly loaded at runtime from
# external modules such as the @notify decorator
#
# The elements here will be additionally added to the NOTIFY_SCHEMA_MAP if
# there is no conflict otherwise.
# The structure looks like the following:
# Module path, e.g. /usr/share/apprise/plugins/my_notify_hook.py
# {
#   'path': path,
#
#   'notify': {
#     'schema': {
#       'name': 'Custom schema name',
#       'fn_name': 'name_of_function_decorator_was_found_on',
#       'url': 'schema://any/additional/info/found/on/url'
#       'plugin': <CustomNotifyWrapperPlugin>
#    },
#     'schema2': {
#       'name': 'Custom schema name',
#       'fn_name': 'name_of_function_decorator_was_found_on',
#       'url': 'schema://any/additional/info/found/on/url'
#       'plugin': <CustomNotifyWrapperPlugin>
#    }
#  }
#
# Note: that the <CustomNotifyWrapperPlugin> inherits from
#       NotifyBase
NOTIFY_CUSTOM_MODULE_MAP = {}

# Maintains a mapping of all configuration schema's supported
CONFIG_SCHEMA_MAP = {}

# Maintains a mapping of all attachment schema's supported
ATTACHMENT_SCHEMA_MAP = {}


class NotifyType:
    """
    A simple mapping of notification types most commonly used with
    all types of logging and notification services.
    """
    INFO = 'info'
    SUCCESS = 'success'
    WARNING = 'warning'
    FAILURE = 'failure'


NOTIFY_TYPES = (
    NotifyType.INFO,
    NotifyType.SUCCESS,
    NotifyType.WARNING,
    NotifyType.FAILURE,
)


class NotifyImageSize:
    """
    A list of pre-defined image sizes to make it easier to work with defined
    plugins.
    """
    XY_32 = '32x32'
    XY_72 = '72x72'
    XY_128 = '128x128'
    XY_256 = '256x256'


NOTIFY_IMAGE_SIZES = (
    NotifyImageSize.XY_32,
    NotifyImageSize.XY_72,
    NotifyImageSize.XY_128,
    NotifyImageSize.XY_256,
)


class NotifyFormat:
    """
    A list of pre-defined text message formats that can be passed via the
    apprise library.
    """
    TEXT = 'text'
    HTML = 'html'
    MARKDOWN = 'markdown'


NOTIFY_FORMATS = (
    NotifyFormat.TEXT,
    NotifyFormat.HTML,
    NotifyFormat.MARKDOWN,
)


class OverflowMode:
    """
    A list of pre-defined modes of how to handle the text when it exceeds the
    defined maximum message size.
    """

    # Send the data as is; untouched.  Let the upstream server decide how the
    # content is handled.  Some upstream services might gracefully handle this
    # with expected intentions; others might not.
    UPSTREAM = 'upstream'

    # Always truncate the text when it exceeds the maximum message size and
    # send it anyway
    TRUNCATE = 'truncate'

    # Split the message into multiple smaller messages that fit within the
    # limits of what is expected.  The smaller messages are sent
    SPLIT = 'split'


# Define our modes so we can verify if we need to
OVERFLOW_MODES = (
    OverflowMode.UPSTREAM,
    OverflowMode.TRUNCATE,
    OverflowMode.SPLIT,
)


class ConfigFormat:
    """
    A list of pre-defined config formats that can be passed via the
    apprise library.
    """

    # A text based configuration. This consists of a list of URLs delimited by
    # a new line.  pound/hashtag (#) or semi-colon (;) can be used as comment
    # characters.
    TEXT = 'text'

    # YAML files allow a more rich of an experience when settig up your
    # apprise configuration files.
    YAML = 'yaml'


# Define our configuration formats mostly used for verification
CONFIG_FORMATS = (
    ConfigFormat.TEXT,
    ConfigFormat.YAML,
)


class ContentIncludeMode:
    """
    The different Content inclusion modes.  All content based plugins will
    have one of these associated with it.
    """
    # - Content inclusion of same type only; hence a file:// can include
    #   a file://
    # - Cross file inclusion is not allowed unless insecure_includes (a flag)
    #   is set to True. In these cases STRICT acts as type ALWAYS
    STRICT = 'strict'

    # This content type can never be included
    NEVER = 'never'

    # This content can always be included
    ALWAYS = 'always'


CONTENT_INCLUDE_MODES = (
    ContentIncludeMode.STRICT,
    ContentIncludeMode.NEVER,
    ContentIncludeMode.ALWAYS,
)


class ContentLocation:
    """
    This is primarily used for handling file attachments.  The idea is
    to track the source of the attachment itself.  We don't want
    remote calls to a server to access local attachments for example.

    By knowing the attachment type and cross-associating it with how
    we plan on accessing the content, we can make a judgement call
    (for security reasons) if we will allow it.

    Obviously local uses of apprise can access both local and remote
    type files.
    """
    # Content is located locally (on the same server as apprise)
    LOCAL = 'local'

    # Content is located in a remote location
    HOSTED = 'hosted'

    # Content is inaccessible
    INACCESSIBLE = 'n/a'


CONTENT_LOCATIONS = (
    ContentLocation.LOCAL,
    ContentLocation.HOSTED,
    ContentLocation.INACCESSIBLE,
)

# This is a reserved tag that is automatically assigned to every
# Notification Plugin
MATCH_ALL_TAG = 'all'

# Will cause notification to trigger under any circumstance even if an
# exclusive tagging was provided.
MATCH_ALWAYS_TAG = 'always'
