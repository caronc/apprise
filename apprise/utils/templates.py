# -*- coding: utf-8 -*-
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
import re
import json


class TemplateType:
    """
    Defines the different template types we can perform parsing on
    """
    # RAW does nothing at all to the content being parsed
    # data is taken at it's absolute value
    RAW = 'raw'

    # Data is presumed to be of type JSON and is therefore escaped
    # if required to do so (such as single quotes)
    JSON = 'json'


def apply_template(template, app_mode=TemplateType.RAW, **kwargs):
    """
    Takes a template in a str format and applies all of the keywords
    and their values to it.

    The app$mode is used to dictact any pre-processing that needs to take place
    to the escaped string prior to it being placed.  The idea here is for
    elements to be placed in a JSON response for example should be escaped
    early in their string format.

    The template must contain keywords wrapped in in double
    squirly braces like {{keyword}}.  These are matched to the respected
    kwargs passed into this function.

    If there is no match found, content is not swapped.

    """

    def _escape_raw(content):
        # No escaping necessary
        return content

    def _escape_json(content):
        # remove surounding quotes
        return json.dumps(content)[1:-1]

    # Our escape function
    fn = _escape_json if app_mode == TemplateType.JSON else _escape_raw

    lookup = [re.escape(x) for x in kwargs.keys()]

    # Compile this into a list
    mask_r = re.compile(
        re.escape('{{') + r'\s*(' + '|'.join(lookup) + r')\s*'
        + re.escape('}}'), re.IGNORECASE)

    # we index 2 characters off the head and 2 characters from the tail
    # to drop the '{{' and '}}' surrounding our match so that we can
    # re-index it back into our list
    return mask_r.sub(lambda x: fn(kwargs[x.group()[2:-2].strip()]), template)
