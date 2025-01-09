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
import copy
import json
import binascii
import typing
import base64


def decode_b64_dict(di: dict) -> dict:
    """
    decodes base64 dictionary previously encoded

    string entries prefixed with `b64:` are targeted
    """
    di = copy.deepcopy(di)
    for k, v in di.items():
        if not isinstance(v, str) or not v.startswith("b64:"):
            continue

        try:
            parsed_v = base64.b64decode(v[4:])
            parsed_v = json.loads(parsed_v)

        except (ValueError, TypeError, binascii.Error,
                json.decoder.JSONDecodeError):
            # ValueError: the length of altchars is not 2.
            # TypeError: invalid input
            # binascii.Error: not base64 (bad padding)
            # json.decoder.JSONDecodeError: Bad JSON object

            parsed_v = v
        di[k] = parsed_v
    return di


def encode_b64_dict(di: dict, encoding='utf-8') -> typing.Tuple[dict, bool]:
    """
    Encodes dictionary entries containing binary types (int, float) into base64

    Final product is always string based values
    """
    di = copy.deepcopy(di)
    needs_decoding = False
    for k, v in di.items():
        if isinstance(v, str):
            continue

        try:
            encoded = base64.urlsafe_b64encode(json.dumps(v).encode(encoding))
            encoded = "b64:{}".format(encoded.decode(encoding))
            needs_decoding = True

        except (ValueError, TypeError):
            # ValueError:
            #  - the length of altchars is not 2.
            # TypeError:
            #  - json not searializable or
            #  - bytes object not passed into urlsafe_b64encode()
            encoded = str(v)

        di[k] = encoded
    return di, needs_decoding
