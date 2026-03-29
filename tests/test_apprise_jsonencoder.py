# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
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

import base64
from datetime import datetime, timezone
import json

# Disable logging for a cleaner testing output
import logging
import sys
from unittest import mock

import pytest

from apprise import Apprise
from apprise.common import AWARE_DATE_ISO_FORMAT, NAIVE_DATE_ISO_FORMAT
from apprise.locale import LazyTranslation
from apprise.utils.json import AppriseJSONEncoder

logging.disable(logging.CRITICAL)

# Ensure we don't create .pyc files for these tests
sys.dont_write_bytecode = True


def test_apprise_json_encoder_datetime_naive():
    "AppriseJSONEncoder: naive datetime serialization"

    dt = datetime(2026, 3, 11, 12, 30, 45, 123456)
    result = json.dumps(dt, cls=AppriseJSONEncoder)
    assert result == f'"{dt.strftime(NAIVE_DATE_ISO_FORMAT)}"'
    assert "T" in result
    # Naive datetimes have no timezone offset
    assert result.endswith('"')
    assert "+00:00" not in result


def test_apprise_json_encoder_datetime_aware():
    "AppriseJSONEncoder: aware datetime serialization"

    dt = datetime(2026, 3, 11, 12, 30, 45, 123456, tzinfo=timezone.utc)
    result = json.dumps(dt, cls=AppriseJSONEncoder)
    assert result == f'"{dt.strftime(AWARE_DATE_ISO_FORMAT)}"'
    assert "T" in result
    # Aware datetimes include the timezone offset
    assert "+0000" in result


def test_apprise_json_encoder_bytes():
    "AppriseJSONEncoder: bytes serialization"

    data = b"hello world"
    result = json.dumps(data, cls=AppriseJSONEncoder)
    expected = base64.b64encode(data).decode("utf-8")
    assert result == f'"{expected}"'

    # Empty bytes
    result = json.dumps(b"", cls=AppriseJSONEncoder)
    assert result == '""'

    # Binary data
    data = bytes(range(256))
    result = json.dumps(data, cls=AppriseJSONEncoder)
    expected = base64.b64encode(data).decode("utf-8")
    assert result == f'"{expected}"'


def test_apprise_json_encoder_set():
    "AppriseJSONEncoder: set serialization"

    data = {1, 2, 3}
    result = json.loads(json.dumps(data, cls=AppriseJSONEncoder))
    assert isinstance(result, list)
    assert sorted(result) == [1, 2, 3]

    # Empty set
    result = json.loads(json.dumps(set(), cls=AppriseJSONEncoder))
    assert result == []


def test_apprise_json_encoder_frozenset():
    "AppriseJSONEncoder: frozenset serialization"

    data = frozenset([4, 5, 6])
    result = json.loads(json.dumps(data, cls=AppriseJSONEncoder))
    assert isinstance(result, list)
    assert sorted(result) == [4, 5, 6]

    # Empty frozenset
    result = json.loads(json.dumps(frozenset(), cls=AppriseJSONEncoder))
    assert result == []


def test_apprise_json_encoder_tuple():
    "AppriseJSONEncoder: tuple serialization"

    data = (7, 8, 9)
    result = json.loads(json.dumps(data, cls=AppriseJSONEncoder))
    assert isinstance(result, list)
    assert result == [7, 8, 9]

    # Empty tuple
    result = json.loads(json.dumps((), cls=AppriseJSONEncoder))
    assert result == []


def test_apprise_json_encoder_lazy_translation():
    "AppriseJSONEncoder: LazyTranslation serialization"

    lt = LazyTranslation(text="hello world")
    result = json.dumps(lt, cls=AppriseJSONEncoder)
    assert result == '"hello world"'

    # A translation with no gettext mapping returns the original text
    lt = LazyTranslation(text="no-translation-key-xyz")
    result = json.dumps(lt, cls=AppriseJSONEncoder)
    assert result == '"no-translation-key-xyz"'


def test_apprise_json_encoder_unsupported_type():
    "AppriseJSONEncoder: unsupported type raises TypeError"

    class CustomObj:
        pass

    with pytest.raises(TypeError):
        json.dumps(CustomObj(), cls=AppriseJSONEncoder)


def test_apprise_json_encoder_nested():
    "AppriseJSONEncoder: nested structures with mixed types"

    data = {
        "when": datetime(2026, 3, 11, 0, 0, 0, tzinfo=timezone.utc),
        "payload": b"binary data",
        "tags": {"alpha", "beta"},
        "label": LazyTranslation(text="nested"),
        "coords": (1.0, 2.0),
    }
    result = json.loads(json.dumps(data, cls=AppriseJSONEncoder))

    assert isinstance(result["when"], str)
    assert "T" in result["when"]
    assert isinstance(result["payload"], str)
    assert result["payload"] == base64.b64encode(b"binary data").decode(
        "utf-8"
    )
    assert isinstance(result["tags"], list)
    assert sorted(result["tags"]) == ["alpha", "beta"]
    assert result["label"] == "nested"
    assert result["coords"] == [1.0, 2.0]


def test_apprise_json_method_no_path():
    "Apprise.json(): returns compact JSON string when no path is given"

    apobj = Apprise()

    # Default call — compact output (indent=None), no newlines
    result = apobj.json()
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert isinstance(parsed, dict)
    # Compact: no newlines in the output
    assert "\n" not in result

    # show_requirements and show_disabled flags are forwarded to details()
    result_req = apobj.json(show_requirements=True)
    assert isinstance(result_req, str)
    assert json.loads(result_req)

    result_dis = apobj.json(show_disabled=True)
    assert isinstance(result_dis, str)
    assert json.loads(result_dis)


def test_apprise_json_method_indent():
    "Apprise.json(): indent > 0 produces pretty-printed output with newlines"

    apobj = Apprise()

    result = apobj.json(indent=4)
    assert isinstance(result, str)
    # Pretty-printed output contains newlines
    assert "\n" in result
    assert json.loads(result)


def test_apprise_json_method_with_path(tmpdir):
    "Apprise.json(): writes JSON to file and returns True"

    apobj = Apprise()
    output = tmpdir.join("details.json")

    assert apobj.json(path=str(output)) is True
    assert output.check(file=True)

    content = output.read()
    parsed = json.loads(content)
    assert isinstance(parsed, dict)

    # Compact by default — no newlines
    assert "\n" not in content


def test_apprise_json_method_with_path_and_indent(tmpdir):
    "Apprise.json(): writes pretty-printed JSON to file when indent is set"

    apobj = Apprise()
    output = tmpdir.join("details_pretty.json")

    assert apobj.json(path=str(output), indent=2) is True
    content = output.read()
    assert "\n" in content
    assert json.loads(content)


def test_apprise_json_method_write_failure(tmpdir):
    "Apprise.json(): returns False when json.dump raises OSError"

    apobj = Apprise()
    output = tmpdir.join("fail.json")

    with mock.patch(
        "apprise.apprise.json.dump", side_effect=OSError("disk full")
    ):
        assert apobj.json(path=str(output)) is False


def test_apprise_json_method_write_eoferror(tmpdir):
    "Apprise.json(): returns False when json.dump raises EOFError"

    apobj = Apprise()
    output = tmpdir.join("eof.json")

    with mock.patch("apprise.apprise.json.dump", side_effect=EOFError):
        assert apobj.json(path=str(output)) is False
