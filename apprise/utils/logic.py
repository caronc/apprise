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
from itertools import chain

from .. import common
from .parse import parse_list


def is_exclusive_match(
    logic,
    data,
    match_all=common.MATCH_ALL_TAG,
    match_always=common.MATCH_ALWAYS_TAG,
):
    """The data variable should always be a set of strings that the logic can
    be compared against. It should be a set.  If it isn't already, then it will
    be converted as such. These identify the tags themselves.

    Our logic should be a list as well:
      - top level entries are treated as an 'or'
      - second level (or more) entries are treated as 'and'

      examples:
        logic="tagA, tagB"                = tagA or tagB
        logic=['tagA', 'tagB']            = tagA or tagB
        logic=[('tagA', 'tagC'), 'tagB']  = (tagA and tagC) or tagB
        logic=[('tagB', 'tagC')]          = tagB and tagC

    If `match_always` is not set to None, then its value is added as an 'or'
    to all specified logic searches.
    """

    if isinstance(logic, str):
        # Update our logic to support our delimiters
        logic = set(parse_list(logic))

    if not logic:
        # If there is no logic to apply then we're done early; we only match
        # if there is also no data to match against
        return not data

    if not isinstance(logic, (list, tuple, set)):
        # garbage input
        return False

    if match_always:
        # Add our match_always to our logic searching if secified
        logic = chain(logic, [match_always])

    # Track what we match against; but by default we do not match
    # against anything
    matched = False

    # Every entry here will be or'ed with the next
    for entry in logic:
        if not isinstance(entry, (str, list, tuple, set)):
            # Garbage entry in our logic found
            return False

        # treat these entries as though all elements found
        # must exist in the notification service
        entries = set(parse_list(entry))
        if not entries:
            # We got a bogus set of tags to parse
            # If there is no logic to apply then we're done early; we only
            # match if there is also no data to match against
            return not data

        if len(entries.intersection(data.union({match_all}))) == len(entries):
            # our set contains all of the entries found
            # in our notification data set
            matched = True
            break

        # else: keep looking

    # Return True if we matched against our logic (or simply none was
    # specified).
    return matched


def dict_full_update(dict1, dict2):
    """Takes 2 dictionaries (dict1 and dict2) that contain sub-dictionaries and
    gracefully merges them into dict1.

    This is similar to: dict1.update(dict2) except that internal dictionaries
    are also recursively applied.
    """

    def _merge(dict1, dict2):
        for k in dict2:
            if (
                k in dict1
                and isinstance(dict1[k], dict)
                and isinstance(dict2[k], dict)
            ):
                _merge(dict1[k], dict2[k])
            else:
                dict1[k] = dict2[k]

    _merge(dict1, dict2)
    return
