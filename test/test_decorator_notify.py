# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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
from os.path import dirname
from os.path import join
from apprise.decorators import notify
from apprise import Apprise
from apprise import AppriseConfig
from apprise import AppriseAsset
from apprise import AppriseAttachment
from apprise import common

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

TEST_VAR_DIR = join(dirname(__file__), 'var')


def test_notify_simple_decoration():
    """decorators: Test simple @notify
    """

    # Verify our schema we're about to declare doesn't already exist
    # in our schema map:
    assert 'utiltest' not in common.NOTIFY_SCHEMA_MAP

    verify_obj = {}

    # Define a function here on the spot
    @notify(on="utiltest", name="Apprise @notify Decorator Testing")
    def my_inline_notify_wrapper(
            body, title, notify_type, attach, *args, **kwargs):

        # Populate our object we can use to validate
        verify_obj.update({
            'body': body,
            'title': title,
            'notify_type': notify_type,
            'attach': attach,
            'args': args,
            'kwargs': kwargs,
        })

    # Now after our hook being inline... it's been loaded
    assert 'utiltest' in common.NOTIFY_SCHEMA_MAP

    # Create ourselves an apprise object
    aobj = Apprise()

    assert aobj.add("utiltest://") is True

    assert len(verify_obj) == 0

    assert aobj.notify(
        "Hello World", title="My Title",
        # add some attachments too
        attach=(
            join(TEST_VAR_DIR, 'apprise-test.gif'),
            join(TEST_VAR_DIR, 'apprise-test.png'),
        )
    ) is True

    # Our content was populated after the notify() call
    assert len(verify_obj) > 0
    assert verify_obj['body'] == "Hello World"
    assert verify_obj['title'] == "My Title"
    assert verify_obj['notify_type'] == common.NotifyType.INFO
    assert isinstance(verify_obj['attach'], AppriseAttachment)
    assert len(verify_obj['attach']) == 2

    # No format was defined
    assert 'body_format' in verify_obj['kwargs']
    assert verify_obj['kwargs']['body_format'] is None

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert isinstance(verify_obj['kwargs'], dict)
    assert 'meta' in verify_obj['kwargs']
    assert isinstance(verify_obj['kwargs']['meta'], dict)
    assert len(verify_obj['kwargs']['meta']) == 4
    assert 'tag' in verify_obj['kwargs']['meta']

    assert 'asset' in verify_obj['kwargs']['meta']
    assert isinstance(verify_obj['kwargs']['meta']['asset'], AppriseAsset)

    assert verify_obj['kwargs']['meta']['schema'] == 'utiltest'
    assert verify_obj['kwargs']['meta']['url'] == 'utiltest://'

    # Reset our verify object (so it can be populated again)
    verify_obj = {}

    # We'll do another test now
    assert aobj.notify(
        "Hello Another World", title="My Other Title",
        body_format=common.NotifyFormat.HTML,
        notify_type=common.NotifyType.WARNING,
    ) is True

    # Our content was populated after the notify() call
    assert len(verify_obj) > 0
    assert verify_obj['body'] == "Hello Another World"
    assert verify_obj['title'] == "My Other Title"
    assert verify_obj['notify_type'] == common.NotifyType.WARNING
    # We have no attachments
    assert verify_obj['attach'] is None

    # No format was defined
    assert 'body_format' in verify_obj['kwargs']
    assert verify_obj['kwargs']['body_format'] == common.NotifyFormat.HTML

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert 'meta' in verify_obj['kwargs']
    assert isinstance(verify_obj['kwargs'], dict)
    assert len(verify_obj['kwargs']['meta']) == 4
    assert 'asset' in verify_obj['kwargs']['meta']
    assert isinstance(verify_obj['kwargs']['meta']['asset'], AppriseAsset)
    assert 'tag' in verify_obj['kwargs']['meta']
    assert isinstance(verify_obj['kwargs']['meta']['tag'], set)
    assert verify_obj['kwargs']['meta']['schema'] == 'utiltest'
    assert verify_obj['kwargs']['meta']['url'] == 'utiltest://'

    assert 'notexc' not in common.NOTIFY_SCHEMA_MAP

    # Define a function here on the spot
    @notify(on="notexc", name="Apprise @notify Exception Handling")
    def my_exception_inline_notify_wrapper(
            body, title, notify_type, attach, *args, **kwargs):
        raise ValueError("An exception was thrown!")

    assert 'notexc' in common.NOTIFY_SCHEMA_MAP

    # Create ourselves an apprise object
    aobj = Apprise()

    assert aobj.add("notexc://") is True

    # Isn't handled
    assert aobj.notify("Exceptions will be thrown!") is False

    # Tidy
    del common.NOTIFY_SCHEMA_MAP['utiltest']
    del common.NOTIFY_SCHEMA_MAP['notexc']


def test_notify_complex_decoration():
    """decorators: Test complex @notify
    """

    # Verify our schema we're about to declare doesn't already exist
    # in our schema map:
    assert 'utiltest' not in common.NOTIFY_SCHEMA_MAP

    verify_obj = {}

    # Define a function here on the spot
    @notify(on="utiltest://user@myhost:23?key=value&NOT=CaseSensitive",
            name="Apprise @notify Decorator Testing")
    def my_inline_notify_wrapper(
            body, title, notify_type, attach, *args, **kwargs):

        # Populate our object we can use to validate
        verify_obj.update({
            'body': body,
            'title': title,
            'notify_type': notify_type,
            'attach': attach,
            'args': args,
            'kwargs': kwargs,
        })

    # Now after our hook being inline... it's been loaded
    assert 'utiltest' in common.NOTIFY_SCHEMA_MAP

    # Create ourselves an apprise object
    aobj = Apprise()

    assert aobj.add("utiltest://") is True

    assert len(verify_obj) == 0

    assert aobj.notify(
        "Hello World", title="My Title",
        # add some attachments too
        attach=(
            join(TEST_VAR_DIR, 'apprise-test.gif'),
            join(TEST_VAR_DIR, 'apprise-test.png'),
        )
    ) is True

    # Our content was populated after the notify() call
    assert len(verify_obj) > 0
    assert verify_obj['body'] == "Hello World"
    assert verify_obj['title'] == "My Title"
    assert verify_obj['notify_type'] == common.NotifyType.INFO
    assert isinstance(verify_obj['attach'], AppriseAttachment)
    assert len(verify_obj['attach']) == 2

    # No format was defined
    assert 'body_format' in verify_obj['kwargs']
    assert verify_obj['kwargs']['body_format'] is None

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert isinstance(verify_obj['kwargs'], dict)
    assert 'meta' in verify_obj['kwargs']
    assert isinstance(verify_obj['kwargs']['meta'], dict)

    assert 'asset' in verify_obj['kwargs']['meta']
    assert isinstance(verify_obj['kwargs']['meta']['asset'], AppriseAsset)

    assert 'tag' in verify_obj['kwargs']['meta']
    assert isinstance(verify_obj['kwargs']['meta']['tag'], set)

    assert len(verify_obj['kwargs']['meta']) == 8
    # We carry all of our default arguments from the @notify's initialization
    assert verify_obj['kwargs']['meta']['schema'] == 'utiltest'

    # Case sensitivity is lost on key assignment and always made lowercase
    # however value case sensitivity is preseved.
    # this is the assembled URL based on the combined values of the default
    # parameters with values provided in the URL (user's configuration)
    assert verify_obj['kwargs']['meta']['url'].startswith(
        'utiltest://user@myhost:23?')

    # We don't know where they get placed, so just search for their match
    assert 'key=value' in verify_obj['kwargs']['meta']['url']
    assert 'not=CaseSensitive' in verify_obj['kwargs']['meta']['url']

    # Reset our verify object (so it can be populated again)
    verify_obj = {}

    # We'll do another test now
    aobj = Apprise()

    assert aobj.add("utiltest://customhost?key=new&key2=another") is True

    assert len(verify_obj) == 0

    # Send our notification
    assert aobj.notify("Hello World", title="My Title") is True

    # Our content was populated after the notify() call
    assert len(verify_obj) > 0
    assert verify_obj['body'] == "Hello World"
    assert verify_obj['title'] == "My Title"
    assert verify_obj['notify_type'] == common.NotifyType.INFO
    assert verify_obj['attach'] is None

    # No format was defined
    assert 'body_format' in verify_obj['kwargs']
    assert verify_obj['kwargs']['body_format'] is None

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert 'meta' in verify_obj['kwargs']
    assert isinstance(verify_obj['kwargs'], dict)
    assert len(verify_obj['kwargs']['meta']) == 8

    # We carry all of our default arguments from the @notify's initialization
    assert verify_obj['kwargs']['meta']['schema'] == 'utiltest'
    # Our host get's correctly over-ridden
    assert verify_obj['kwargs']['meta']['host'] == 'customhost'

    assert verify_obj['kwargs']['meta']['user'] == "user"
    assert verify_obj['kwargs']['meta']['port'] == 23
    assert isinstance(verify_obj['kwargs']['meta']['qsd'], dict)
    assert len(verify_obj['kwargs']['meta']['qsd']) == 3
    # our key is over-ridden
    assert verify_obj['kwargs']['meta']['qsd']['key'] == 'new'
    # Our other keys are preserved
    assert verify_obj['kwargs']['meta']['qsd']['not'] == 'CaseSensitive'
    # New keys are added
    assert verify_obj['kwargs']['meta']['qsd']['key2'] == 'another'

    # Case sensitivity is lost on key assignment and always made lowercase
    # however value case sensitivity is preseved.
    # this is the assembled URL based on the combined values of the default
    # parameters with values provided in the URL (user's configuration)
    assert verify_obj['kwargs']['meta']['url'].startswith(
        'utiltest://user@customhost:23?')

    # We don't know where they get placed, so just search for their match
    assert 'key=new' in verify_obj['kwargs']['meta']['url']
    assert 'not=CaseSensitive' in verify_obj['kwargs']['meta']['url']
    assert 'key2=another' in verify_obj['kwargs']['meta']['url']

    # Tidy
    del common.NOTIFY_SCHEMA_MAP['utiltest']


def test_notify_multi_instance_decoration(tmpdir):
    """decorators: Test multi-instance @notify
    """

    # Verify our schema we're about to declare doesn't already exist
    # in our schema map:
    assert 'multi' not in common.NOTIFY_SCHEMA_MAP

    verify_obj = []

    # Define a function here on the spot
    @notify(on="multi", name="Apprise @notify Decorator Testing")
    def my_inline_notify_wrapper(
            body, title, notify_type, attach, meta, *args, **kwargs):

        # Track what is added
        verify_obj.append({
            'body': body,
            'title': title,
            'notify_type': notify_type,
            'attach': attach,
            'meta': meta,
            'args': args,
            'kwargs': kwargs,
        })

    # Now after our hook being inline... it's been loaded
    assert 'multi' in common.NOTIFY_SCHEMA_MAP

    # Prepare our config
    t = tmpdir.mkdir("multi-test").join("apprise.yml")
    t.write("""urls:
    - multi://user1:pass@hostname
    - multi://user2:pass2@hostname
    """)

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # Create ourselves an apprise object
    aobj = Apprise()

    # Add our configuration
    aobj.add(ac)

    # The number of configuration files that exist
    assert len(ac) == 1

    # no notifications are loaded
    assert len(ac.servers()) == 2

    # Nothing stored yet in our object
    assert len(verify_obj) == 0

    assert aobj.notify("Hello World", title="My Title") is True

    assert len(verify_obj) == 2

    # Python 3.6 does not nessisarily return list in order
    # So let's be sure it's sorted by the user id field to make the remaining
    # checks on this test easy
    verify_obj = sorted(verify_obj, key=lambda x: x['meta']['user'])

    # Our content was populated after the notify() call
    obj = verify_obj[0]
    assert obj['body'] == "Hello World"
    assert obj['title'] == "My Title"
    assert obj['notify_type'] == common.NotifyType.INFO

    meta = obj['meta']
    assert isinstance(meta, dict)

    # No format was defined
    assert 'body_format' in obj['kwargs']
    assert obj['kwargs']['body_format'] is None

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert isinstance(obj['kwargs'], dict)

    assert 'asset' in meta
    assert isinstance(meta['asset'], AppriseAsset)

    assert 'tag' in meta
    assert isinstance(meta['tag'], set)

    assert len(meta) == 7
    # We carry all of our default arguments from the @notify's initialization
    assert meta['schema'] == 'multi'
    assert meta['host'] == 'hostname'
    assert meta['user'] == 'user1'
    assert meta['password'] == 'pass'

    # Verify our URL is correct
    assert meta['url'] == 'multi://user1:pass@hostname'

    #
    # Now verify our second URL saved correct
    #

    # Our content was populated after the notify() call
    obj = verify_obj[1]
    assert obj['body'] == "Hello World"
    assert obj['title'] == "My Title"
    assert obj['notify_type'] == common.NotifyType.INFO

    meta = obj['meta']
    assert isinstance(meta, dict)

    # No format was defined
    assert 'body_format' in obj['kwargs']
    assert obj['kwargs']['body_format'] is None

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert isinstance(obj['kwargs'], dict)

    assert 'asset' in meta
    assert isinstance(meta['asset'], AppriseAsset)

    assert 'tag' in meta
    assert isinstance(meta['tag'], set)

    assert len(meta) == 7
    # We carry all of our default arguments from the @notify's initialization
    assert meta['schema'] == 'multi'
    assert meta['host'] == 'hostname'
    assert meta['user'] == 'user2'
    assert meta['password'] == 'pass2'

    # Verify our URL is correct
    assert meta['url'] == 'multi://user2:pass2@hostname'

    # Tidy
    del common.NOTIFY_SCHEMA_MAP['multi']
