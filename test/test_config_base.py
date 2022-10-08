# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

import pytest
from apprise.AppriseAsset import AppriseAsset
from apprise.config.ConfigBase import ConfigBase
from apprise import ConfigFormat
from apprise import plugins
import yaml

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_config_base():
    """
    API: ConfigBase() object

    """

    # invalid types throw exceptions
    with pytest.raises(TypeError):
        ConfigBase(**{'format': 'invalid'})

    # Config format types are not the same as ConfigBase ones
    with pytest.raises(TypeError):
        ConfigBase(**{'format': 'markdown'})

    cb = ConfigBase(**{'format': 'yaml'})
    assert isinstance(cb, ConfigBase)

    cb = ConfigBase(**{'format': 'text'})
    assert isinstance(cb, ConfigBase)

    # Set encoding
    cb = ConfigBase(encoding='utf-8', format='text')
    assert isinstance(cb, ConfigBase)

    # read is not supported in the base object; only the children
    assert cb.read() is None

    # There are no servers loaded on a freshly created object
    assert len(cb.servers()) == 0

    # Unsupported URLs are not parsed
    assert ConfigBase.parse_url(url='invalid://') is None

    # Valid URL & Valid Format
    results = ConfigBase.parse_url(
        url='file://relative/path?format=yaml&encoding=latin-1')
    assert isinstance(results, dict)
    # These are moved into the root
    assert results.get('format') == 'yaml'
    assert results.get('encoding') == 'latin-1'

    # But they also exist in the qsd location
    assert isinstance(results.get('qsd'), dict)
    assert results['qsd'].get('encoding') == 'latin-1'
    assert results['qsd'].get('format') == 'yaml'

    # Valid URL & Invalid Format
    results = ConfigBase.parse_url(
        url='file://relative/path?format=invalid&encoding=latin-1')
    assert isinstance(results, dict)
    # Only encoding is moved into the root
    assert 'format' not in results
    assert results.get('encoding') == 'latin-1'

    # But they will always exist in the qsd location
    assert isinstance(results.get('qsd'), dict)
    assert results['qsd'].get('encoding') == 'latin-1'
    assert results['qsd'].get('format') == 'invalid'


def test_config_base_detect_config_format():
    """
    API: ConfigBase.detect_config_format

    """

    # Garbage Handling
    for garbage in (object(), None, 42):
        # A response is always correctly returned
        assert ConfigBase.detect_config_format(garbage) is None

    # Empty files are valid
    assert ConfigBase.detect_config_format('') is ConfigFormat.TEXT

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
    assert ConfigBase.detect_config_format('\n\n\n') is ConfigFormat.TEXT

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
        assert result == (list(), list())

    # Valid Text Configuration
    result = ConfigBase.config_parse("""
    # A comment line over top of a URL
    mailto://userb:pass@gmail.com
    """, asset=AppriseAsset())
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
    result = ConfigBase.config_parse("""
# if no version is specified then version 1 is presumed
version: 1

#
# Define your notification urls:
#
urls:
  - pbul://o.gn5kj6nfhv736I7jC3cj3QLRiyhgl98b
  - mailto://test:password@gmail.com
  - syslog://:
      - tag: devops, admin
    """, asset=AppriseAsset())

    # We expect to parse 3 entries from the above
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], list)
    assert len(result[0]) == 3
    assert len(result[0][0].tags) == 0
    assert len(result[0][1].tags) == 0
    assert len(result[0][2].tags) == 2

    # Test case where we pass in a bad format
    result = ConfigBase.config_parse("""
    ; A comment line over top of a URL
    mailto://userb:pass@gmail.com
    """, config_format='invalid-format')

    # This is not parseable despite the valid text
    assert isinstance(result, tuple)
    assert isinstance(result[0], list)
    assert len(result[0]) == 0

    result, _ = ConfigBase.config_parse("""
    ; A comment line over top of a URL
    mailto://userb:pass@gmail.com
    """, config_format=ConfigFormat.TEXT)

    # Parseable
    assert isinstance(result, list)
    assert len(result) == 1


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
        assert result == (list(), list())

    # Valid Configuration
    result, config = ConfigBase.config_parse_text("""
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
    include apprise.cfg     """, asset=AppriseAsset())

    # We expect to parse 3 entries from the above
    assert isinstance(result, list)
    assert isinstance(config, list)
    assert len(result) == 4
    assert len(result[0].tags) == 0

    # Our last element will have 2 tags associated with it
    assert len(result[-1].tags) == 2
    assert 'taga' in result[-1].tags
    assert 'tagb' in result[-1].tags

    assert len(config) == 2
    assert 'http://localhost:8080/notify/apprise' in config
    assert 'apprise.cfg' in config

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

    # There was 1 valid entry
    assert len(config) == 0

    # Test case where a comment is on it's own line with nothing else
    result, config = ConfigBase.config_parse_text("#")
    # We expect to parse 0 entries from the above
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0


def test_config_base_config_parse_yaml():
    """
    API: ConfigBase.config_parse_yaml object

    """

    # general reference used below
    asset = AppriseAsset()

    # Garbage Handling
    for garbage in (object(), None, '', 42):
        # A response is always correctly returned
        result = ConfigBase.config_parse_yaml(garbage)
        # response is a tuple...
        assert isinstance(result, tuple)
        # containing 2 items (plugins, config)
        assert len(result) == 2
        # In the case of garbage in, we get garbage out; both lists are empty
        assert result == (list(), list())

    # Invalid Version
    result, config = ConfigBase.config_parse_yaml("version: 2a", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid Syntax (throws a ScannerError)
    result, config = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

urls
""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Missing url token
    result, config = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # No urls defined
    result, config = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

urls:
""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid url defined
    result, config = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

# Invalid URL definition; yet the answer to life at the same time
urls: 43
""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid url/schema
    result, config = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

urls:
  - invalid://

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid url/schema
    result, config = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

urls:
  - invalid://:
    - a: b

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid url/schema
    result, config = ConfigBase.config_parse_yaml("""
# Include entry with nothing associated with it
include:

urls:
  - just some free text that isn't valid:
    - a garbage entry to go with it

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid url/schema
    result, config = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed
version: 1

urls:
  - not even a proper url

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Invalid url/schema
    result, config = ConfigBase.config_parse_yaml("""
urls:
  # a very invalid sns entry
  - sns://T1JJ3T3L2/
  - sns://:@/:
    - invalid: test
  - sns://T1JJ3T3L2/:
    - invalid: test

  # some strangeness
  -
    -
      - test

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # Valid Configuration
    result, config = ConfigBase.config_parse_yaml("""
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

""", asset=asset)

    # We expect to parse 4 entries from the above
    # The Ryver one is in a native form and the 4th one is invalid
    assert isinstance(result, list)
    assert len(result) == 4
    assert len(result[0].tags) == 0

    # There were 3 include entries
    assert len(config) == 3
    assert 'file:///absolute/path/' in config
    assert 'relative/path' in config
    assert 'http://test.com' in config

    # Valid Configuration
    result, config = ConfigBase.config_parse_yaml("""
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

""", asset=asset)

    # We expect to parse 6 entries from the above because the tgram:// entry
    # would have failed to be loaded
    assert isinstance(result, list)
    assert len(result) == 6
    assert len(result[0].tags) == 2

    # Our single line included
    assert len(config) == 1
    assert 'http://localhost:8080/notify/apprise' in config

    # Global Tags
    result, config = ConfigBase.config_parse_yaml("""
# Global Tags stacked as a list
tag:
  - admin
  - devops

urls:
  - json://localhost
  - dbus://
""", asset=asset)

    # We expect to parse 3 entries from the above
    assert isinstance(result, list)
    assert len(result) == 2

    # There were no include entries defined
    assert len(config) == 0

    # all entries will have our global tags defined in them
    for entry in result:
        assert 'admin' in entry.tags
        assert 'devops' in entry.tags

    # Global Tags
    result, config = ConfigBase.config_parse_yaml("""
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
""", asset=asset)

    # all entries will have our global tags defined in them
    for entry in result:
        assert 'admin' in entry.tags
        assert 'devops' in entry.tags

    # We expect to parse 3 entries from the above
    assert isinstance(result, list)
    assert len(result) == 2

    # json:// has 2 globals + 3 defined
    assert len(result[0].tags) == 5
    assert 'text' in result[0].tags

    # json:// has 2 globals + 2 defined
    assert len(result[1].tags) == 4
    assert 'list-tag' in result[1].tags

    # There were no include entries defined
    assert len(config) == 0

    # An invalid set of entries
    result, config = ConfigBase.config_parse_yaml("""
urls:
  # The following tags will get added to the global set
  - json://localhost:
    -
      -
        - entry
""", asset=asset)

    # We expect to parse 3 entries from the above
    assert isinstance(result, list)
    assert len(result) == 0

    # There were no include entries defined
    assert len(config) == 0

    # An asset we'll manipulate; set some system flags
    asset = AppriseAsset(_uid="abc123", _recursion=1)

    # Global Tags
    result, config = ConfigBase.config_parse_yaml("""
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
""", asset=asset)

    # We expect to parse 3 entries from the above
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

    # the theme was not updated and remains the same as it was
    assert asset.theme == AppriseAsset().theme

    # Empty string assignment
    assert isinstance(asset.image_url_mask, str) is True
    assert asset.image_url_mask == ""
    assert isinstance(asset.image_url_logo, str) is True
    assert asset.image_url_logo == ""

    # For on-lookers looking through this file; here is a perfectly formatted
    # YAML configuration file for your reference so you can see it without
    # all of the errors like the ones identified above
    result, config = ConfigBase.config_parse_yaml("""
# if no version is specified then version 1 is presumed. Thus this is a
# completely optional field. It's a good idea to just add this line because it
# will help with future ambiguity (if it ever occurs).
version: 1

# Define an Asset object if you wish (Optional)
asset:
  app_id: AppriseTest
  app_desc: Apprise Test Notifications
  app_url: http://nuxref.com

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
""", asset=asset)

    # okay, here is how we get our total based on the above (read top-down)
    # +1  json:// entry
    # +1  xml:// entry
    # +2  mailto:// entry to jason@hotmail.com and fred@live.com
    # +2  mailto:// entry to jeff@gmail.com and chris@yahoo.com
    # = 6
    assert len(result) == 6

    # all six entries will have our global tags defined in them
    for entry in result:
        assert 'admin' in entry.tags
        assert 'devops' in entry.tags

    # Entries can be directly accessed as they were added

    # our json:// had no additional tags added; so just the global ones
    # So just 2; admin and devops (these were already validated above in the
    # for loop
    assert len(result[0].tags) == 2

    # our xml:// object has 1 tag added (customer)
    assert len(result[1].tags) == 3
    assert 'customer' in result[1].tags

    # You get the idea, here is just a direct mapping to the remaining entries
    # in the same order they appear above
    assert len(result[2].tags) == 2
    assert len(result[3].tags) == 2

    assert len(result[4].tags) == 4
    assert 'customer' in result[4].tags
    assert 'jeff' in result[4].tags

    assert len(result[5].tags) == 4
    assert 'customer' in result[5].tags
    assert 'chris' in result[5].tags

    # There were no include entries defined
    assert len(config) == 0

    # Valid Configuration (multi inline configuration entries)
    result, config = ConfigBase.config_parse_yaml("""
# A configuration file that contains 2 includes separated by a comma and/or
# space:
include: http://localhost:8080/notify/apprise, http://localhost/apprise/cfg

""", asset=asset)

    # We will have loaded no results
    assert isinstance(result, list)
    assert len(result) == 0

    # But our two configuration files will be present:
    assert len(config) == 2
    assert 'http://localhost:8080/notify/apprise' in config
    assert 'http://localhost/apprise/cfg' in config

    # Valid Configuration (another way of specifying more then one include)
    result, config = ConfigBase.config_parse_yaml("""
# A configuration file that contains 4 includes on their own
# lines beneath the keyword `include`:
include:
   http://localhost:8080/notify/apprise
   http://localhost/apprise/cfg01
   http://localhost/apprise/cfg02
   http://localhost/apprise/cfg03

""", asset=asset)

    # We will have loaded no results
    assert isinstance(result, list)
    assert len(result) == 0

    # But our 4 configuration files will be present:
    assert len(config) == 4
    assert 'http://localhost:8080/notify/apprise' in config
    assert 'http://localhost/apprise/cfg01' in config
    assert 'http://localhost/apprise/cfg02' in config
    assert 'http://localhost/apprise/cfg03' in config

    # Test a configuration with an invalid schema with options
    result, config = ConfigBase.config_parse_yaml("""
    urls:
      - invalid://:
          tag: 'invalid'
          :name: 'Testing2'
          :body: 'test body2'
          :title: 'test title2'
""", asset=asset)

    # We will have loaded no results
    assert isinstance(result, list)
    assert len(result) == 0

    # Valid Configuration (we allow comma separated entries for
    # each defined bullet)
    result, config = ConfigBase.config_parse_yaml("""
# A configuration file that contains 4 includes on their own
# lines beneath the keyword `include`:
include:
   - http://localhost:8080/notify/apprise, http://localhost/apprise/cfg01
     http://localhost/apprise/cfg02
   - http://localhost/apprise/cfg03

""", asset=asset)

    # We will have loaded no results
    assert isinstance(result, list)
    assert len(result) == 0

    # But our 4 configuration files will be present:
    assert len(config) == 4
    assert 'http://localhost:8080/notify/apprise' in config
    assert 'http://localhost/apprise/cfg01' in config
    assert 'http://localhost/apprise/cfg02' in config
    assert 'http://localhost/apprise/cfg03' in config


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
    assert isinstance(yaml_result[0], plugins.NotifyEmail)
    assert isinstance(text_result[0], plugins.NotifyEmail)
    assert 'mytag' in text_result[0]
    assert 'mytag' in yaml_result[0]


# This test fails on CentOS 8.x so it was moved into it's own function
# so it could be bypassed. The ability to use lists in YAML files didn't
# appear to happen until later on; it's certainly not available in v3.12
# which was what shipped with CentOS v8 at the time.
@pytest.mark.skipif(int(yaml.__version__.split('.')[0]) <= 3,
                    reason="requires pyaml v4.x or higher.")
def test_config_base_config_parse_yaml_list():
    """
    API: ConfigBase.config_parse_yaml list parsing

    """

    # general reference used below
    asset = AppriseAsset()

    # Invalid url/schema
    result, config = ConfigBase.config_parse_yaml("""
# no lists... just no
urls: [milk, pumpkin pie, eggs, juice]

# Including by list is okay
include: [file:///absolute/path/, relative/path, http://test.com]

""", asset=asset)

    # Invalid data gets us an empty result set
    assert isinstance(result, list)
    assert len(result) == 0

    # There were 3 include entries
    assert len(config) == 3
    assert 'file:///absolute/path/' in config
    assert 'relative/path' in config
    assert 'http://test.com' in config
