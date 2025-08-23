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

from datetime import datetime, timezone as _tz, tzinfo
from inspect import cleandoc

# Disable logging for a cleaner testing output
import logging

import pytest
import yaml

from apprise import Apprise, AppriseAsset, AppriseConfig, ConfigFormat
from apprise.config import ConfigBase
from apprise.plugins.email import NotifyEmail
from apprise.utils.time import zoneinfo

logging.disable(logging.CRITICAL)


def test_config_base():
    """
    API: ConfigBase() object

    """

    # invalid types throw exceptions
    with pytest.raises(TypeError):
        ConfigBase(**{"format": "invalid"})

    # Config format types are not the same as ConfigBase ones
    with pytest.raises(TypeError):
        ConfigBase(**{"format": "markdown"})

    cb = ConfigBase(**{"format": "yaml"})
    assert isinstance(cb, ConfigBase)

    cb = ConfigBase(**{"format": "text"})
    assert isinstance(cb, ConfigBase)

    # Set encoding
    cb = ConfigBase(encoding="utf-8", format="text")
    assert isinstance(cb, ConfigBase)

    # read is not supported in the base object; only the children
    assert cb.read() is None

    # There are no servers loaded on a freshly created object
    assert len(cb.servers()) == 0

    # Unsupported URLs are not parsed
    assert ConfigBase.parse_url(url="invalid://") is None

    # Valid URL & Valid Format
    results = ConfigBase.parse_url(
        url="file://relative/path?format=yaml&encoding=latin-1"
    )
    assert isinstance(results, dict)
    # These are moved into the root
    assert results.get("format") == "yaml"
    assert results.get("encoding") == "latin-1"

    # But they also exist in the qsd location
    assert isinstance(results.get("qsd"), dict)
    assert results["qsd"].get("encoding") == "latin-1"
    assert results["qsd"].get("format") == "yaml"

    # Valid URL & Invalid Format
    results = ConfigBase.parse_url(
        url="file://relative/path?format=invalid&encoding=latin-1"
    )
    assert isinstance(results, dict)
    # Only encoding is moved into the root
    assert "format" not in results
    assert results.get("encoding") == "latin-1"

    # But they will always exist in the qsd location
    assert isinstance(results.get("qsd"), dict)
    assert results["qsd"].get("encoding") == "latin-1"
    assert results["qsd"].get("format") == "invalid"


def test_config_base_detect_config_format():
    """
    API: ConfigBase.detect_config_format

    """

    # Garbage Handling
    for garbage in (object(), None, 42):
        # A response is always correctly returned
        assert ConfigBase.detect_config_format(garbage) is None

    # Empty files are valid
    assert ConfigBase.detect_config_format("") is ConfigFormat.TEXT

    # Valid Text Configuration
    assert ConfigBase.detect_config_format("""
    # A comment line over top of a URL
    mailto://userb:pass@gmail.com
    """) is ConfigFormat.TEXT

    # A text file that has semi-colon as comment characters
    # is valid too
    assert ConfigBase.detect_config_format("""
    ; A comment line over top of a URL
    mailto://userb:pass@gmail.com
    """) is ConfigFormat.TEXT

    # Valid YAML Configuration
    assert ConfigBase.detect_config_format("""
    # A comment line over top of a URL
    version: 1
    """) is ConfigFormat.YAML

    # Just a whole lot of blank lines...
    assert ConfigBase.detect_config_format("\n\n\n") is ConfigFormat.TEXT

    # Invalid Config
    assert ConfigBase.detect_config_format("3") is None


def test_config_base_config_parse():
    """
    API: ConfigBase.config_parse

    """

    # Garbage Handling
    for garbage in (object(), None, 42):
        # A response is always correctly returned
        result = ConfigBase.config_parse(garbage)
        # response is a tuple...
        assert isinstance(result, tuple)
        # containing 2 items (plugins, config)
        assert len(result) == 2
        # In the case of garbage in, we get garbage out; both lists are empty
        assert result == ([], [])

    # Valid Text Configuration
    result = ConfigBase.config_parse(
        """
    # A comment line over top of a URL
    mailto://userb:pass@gmail.com
    """,
        asset=AppriseAsset(),
    )
    # We expect to parse 1 entry from the above
    assert isinstance(result, tuple)
    assert len(result) == 2
    # The first element is the number of notification services processed
    assert len(result[0]) == 1
    # If we index into the item, we can check to see the tags associate
    # with it
    assert len(result[0][0].tags) == 0

    # The second is the number of configuration include lines parsed
    assert len(result[1]) == 0

    # Valid Configuration
    result = ConfigBase.config_parse(
        """
# if no version is specified then version 1 is presumed
version: 1

#
# Define your notification urls:
#
urls:
  - pbul://o.gn5kj6nfhv736I7jC3cj3QLRiyhgl98b
  - mailto://test:password@gmail.com
  - json://localhost:
      - tag: devops, admin
    """,
        asset=AppriseAsset(),
    )

    # We expect to parse 2 entries from the above
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], list)
    assert len(result[0]) == 3
    assert len(result[0][0].tags) == 0
    assert len(result[0][1].tags) == 0
    assert len(result[0][2].tags) == 2

    # Test case where we pass in a bad format
    result = ConfigBase.config_parse(
        """
    ; A comment line over top of a URL
    mailto://userb:pass@gmail.com
    """,
        config_format="invalid-format",
    )

    # This is not parseable despite the valid text
    assert isinstance(result, tuple)
    assert isinstance(result[0], list)
    assert len(result[0]) == 0

    result, _ = ConfigBase.config_parse(
        """
    ; A comment line over top of a URL
    mailto://userb:pass@gmail.com
    """,
        config_format=ConfigFormat.TEXT,
    )

    # Parseable
    assert isinstance(result, list)
    assert len(result) == 1


def test_config_base_discord_bug_report_01():
    """
    API: ConfigBase.config_parse user feedback

    A Discord report that a tag was not correctly assigned to a URL when
    presented in the following format
       urls:
         - json://myhost:
           - tag: test
             userid: test
    """
    result, config = ConfigBase.config_parse(
        """
    urls:
      - json://myhost:
        - tag: test
          userid: test
    """,
        asset=AppriseAsset(),
    )

    # We expect to parse 4 entries from the above
    assert isinstance(result, list)
    assert isinstance(config, list)
    assert len(result) == 1
    assert len(result[0].tags) == 1
    assert "test" in result[0].tags


def test_config_base_config_parse_text():
    """
    API: ConfigBase.config_parse_text object

    """

    # Garbage Handling
    for garbage in (object(), None, 42):
        # A response is always correctly returned
        result = ConfigBase.config_parse_text(garbage)
        # response is a tuple...
        assert isinstance(result, tuple)
        # containing 2 items (plugins, config)
        assert len(result) == 2
        # In the case of garbage in, we get garbage out; both lists are empty
        assert result == ([], [])

    # Valid Configuration
    result, config = ConfigBase.config_parse_text(
        """
    # A completely invalid token on json string (it gets ignored)
    # but the URL is still valid
    json://localhost?invalid-token=nodashes

    # A comment line over top of a URL
    mailto://userb:pass@gmail.com

    # Test a URL using it's native format; in this case Ryver
    https://apprise.ryver.com/application/webhook/ckhrjW8w672m6HG

    # Invalid URL as it's not associated with a plugin
    # or a native url
    https://not.a.native.url/

    # A line with mulitiple tag assignments to it
    taga,tagb=kde://

    # An include statement to Apprise API with trailing spaces:
    include http://localhost:8080/notify/apprise

    # A relative include statement (with trailing spaces)
    include apprise.cfg     """,
        asset=AppriseAsset(),
    )

    # We expect to parse 4 entries from the above
    assert isinstance(result, list)
    assert isinstance(config, list)
    assert len(result) == 4
    assert len(result[0].tags) == 0

    # Our last element will have 2 tags associated with it
    assert len(result[-1].tags) == 2
    assert "taga" in result[-1].tags
    assert "tagb" in result[-1].tags

    assert len(config) == 2
    assert "http://localhost:8080/notify/apprise" in config
    assert "apprise.cfg" in config

    # Here is a similar result set however this one has an invalid line
    # in it which invalidates the entire file
    result, config = ConfigBase.config_parse_text("""
    # A comment line over top of a URL
    mailto://userc:pass@gmail.com

    # A line with mulitiple tag assignments to it
    taga,tagb=windows://

    I am an invalid line that does not follow any of the Apprise file rules!
    """)

    # We expect to parse 0 entries from the above because the invalid line
    # invalidates the entire configuration file. This is for security reasons;
    # we don't want to point at files load content in them just because they
    # resemble an Apprise configuration.
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # More invalid data
    result, config = ConfigBase.config_parse_text("""
    # An invalid URL
    invalid://user:pass@gmail.com

    # A tag without a url
    taga=

    # A very poorly structured url
    sns://:@/

    # Just 1 token provided
    sns://T1JJ3T3L2/

    # Even with the above invalid entries, we can still
    # have valid include lines
    include file:///etc/apprise.cfg

    # An invalid include (nothing specified afterwards)
    include

    # An include of a config type we don't support
    include invalid://
    """)

    # We expect to parse 0 entries from the above
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Test case where a comment is on it's own line with nothing else
    result, config = ConfigBase.config_parse_text("#")
    # We expect to parse 0 entries from the above
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Verify our tagging works when multiple tags are provided
    result, config = ConfigBase.config_parse_text("""
    tag1, tag2, tag3=json://user:pass@localhost
    """)

    assert isinstance(result, list)
    assert len(result) == 1
    assert len(result[0].tags) == 3
    assert "tag1" in result[0].tags
    assert "tag2" in result[0].tags
    assert "tag3" in result[0].tags


def test_config_base_config_tag_groups_text():
    """
    API: ConfigBase.config_tag_groups_text object

    """

    # Valid Configuration
    result, config = ConfigBase.config_parse_text(
        """
    # Tag assignments
    groupA, groupB = tagB, tagC

    # groupB doubles down as it takes the entries initialized above
    # plus the added ones defined below
    groupB = tagA, tagB, tagD
    groupC = groupA, groupB, groupC, tagE

    # Tag that recursively looks to more tags
    groupD = groupC

    # Assigned ourselves
    groupX = groupX

    # Set up a recursive loop
    groupE = groupF
    groupF = groupE

    # Set up a larger recursive loop
    groupG = groupH
    groupH = groupI
    groupI = groupJ
    groupJ = groupK
    groupK = groupG

    # Bad assignments
    groupM = , , ,
     , ,   = , , ,

    # int's and floats are okay
    1 = 2
    a = 5

    # A comment line over top of a URL
    4, groupB = mailto://userb:pass@gmail.com

    # Tag Assignments
    tagA,groupB=json://localhost

    # More Tag Assignments
    tagC,groupB=xml://localhost

    # More Tag Assignments
    groupD=form://localhost

    """,
        asset=AppriseAsset(),
    )

    # We expect to parse 4 entries from the above
    assert isinstance(result, list)
    assert isinstance(config, list)
    assert len(result) == 4

    # Our first element is our group tags
    assert len(result[0].tags) == 2
    assert "groupB" in result[0].tags
    assert "4" in result[0].tags

    # No additional configuration is loaded
    assert len(config) == 0

    apobj = Apprise()
    assert apobj.add(result)
    # We match against 1 entry
    assert len(list(apobj.find("tagA"))) == 1
    assert len(list(apobj.find("tagB"))) == 0
    assert len(list(apobj.find("groupA"))) == 1
    assert len(list(apobj.find("groupB"))) == 3
    assert len(list(apobj.find("groupC"))) == 2
    assert len(list(apobj.find("groupD"))) == 3

    # Invalid Assignment
    result, config = ConfigBase.config_parse_text("""
    # Must have something to equal or it's a bad line
    group =

    # A tag Assignments that is never gotten to as the line
    # above is bad
    groupD=form://localhost
    """)

    # We expect to parse 0 entries from the above
    assert isinstance(result, list)
    assert isinstance(config, list)
    assert len(result) == 0
    assert len(config) == 0

    # Invalid Assignment
    result, config = ConfigBase.config_parse_text("""
    # Rundant assignment
    group = group

    # Our group assignment
    group=windows://

    """)

    # the redundant assignment does us no harm; but it doesn't grant us any
    # value either
    assert isinstance(result, list)
    assert len(result) == 1

    # Our first element is our group tags
    assert len(result[0].tags) == 1
    assert "group" in result[0].tags

    # There were no include entries defined
    assert len(config) == 0

    # More invalid data
    result, config = ConfigBase.config_parse_text("""
    # A tag without a url or group assignment
    taga=

    """)

    # We expect to parse 0 entries from the above
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    result, config = ConfigBase.config_parse_text("""
    # A tag without a url or group assignment
    taga= %%INVALID
    """)

    # We expect to parse 0 entries from the above
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0


def test_config_base_config_parse_text_with_url():
    """
    API: ConfigBase.config_parse_text object_with_url

    """
    # Here is a similar result set however this one has an invalid line
    # in it which invalidates the entire file
    result, config = ConfigBase.config_parse_text("""
    # Test a URL that has a URL as an argument
    json://user:pass@localhost?+arg=http://example.com?arg2=1&arg3=3
    """)

    # No tag is parsed, but our URL successfully parses as is

    assert isinstance(result, list)
    assert len(result) == 1
    assert len(result[0].tags) == 0

    # Verify our URL is correctly captured
    assert "%2Barg=http%3A%2F%2Fexample.com%3Farg2%3D1" in result[0].url()
    assert "json://user:pass@localhost/" in result[0].url()

    # There were no include entries defined
    assert len(config) == 0

    # Pass in our configuration again
    result, config = ConfigBase.config_parse_text(result[0].url())

    # Verify that our results repeat themselves
    assert isinstance(result, list)
    assert len(result) == 1
    assert len(result[0].tags) == 0
    assert "%2Barg=http%3A%2F%2Fexample.com%3Farg2%3D1" in result[0].url()
    assert "json://user:pass@localhost/" in result[0].url()

    assert len(config) == 0


def test_config_base_config_parse_yaml():
    """
    API: ConfigBase.config_parse_yaml object

    """

    # general reference used below
    asset = AppriseAsset()

    # Garbage Handling
    for garbage in (object(), None, "", 42):
        # A response is always correctly returned
        result = ConfigBase.config_parse_yaml(garbage)
        # response is a tuple...
        assert isinstance(result, tuple)
        # containing 2 items (plugins, config)
        assert len(result) == 2
        # In the case of garbage in, we get garbage out; both lists are empty
        assert result == ([], [])

    # Invalid Version
    result, config = ConfigBase.config_parse_yaml("version: 2a", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid Syntax (throws a ScannerError)
    result, config = ConfigBase.config_parse_yaml(
        """
# if no version is specified then version 1 is presumed
version: 1

urls
""",
        asset=asset,
    )

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Missing url token
    result, config = ConfigBase.config_parse_yaml(
        """
# if no version is specified then version 1 is presumed
version: 1

""",
        asset=asset,
    )

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # No urls defined
    result, config = ConfigBase.config_parse_yaml(
        """
# if no version is specified then version 1 is presumed
version: 1

urls:
""",
        asset=asset,
    )

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid url defined
    result, config = ConfigBase.config_parse_yaml(
        """
# if no version is specified then version 1 is presumed
version: 1

# Invalid URL definition; yet the answer to life at the same time
urls: 43
""",
        asset=asset,
    )

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid url/schema
    result, config = ConfigBase.config_parse_yaml(
        """
# if no version is specified then version 1 is presumed
version: 1

urls:
  - invalid://

""",
        asset=asset,
    )

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid url/schema
    result, config = ConfigBase.config_parse_yaml(
        """
# if no version is specified then version 1 is presumed
version: 1

urls:
  - invalid://:
    - a: b

""",
        asset=asset,
    )

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid url/schema
    result, config = ConfigBase.config_parse_yaml(
        """
# Include entry with nothing associated with it
include:

urls:
  - just some free text that isn't valid:
    - a garbage entry to go with it

""",
        asset=asset,
    )

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid url/schema
    result, config = ConfigBase.config_parse_yaml(
        """
# if no version is specified then version 1 is presumed
version: 1

urls:
  - not even a proper url

""",
        asset=asset,
    )

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid url/schema
    result, config = ConfigBase.config_parse_yaml(
        """
urls:
  # a very invalid sns entry
  - sns://T1JJ3T3L2/
  - sns://:@/:
    - invalid: test
  - sns://T1JJ3T3L2/:
    - invalid: test
    - _invalid: Token can not start with an underscore

  # some strangeness
  -
    -
      - test

""",
        asset=asset,
    )

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Valid Configuration
    result, config = ConfigBase.config_parse_yaml(
        """
# if no version is specified then version 1 is presumed
version: 1

# Including by dict
include:
  # File includes
  - file:///absolute/path/
  - relative/path
  # Trailing colon shouldn't disrupt include
  - http://test.com:

  # invalid (numeric)
  - 4

  # some strangeness
  -
    -
      - test

#
# Define your notification urls:
#
urls:
  - pbul://o.gn5kj6nfhv736I7jC3cj3QLRiyhgl98b
  - mailto://test:password@gmail.com
  - https://apprise.ryver.com/application/webhook/ckhrjW8w672m6HG
  - https://not.a.native.url/

    # A completely invalid token on json string (it gets ignored)
    # but the URL is still valid
  - json://localhost?invalid-token=nodashes

""",
        asset=asset,
    )

    # We expect to parse 4 entries from the above
    # The Ryver one is in a native form and the 4th one is invalid
    assert isinstance(result, list)
    assert len(result) == 4
    assert len(result[0].tags) == 0

    # There were 3 include entries
    assert len(config) == 3
    assert "file:///absolute/path/" in config
    assert "relative/path" in config
    assert "http://test.com" in config

    # Valid Configuration
    result, config = ConfigBase.config_parse_yaml(
        """
# A single line include is supported
include: http://localhost:8080/notify/apprise

urls:
  # The following generates 1 service
  - json://localhost:
       tag: my-custom-tag, my-other-tag

  # The following also generates 1 service
  - json://localhost:
    - tag: my-custom-tag, my-other-tag

  # How to stack multiple entries (this generates 2):
  - mailto://user:123abc@yahoo.ca:
    - to: test@examle.com
    - to: test2@examle.com

      # This is an illegal entry; the schema can not be changed
      schema: json

  # accidently left a colon at the end of the url; no problem
  # we'll accept it
  - mailto://oscar:pass@gmail.com:

  # A Ryver URL (using Native format); still accepted
  - https://apprise.ryver.com/application/webhook/ckhrjW8w672m6HG:

  # An invalid URL with colon (ignored)
  - https://not.a.native.url/:

  # A telegram entry (returns a None in parse_url())
  - tgram://invalid

""",
        asset=asset,
    )

    # We expect to parse 6 entries from the above because the tgram:// entry
    # would have failed to be loaded
    assert isinstance(result, list)
    assert len(result) == 6
    assert len(result[0].tags) == 2

    # Our single line included
    assert len(config) == 1
    assert "http://localhost:8080/notify/apprise" in config

    # Global Tags
    result, config = ConfigBase.config_parse_yaml(
        """
# Global Tags stacked as a list
tag:
  - admin
  - devops

urls:
  - json://localhost
  - dbus://
""",
        asset=asset,
    )

    # We expect to parse 2 entries from the above
    assert isinstance(result, list)
    assert len(result) == 2

    # There were no include entries defined
    assert len(config) == 0

    # all entries will have our global tags defined in them
    for entry in result:
        assert "admin" in entry.tags
        assert "devops" in entry.tags

    # Global Tags
    result, config = ConfigBase.config_parse_yaml(
        """
# Global Tags
tag: admin, devops

urls:
  # The following tags will get added to the global set
  - json://localhost:
    - tag: string-tag, my-other-tag, text

  # Tags can be presented in this list format too:
  - dbus://:
    - tag:
      - list-tag
      - dbus
""",
        asset=asset,
    )

    # all entries will have our global tags defined in them
    for entry in result:
        assert "admin" in entry.tags
        assert "devops" in entry.tags

    # We expect to parse 2 entries from the above
    assert isinstance(result, list)
    assert len(result) == 2

    # json:// has 2 globals + 3 defined
    assert len(result[0].tags) == 5
    assert "text" in result[0].tags

    # json:// has 2 globals + 2 defined
    assert len(result[1].tags) == 4
    assert "list-tag" in result[1].tags

    # There were no include entries defined
    assert len(config) == 0

    # An invalid set of entries
    result, config = ConfigBase.config_parse_yaml(
        """
urls:
  # The following tags will get added to the global set
  - json://localhost:
    -
      -
        - entry
""",
        asset=asset,
    )

    # We expect to parse 0 entries from the above
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # An asset we'll manipulate; set some system flags
    asset = AppriseAsset(_uid="abc123", _recursion=1)

    # Global Tags
    result, config = ConfigBase.config_parse_yaml(
        """
# Test the creation of our apprise asset object
asset:
  app_id: AppriseTest
  app_desc: Apprise Test Notifications
  app_url: http://nuxref.com
  async_mode: no

  # System flags should never get set
  _uid: custom_id
  _recursion: 100

  # Support setting empty values
  image_url_mask:
  image_url_logo:

  image_path_mask: tmp/path

  # Timezone (supports tz keyword too)
  tz: America/Montreal

  # invalid entry
  theme:
    -
      -
        - entry

  # Now for some invalid entries
  invalid: entry
  __init__: can't be over-ridden
  nolists:
    - we don't support these entries
    - in the apprise object

urls:
  - json://localhost:
""",
        asset=asset,
    )

    # We expect to parse 1 entries from the above
    assert isinstance(result, list)
    assert len(result) == 1

    # There were no include entries defined
    assert len(config) == 0

    assert asset.app_id == "AppriseTest"
    assert asset.app_desc == "Apprise Test Notifications"
    assert asset.app_url == "http://nuxref.com"

    # Verify our system flags retain only the value they were initialized to
    assert asset._uid == "abc123"
    assert asset._recursion == 1

    # Boolean types stay boolean
    assert asset.async_mode is False

    # Our TimeZone
    assert isinstance(asset.tzinfo, tzinfo)
    assert asset.tzinfo.key == zoneinfo("America/Montreal").key

    # the theme was not updated and remains the same as it was
    assert asset.theme == AppriseAsset().theme

    # Empty string assignment
    assert isinstance(asset.image_url_mask, str)
    assert asset.image_url_mask == ""
    assert isinstance(asset.image_url_logo, str)
    assert asset.image_url_logo == ""

    # For on-lookers looking through this file; here is a perfectly formatted
    # YAML configuration file for your reference so you can see it without
    # all of the errors like the ones identified above
    result, config = ConfigBase.config_parse_yaml(
        """
# if no version is specified then version 1 is presumed. Thus this is a
# completely optional field. It's a good idea to just add this line because it
# will help with future ambiguity (if it ever occurs).
version: 1

# Define an Asset object if you wish (Optional)
asset:
  app_id: AppriseTest
  app_desc: Apprise Test Notifications
  app_url: http://nuxref.com

  # An invalid timezone
  timezone: invalid

# Optionally define some global tags to associate with ALL of your
# urls below.
tag: admin, devops

# Define your URLs (Mandatory!)
urls:
  # Either on-line each entry like this:
  - json://localhost

  # Or add a colon to the end of the URL where you can optionally provide
  # over-ride entries.  One of the most likely entry to be used here
  # is the tag entry.  This gets extended to the global tag (if defined)
  # above
  - xml://localhost:
    - tag: customer

  # The more elements you specify under a URL the more times the URL will
  # get replicated and used. Hence this entry actually could be considered
  # 2 URLs being called with just the destination email address changed:
  - mailto://george:password@gmail.com:
     - to: jason@hotmail.com
     - to: fred@live.com

  # Again... to re-iterate, the above mailto:// would actually fire two (2)
  # separate emails each with a different destination address specified.
  # Be careful when defining your arguments and differentiating between
  # when to use the dash (-) and when not to.  Each time you do, you will
  # cause another instance to be created.

  # Defining more then 1 element to a muti-set is easy, it looks like this:
  - mailto://jackson:abc123@hotmail.com:
     - to: jeff@gmail.com
       tag: jeff, customer

     - to: chris@yahoo.com
       tag: chris, customer
""",
        asset=asset,
    )

    # okay, here is how we get our total based on the above (read top-down)
    # +1  json:// entry
    # +1  xml:// entry
    # +2  mailto:// entry to jason@hotmail.com and fred@live.com
    # +2  mailto:// entry to jeff@gmail.com and chris@yahoo.com
    # = 6
    assert len(result) == 6

    # all six entries will have our global tags defined in them
    for entry in result:
        assert "admin" in entry.tags
        assert "devops" in entry.tags

    # Entries can be directly accessed as they were added

    # our json:// had no additional tags added; so just the global ones
    # So just 2; admin and devops (these were already validated above in the
    # for loop
    assert len(result[0].tags) == 2

    # our xml:// object has 1 tag added (customer)
    assert len(result[1].tags) == 3
    assert "customer" in result[1].tags

    # You get the idea, here is just a direct mapping to the remaining entries
    # in the same order they appear above
    assert len(result[2].tags) == 2
    assert len(result[3].tags) == 2

    assert len(result[4].tags) == 4
    assert "customer" in result[4].tags
    assert "jeff" in result[4].tags

    assert len(result[5].tags) == 4
    assert "customer" in result[5].tags
    assert "chris" in result[5].tags

    # There were no include entries defined
    assert len(config) == 0

    # Valid Configuration (multi inline configuration entries)
    result, config = ConfigBase.config_parse_yaml(
        """
# A configuration file that contains 2 includes separated by a comma and/or
# space:
include: http://localhost:8080/notify/apprise, http://localhost/apprise/cfg

""",
        asset=asset,
    )

    # We will have loaded no results
    assert isinstance(result, list)
    assert len(result) == 0

    # But our two configuration files will be present:
    assert len(config) == 2
    assert "http://localhost:8080/notify/apprise" in config
    assert "http://localhost/apprise/cfg" in config

    # Valid Configuration (another way of specifying more then one include)
    result, config = ConfigBase.config_parse_yaml(
        """
# A configuration file that contains 4 includes on their own
# lines beneath the keyword `include`:
include:
   http://localhost:8080/notify/apprise
   http://localhost/apprise/cfg01
   http://localhost/apprise/cfg02
   http://localhost/apprise/cfg03

""",
        asset=asset,
    )

    # We will have loaded no results
    assert isinstance(result, list)
    assert len(result) == 0

    # But our 4 configuration files will be present:
    assert len(config) == 4
    assert "http://localhost:8080/notify/apprise" in config
    assert "http://localhost/apprise/cfg01" in config
    assert "http://localhost/apprise/cfg02" in config
    assert "http://localhost/apprise/cfg03" in config

    # Test a configuration with an invalid schema with options
    result, config = ConfigBase.config_parse_yaml(
        """
    urls:
      - invalid://:
          tag: 'invalid'
          :name: 'Testing2'
          :body: 'test body2'
          :title: 'test title2'
""",
        asset=asset,
    )

    # We will have loaded no results
    assert isinstance(result, list)
    assert len(result) == 0

    # Valid Configuration (we allow comma separated entries for
    # each defined bullet)
    result, config = ConfigBase.config_parse_yaml(
        """
# A configuration file that contains 4 includes on their own
# lines beneath the keyword `include`:
include:
   - http://localhost:8080/notify/apprise, http://localhost/apprise/cfg01
     http://localhost/apprise/cfg02
   - http://localhost/apprise/cfg03

""",
        asset=asset,
    )

    # We will have loaded no results
    assert isinstance(result, list)
    assert len(result) == 0

    # But our 4 configuration files will be present:
    assert len(config) == 4
    assert "http://localhost:8080/notify/apprise" in config
    assert "http://localhost/apprise/cfg01" in config
    assert "http://localhost/apprise/cfg02" in config
    assert "http://localhost/apprise/cfg03" in config


def test_yaml_vs_text_tagging():
    """
    API: ConfigBase YAML vs TEXT tagging
    """

    yaml_result, _ = ConfigBase.config_parse_yaml("""
    urls:
      - mailtos://lead2gold:yesqbrulvaelyxve@gmail.com:
         tag: mytag
    """)
    assert yaml_result

    text_result, _ = ConfigBase.config_parse_text("""
    mytag=mailtos://lead2gold:yesqbrulvaelyxve@gmail.com
    """)
    assert text_result

    # Now we compare our results and verify they are the same
    assert len(yaml_result) == len(text_result)
    assert isinstance(yaml_result[0], NotifyEmail)
    assert isinstance(text_result[0], NotifyEmail)
    assert "mytag" in text_result[0]
    assert "mytag" in yaml_result[0]


def test_config_base_config_tag_groups_yaml_01():
    """
    API: ConfigBase.config_tag_groups_yaml #1 object

    """

    # general reference used below
    asset = AppriseAsset()

    # Valid Configuration
    result, config = ConfigBase.config_parse_yaml(
        """
# if no version is specified then version 1 is presumed
version: 1

groups:
  - group1: tagB, tagC, tagNotAssigned
  - group2:
      - tagA
      - tagC
  - group3:
      - tagD: optional comment
      - tagA: optional comment #2

  # No assignment
  - group4

  # No assignment type 2
  - group5:

  # Integer assignment
  - group6: 3
  - group6: 3, 4, 5, test
  - group6: 3.5, tagC

  # Recursion
  - groupA: groupB
  - groupB: groupA
  # And Again... (just because)
  - groupA: groupB
  - groupB: groupA

  # Self assignment
  - groupX: groupX

  # Set up a larger recursive loop
  - groupG: groupH
  - groupH: groupI, groupJ
  - groupI: groupJ, groupG
  - groupJ: groupK, groupH, groupI
  - groupK: groupG

  # No tags assigned
  - groupK: ",,  , ,"
  - " , ": ",, , ,"

  # Multi Assignments
  - groupL, groupM: tagD, tagA
  - 4, groupN:
     - tagD
     - tagE, TagA

  # Add one more tag to groupL making it different then GroupM by 1
  - groupL: tagB
#
# Define your notification urls:
#
urls:
  - form://localhost:
     - tag: tagA
  - mailto://test:password@gmail.com:
     - tag: tagB
  - xml://localhost:
     - tag: tagC
  - json://localhost:
     - tag: tagD, tagA

""",
        asset=asset,
    )

    # We expect to parse 4 entries from the above
    assert isinstance(result, list)
    assert isinstance(config, list)
    assert len(result) == 4

    # Our first element is our group tags
    assert len(result[0].tags) == 5
    assert "group2" in result[0].tags
    assert "group3" in result[0].tags
    assert "groupL" in result[0].tags
    assert "groupM" in result[0].tags
    assert "tagA" in result[0].tags

    # No additional configuration is loaded
    assert len(config) == 0

    apobj = Apprise()
    assert apobj.add(result)
    # We match against 1 entry
    assert len(list(apobj.find("tagA"))) == 2
    assert len(list(apobj.find("tagB"))) == 1
    assert len(list(apobj.find("tagC"))) == 1
    assert len(list(apobj.find("tagD"))) == 1
    assert len(list(apobj.find("group1"))) == 2
    assert len(list(apobj.find("group2"))) == 3
    assert len(list(apobj.find("group3"))) == 2
    assert len(list(apobj.find("group4"))) == 0
    assert len(list(apobj.find("group5"))) == 0
    # json:// -- group6 -> 4 -> TagA
    # xml://  -- group6 -> TagC
    assert len(list(apobj.find("group6"))) == 2
    assert len(list(apobj.find("4"))) == 1
    assert len(list(apobj.find("groupN"))) == 1


def test_config_base_config_tag_groups_yaml_02():
    """
    API: ConfigBase.config_tag_groups_yaml #2 object

    """

    # general reference used below
    asset = AppriseAsset()

    # Valid Configuration
    result, config = ConfigBase.config_parse_yaml(
        """
# if no version is specified then version 1 is presumed
version: 1

groups:
  group1: tagB, tagC, tagNotAssigned
  group2:
    - tagA
    - tagC
  group3:
    - tagD: optional comment
    - tagA: optional comment #2

  # No assignment type 2
  group5:

  # Integer assignment (since it's not a list, the last element prevails
  # and replaces the above); '4' does not get appended as it would in
  # the event this was a list instead
  group6: 3
  group6: 3, 4, 5, test
  group6: 3.5, tagC

  # Recursion
  groupA: groupB
  groupB: groupA
  # And Again... (just because)
  groupA: groupB
  groupB: groupA

  # Self assignment
  groupX: groupX

  # Set up a larger recursive loop
  groupG: groupH
  groupH: groupI, groupJ
  groupI: groupJ, groupG
  groupJ: groupK, groupH, groupI
  groupK: groupG

  # No tags assigned
  groupK: ",,  , ,"
  " , ": ",, , ,"

  # Multi Assignments
  groupL, groupM: tagD, tagA
  4, groupN:
   - tagD
   - tagE, TagA

  # Add one more tag to groupL making it different then GroupM by 1
  groupL: tagB
#
# Define your notification urls:
#
urls:
  - form://localhost:
     - tag: tagA
  - mailto://test:password@gmail.com:
     - tag: tagB
  - xml://localhost:
     - tag: tagC
  - json://localhost:
     - tag: tagD, tagA

""",
        asset=asset,
    )

    # We expect to parse 4 entries from the above
    assert isinstance(result, list)
    assert isinstance(config, list)
    assert len(result) == 4

    # Our first element is our group tags
    assert len(result[0].tags) == 5
    assert "group2" in result[0].tags
    assert "group3" in result[0].tags
    assert "groupL" in result[0].tags
    assert "groupM" in result[0].tags
    assert "tagA" in result[0].tags

    # No additional configuration is loaded
    assert len(config) == 0

    apobj = Apprise()
    assert apobj.add(result)
    # We match against 1 entry
    assert len(list(apobj.find("tagA"))) == 2
    assert len(list(apobj.find("tagB"))) == 1
    assert len(list(apobj.find("tagC"))) == 1
    assert len(list(apobj.find("tagD"))) == 1
    assert len(list(apobj.find("group1"))) == 2
    assert len(list(apobj.find("group2"))) == 3
    assert len(list(apobj.find("group3"))) == 2
    assert len(list(apobj.find("group4"))) == 0
    assert len(list(apobj.find("group5"))) == 0
    # NOT json:// -- group6 -> 4 -> TagA (not appended because dict storage)
    #                          ^
    #                          |
    #            See: test_config_base_config_tag_groups_yaml_01 (above)
    #                 dict storage (as this tests for) causes last entry to
    #                 prevail; previous assignments are lost
    #
    # xml://  -- group6 -> TagC
    assert len(list(apobj.find("group6"))) == 1
    assert len(list(apobj.find("4"))) == 1
    assert len(list(apobj.find("groupN"))) == 1
    assert len(list(apobj.find("groupK"))) == 0


def test_config_base_config_parse_yaml_globals():
    """
    API: ConfigBase.config_parse_yaml globals

    """

    # general reference used below
    asset = AppriseAsset()

    # Invalid Syntax (throws a ScannerError)
    results, config = ConfigBase.config_parse_yaml(
        cleandoc("""
    urls:
      - jsons://localhost1:
         - to: jeff@gmail.com
           tag: jeff, customer
           cto: 30
           rto: 30
           verify: no

      - jsons://localhost2?cto=30&rto=30&verify=no:
         - to: json@gmail.com
           tag: json, customer
    """),
        asset=asset,
    )

    # Invalid data gets us an empty result set
    assert isinstance(results, list)

    # Our results loaded
    assert len(results) == 2
    assert len(config) == 0

    # Now verify that our global variables correctly initialized
    for entry in results:
        assert entry.verify_certificate is False
        assert entry.socket_read_timeout == 30
        assert entry.socket_connect_timeout == 30


# This test fails on CentOS 8.x so it was moved into it's own function
# so it could be bypassed. The ability to use lists in YAML files didn't
# appear to happen until later on; it's certainly not available in v3.12
# which was what shipped with CentOS v8 at the time.
@pytest.mark.skipif(
    int(yaml.__version__.split(".")[0]) <= 3,
    reason="requires pyaml v4.x or higher.",
)
def test_config_base_config_parse_yaml_list():
    """
    API: ConfigBase.config_parse_yaml list parsing

    """

    # general reference used below
    asset = AppriseAsset()

    # Invalid url/schema
    result, config = ConfigBase.config_parse_yaml(
        """
# no lists... just no
urls: [milk, pumpkin pie, eggs, juice]

# Including by list is okay
include: [file:///absolute/path/, relative/path, http://test.com]

""",
        asset=asset,
    )

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were 3 include entries
    assert len(config) == 3
    assert "file:///absolute/path/" in config
    assert "relative/path" in config
    assert "http://test.com" in config


def test_yaml_asset_timezone_and_asset_tokens(tmpdir):
    """
    Covers: valid tz, reserved keys, invalid key, bool coercion, None->"",
    invalid type for string, and %z formatting path used later by plugins.
    """
    cfg = tmpdir.join("asset-tz.yml")
    cfg.write(
        """
version: 1
asset:
  tz: "  america/toronto  "     # case-insensitive + whitespace cleanup
  _private: "ignored"           # reserved (starts with _)
  name_: "ignored"              # reserved (ends with _)
  not_a_field: "ignored"        # invalid asset key
  secure_logging: "yes"         # string -> bool via parse_bool
  app_id: null                  # None becomes empty string
  app_desc: [ "list" ]          # invalid type for string -> warning path
urls:
  - json://localhost
"""
    )

    ac = AppriseConfig(paths=str(cfg))
    # Force a fresh parse and get the loaded plugin
    servers = ac.servers()
    assert len(servers) == 1

    plugin = servers[0]
    asset = plugin.asset

    # tz was accepted and normalised
    # lower() is required since Mac and Window are not case sensitive and will
    # See output as it was passed in and not corrected per IANA
    assert getattr(asset.tzinfo, "key", None).lower() == "america/toronto"
    # boolean coercion applied
    assert asset.secure_logging is True
    # None -> ""
    assert asset.app_id == ""


def test_yaml_asset_timezone_invalid_and_precedence(tmpdir):
    """
    If 'timezone' is present but invalid, it takes precedence over 'tz'
    and MUST NOT set the asset to the 'tz' value. We assert that London
    was not applied. We deliberately avoid asserting the exact fallback,
    since environments may surface a system tz (datetime.timezone) that
    lacks a `.key` attribute.
    """
    cfg = tmpdir.join("asset-tz-invalid.yml")
    cfg.write(
        """
version: 1
asset:
  timezone: null                # invalid (will be seen as "None")
  tz: Europe/London             # would be valid, but 'timezone' wins
urls:
  - json://localhost
"""
    )

    base_asset = AppriseAsset(timezone="UTC")
    ac = AppriseConfig(paths=str(cfg))
    servers = ac.servers(asset=base_asset)
    assert len(servers) == 1

    tzinfo = servers[0].asset.tzinfo

    # The key assertion: 'tz' MUST NOT have been applied
    assert getattr(tzinfo, "key", "").lower() != "europe/london"

    # Sanity check that something sensible is set
    # Compare offsets at a fixed instant instead of object identity
    dt = datetime(2024, 1, 1, 12, 0, tzinfo=_tz.utc)
    assert tzinfo.utcoffset(dt) is not None


@pytest.mark.parametrize("garbage_yaml", [
    "123", "3.1415", "true", "[UTC]", "{x: UTC}",
])
def test_yaml_asset_tz_garbage_types_only(tmpdir, garbage_yaml):
    """
    If only 'tz' is present and it is non-string, it is ignored.
    We assert it didn't become a real IANA zone (e.g., Europe/London),
    and that the tzinfo is usable.
    """
    cfg = tmpdir.join("asset-tz-garbage-only.yml")
    cfg.write(
        f"""
version: 1
asset:
  tz: {garbage_yaml}            # non-string -> warning path
urls:
  - json://localhost
"""
    )

    base_asset = AppriseAsset(timezone="UTC")
    ac = AppriseConfig(paths=str(cfg))
    servers = ac.servers(asset=base_asset)
    assert len(servers) == 1

    tzinfo = servers[0].asset.tzinfo

    # 1) Did not “accidentally” become a valid IANA from elsewhere.
    assert getattr(tzinfo, "key", "").lower() != "europe/london"

    # 2) tzinfo is usable (offset resolves at a fixed instant).
    dt = datetime(2024, 1, 1, 12, 0, tzinfo=_tz.utc)
    assert tzinfo.utcoffset(dt) is not None
    # also stable tzname resolution
    assert isinstance(tzinfo.tzname(dt), str)
