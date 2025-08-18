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
import contextlib
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..logger import logger


def zoneinfo(name: str) -> ZoneInfo:
    """
    More forgiving ZoneInfo instantiation
    - Accepts lower/upper case
    - Normalises common UTC variants
    """
    if not isinstance(name, str):
        return None

    # Normalise common UTC spellings
    if name.lower() in {"utc", "z", "gmt"}:
        name = "UTC"

    # Try exact match first
    try:
        return ZoneInfo(name)

    except ValueError:
        # Just all around bad data; no need to proceed
        return None

    except ZoneInfoNotFoundError:
        pass

    # Try case-insensitive match across available keys
    from zoneinfo import available_timezones
    lowered = name.lower().strip()
    for zone in available_timezones():
        full_zone = zone.lower()
        if full_zone == lowered:
            return ZoneInfo(zone)

        with contextlib.suppress(IndexError):
            location = full_zone.split("/")[1:][0]
            if location and location == lowered:
                return ZoneInfo(zone)

    logger.warning("Unknown timezone specified: %s", name)
    return None
