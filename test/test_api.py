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

from __future__ import print_function
import re
import sys
import pytest
import requests
from unittest import mock

from os.path import dirname
from os.path import join

from apprise import Apprise
from apprise import AppriseAsset
from apprise import AppriseAttachment
from apprise import NotifyBase
from apprise import NotifyType
from apprise import NotifyFormat
from apprise import NotifyImageSize
from apprise import __version__
from apprise import URLBase
from apprise import PrivacyMode
from apprise.AppriseLocale import LazyTranslation

from apprise import common
from apprise.plugins import __load_matrix
from apprise.plugins import __reset_matrix
from apprise.utils import parse_list
import inspect

# Sending notifications requires the coroutines to be awaited, so we need to
# wrap the original function when mocking it.
import apprise.py3compat.asyncio as py3aio

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = join(dirname(__file__), 'var')


def test_apprise():
    """
    API: Apprise() object

    """
    def do_notify(server, *args, **kwargs):
        return server.notify(*args, **kwargs)

    apprise_test(do_notify)


def test_apprise_async():
    """
    API: Apprise() object asynchronous methods

    """
    def do_notify(server, *args, **kwargs):
        return py3aio.tosync(server.async_notify(*args, **kwargs))

    apprise_test(do_notify)


def apprise_test(do_notify):
    # Caling load matix a second time which is an internal function causes it
    # to skip over content already loaded into our matrix and thefore accesses
    # other if/else parts of the code that aren't otherwise called
    __load_matrix()

    a = Apprise()

    # no items
    assert len(a) == 0

    # Apprise object can also be directly tested with 'if' keyword
    # No entries results in a False response
    assert not a

    # Create an Asset object
    asset = AppriseAsset(theme='default')

    # We can load the device using our asset
    a = Apprise(asset=asset)

    # We can load our servers up front as well
    servers = [
        'faast://abcdefghijklmnop-abcdefg',
        'kodi://kodi.server.local',
    ]

    a = Apprise(servers=servers)

    # 2 servers loaded
    assert len(a) == 2

    # Apprise object can also be directly tested with 'if' keyword
    # At least one entry results in a True response
    assert a

    # We can retrieve our URLs this way:
    assert len(a.urls()) == 2

    # We can add another server
    assert a.add('mmosts://mattermost.server.local/'
                 '3ccdd113474722377935511fc85d3dd4') is True
    assert len(a) == 3

    # Try adding nothing but delimiters
    assert a.add(',, ,, , , , ,') is False

    # The number of servers added doesn't change
    assert len(a) == 3

    # We can pop an object off of our stack by it's indexed value:
    obj = a.pop(0)
    assert isinstance(obj, NotifyBase) is True
    assert len(a) == 2

    # We can retrieve elements from our list too by reference:
    assert isinstance(a[0].url(), str) is True

    # We can iterate over our list too:
    count = 0
    for o in a:
        assert isinstance(o.url(), str) is True
        count += 1
    # verify that we did indeed iterate over each element
    assert len(a) == count

    # We can empty our set
    a.clear()
    assert len(a) == 0

    # An invalid schema
    assert a.add('this is not a parseable url at all') is False
    assert len(a) == 0

    # An unsupported schema
    assert a.add(
        'invalid://we.just.do.not.support.this.plugin.type') is False
    assert len(a) == 0

    # A poorly formatted URL
    assert a.add('json://user:@@@:bad?no.good') is False
    assert len(a) == 0

    # Add a server with our asset we created earlier
    assert a.add('mmosts://mattermost.server.local/'
                 '3ccdd113474722377935511fc85d3dd4', asset=asset) is True

    # Clear our server listings again
    a.clear()

    # No servers to notify
    assert do_notify(a, title="my title", body="my body") is False

    class BadNotification(NotifyBase):
        def __init__(self, **kwargs):
            super(BadNotification, self).__init__(**kwargs)

            # We fail whenever we're initialized
            raise TypeError()

        def url(self, **kwargs):
            # Support URL
            return ''

        @staticmethod
        def parse_url(url, *args, **kwargs):
            # always parseable
            return NotifyBase.parse_url(url, verify_host=False)

    class GoodNotification(NotifyBase):
        def __init__(self, **kwargs):
            super(GoodNotification, self).__init__(
                notify_format=NotifyFormat.HTML, **kwargs)

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay
            return True

        @staticmethod
        def parse_url(url, *args, **kwargs):
            # always parseable
            return NotifyBase.parse_url(url, verify_host=False)

    # Store our bad notification in our schema map
    common.NOTIFY_SCHEMA_MAP['bad'] = BadNotification

    # Store our good notification in our schema map
    common.NOTIFY_SCHEMA_MAP['good'] = GoodNotification

    # Just to explain what is happening here, we would have parsed the
    # url properly but failed when we went to go and create an instance
    # of it.
    assert a.add('bad://localhost') is False
    assert len(a) == 0

    # We'll fail because we've got nothing to notify
    assert do_notify(
        a, title="my title", body="my body") is False

    # Clear our server listings again
    a.clear()

    assert a.add('good://localhost') is True
    assert len(a) == 1

    # Bad Notification Type is still allowed as it is presumed the user
    # know's what their doing
    assert do_notify(
        a, title="my title", body="my body", notify_type='bad') is True

    # No Title/Body combo's
    assert do_notify(a, title=None, body=None) is False
    assert do_notify(a, title='', body=None) is False
    assert do_notify(a, title=None, body='') is False

    assert do_notify(a, title=5, body=b'bytes') is False
    assert do_notify(a, title=b"bytes", body=10) is False
    assert do_notify(a, title=object(), body=b'bytes') is False
    assert do_notify(a, title=b"bytes", body=object()) is False

    # As long as one is present, we're good
    assert do_notify(a, title=None, body='present') is True
    assert do_notify(a, title='present', body=None) is True
    assert do_notify(a, title="present", body="present") is True

    # Send Attachment with success
    attach = join(TEST_VAR_DIR, 'apprise-test.gif')
    assert do_notify(
        a, body='body', title='test', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Send the attachment as an AppriseAttachment object
    assert do_notify(
        a, body='body', title='test', notify_type=NotifyType.INFO,
        attach=AppriseAttachment(attach)) is True

    # test a invalid attachment
    assert do_notify(
        a, body='body', title='test', notify_type=NotifyType.INFO,
        attach='invalid://') is False

    # Repeat the same tests above...
    # however do it by directly accessing the object; this grants the similar
    # results:
    assert do_notify(
        a[0], body='body', title='test', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Send the attachment as an AppriseAttachment object
    assert do_notify(
        a[0], body='body', title='test', notify_type=NotifyType.INFO,
        attach=AppriseAttachment(attach)) is True

    # test a invalid attachment
    assert do_notify(
        a[0], body='body', title='test', notify_type=NotifyType.INFO,
        attach='invalid://') is False

    class ThrowNotification(NotifyBase):
        def notify(self, **kwargs):
            # Pretend everything is okay
            raise TypeError()

        def url(self, **kwargs):
            # Support URL
            return ''

    class RuntimeNotification(NotifyBase):
        def notify(self, **kwargs):
            # Pretend everything is okay
            raise RuntimeError()

        def url(self, **kwargs):
            # Support URL
            return ''

    class FailNotification(NotifyBase):

        def notify(self, **kwargs):
            # Pretend everything is okay
            return False

        def url(self, **kwargs):
            # Support URL
            return ''

    # Store our bad notification in our schema map
    common.NOTIFY_SCHEMA_MAP['throw'] = ThrowNotification

    # Store our good notification in our schema map
    common.NOTIFY_SCHEMA_MAP['fail'] = FailNotification

    # Store our good notification in our schema map
    common.NOTIFY_SCHEMA_MAP['runtime'] = RuntimeNotification

    for async_mode in (True, False):
        # Create an Asset object
        asset = AppriseAsset(theme='default', async_mode=async_mode)

        # We can load the device using our asset
        a = Apprise(asset=asset)

        assert a.add('runtime://localhost') is True
        assert a.add('throw://localhost') is True
        assert a.add('fail://localhost') is True
        assert len(a) == 3

        # Test when our notify both throws an exception and or just
        # simply returns False
        assert do_notify(a, title="present", body="present") is False

    # Create a Notification that throws an unexected exception
    class ThrowInstantiateNotification(NotifyBase):
        def __init__(self, **kwargs):
            # Pretend everything is okay
            raise TypeError()

        def url(self, **kwargs):
            # Support URL
            return ''

    common.NOTIFY_SCHEMA_MAP['throw'] = ThrowInstantiateNotification

    # Reset our object
    a.clear()
    assert len(a) == 0

    # Test our socket details
    # rto = Socket Read Timeout
    # cto = Socket Connect Timeout
    plugin = a.instantiate('good://localhost?rto=5.1&cto=10')
    assert isinstance(plugin, NotifyBase)
    assert plugin.socket_connect_timeout == 10.0
    assert plugin.socket_read_timeout == 5.1

    plugin = a.instantiate('good://localhost?rto=invalid&cto=invalid')
    assert isinstance(plugin, NotifyBase)
    assert plugin.socket_connect_timeout == URLBase.socket_connect_timeout
    assert plugin.socket_read_timeout == URLBase.socket_read_timeout

    # Reset our object
    a.clear()
    assert len(a) == 0

    # Instantiate a bad object
    plugin = a.instantiate(object, tag="bad_object")
    assert plugin is None

    # Instantiate a good object
    plugin = a.instantiate('good://localhost', tag="good")
    assert isinstance(plugin, NotifyBase)

    # Test simple tagging inside of the object
    assert "good" in plugin
    assert "bad" not in plugin

    # the in (__contains__ override) is based on or'ed content; so although
    # 'bad' isn't tagged as being in the plugin, 'good' is, so the return
    # value of this is True
    assert ["bad", "good"] in plugin
    assert set(["bad", "good"]) in plugin
    assert ("bad", "good") in plugin

    # We an add already substatiated instances into our Apprise object
    a.add(plugin)
    assert len(a) == 1

    # We can add entries as a list too (to add more then one)
    a.add([plugin, plugin, plugin])
    assert len(a) == 4

    # Reset our object again
    a.clear()
    with pytest.raises(TypeError):
        a.instantiate('throw://localhost', suppress_exceptions=False)

    assert len(a) == 0

    assert a.instantiate(
        'throw://localhost', suppress_exceptions=True) is None
    assert len(a) == 0

    #
    # We rince and repeat the same tests as above, however we do them
    # using the dict version
    #

    # Reset our object
    a.clear()
    assert len(a) == 0

    # Instantiate a good object
    plugin = a.instantiate({
        'schema': 'good',
        'host': 'localhost'}, tag="good")
    assert isinstance(plugin, NotifyBase)

    # Test simple tagging inside of the object
    assert "good" in plugin
    assert "bad" not in plugin

    # the in (__contains__ override) is based on or'ed content; so although
    # 'bad' isn't tagged as being in the plugin, 'good' is, so the return
    # value of this is True
    assert ["bad", "good"] in plugin
    assert set(["bad", "good"]) in plugin
    assert ("bad", "good") in plugin

    # We an add already substatiated instances into our Apprise object
    a.add(plugin)
    assert len(a) == 1

    # We can add entries as a list too (to add more then one)
    a.add([plugin, plugin, plugin])
    assert len(a) == 4

    # Reset our object again
    a.clear()
    with pytest.raises(TypeError):
        a.instantiate({
            'schema': 'throw',
            'host': 'localhost'}, suppress_exceptions=False)

    assert len(a) == 0

    assert a.instantiate({
        'schema': 'throw',
        'host': 'localhost'}, suppress_exceptions=True) is None
    assert len(a) == 0


def test_apprise_pretty_print(tmpdir):
    """
    API: Apprise() Pretty Print tests

    """
    # Privacy Print
    # PrivacyMode.Secret always returns the same thing to avoid guessing
    assert URLBase.pprint(
        None, privacy=True, mode=PrivacyMode.Secret) == '****'
    assert URLBase.pprint(
        42, privacy=True, mode=PrivacyMode.Secret) == '****'
    assert URLBase.pprint(
        object, privacy=True, mode=PrivacyMode.Secret) == '****'
    assert URLBase.pprint(
        "", privacy=True, mode=PrivacyMode.Secret) == '****'
    assert URLBase.pprint(
        "a", privacy=True, mode=PrivacyMode.Secret) == '****'
    assert URLBase.pprint(
        "ab", privacy=True, mode=PrivacyMode.Secret) == '****'
    assert URLBase.pprint(
        "abcdefghijk", privacy=True, mode=PrivacyMode.Secret) == '****'

    # PrivacyMode.Outer
    assert URLBase.pprint(
        None, privacy=True, mode=PrivacyMode.Outer) == ''
    assert URLBase.pprint(
        42, privacy=True, mode=PrivacyMode.Outer) == ''
    assert URLBase.pprint(
        object, privacy=True, mode=PrivacyMode.Outer) == ''
    assert URLBase.pprint(
        "", privacy=True, mode=PrivacyMode.Outer) == ''
    assert URLBase.pprint(
        "a", privacy=True, mode=PrivacyMode.Outer) == 'a...a'
    assert URLBase.pprint(
        "ab", privacy=True, mode=PrivacyMode.Outer) == 'a...b'
    assert URLBase.pprint(
        "abcdefghijk", privacy=True, mode=PrivacyMode.Outer) == 'a...k'

    # PrivacyMode.Tail
    assert URLBase.pprint(
        None, privacy=True, mode=PrivacyMode.Tail) == ''
    assert URLBase.pprint(
        42, privacy=True, mode=PrivacyMode.Tail) == ''
    assert URLBase.pprint(
        object, privacy=True, mode=PrivacyMode.Tail) == ''
    assert URLBase.pprint(
        "", privacy=True, mode=PrivacyMode.Tail) == ''
    assert URLBase.pprint(
        "a", privacy=True, mode=PrivacyMode.Tail) == '...a'
    assert URLBase.pprint(
        "ab", privacy=True, mode=PrivacyMode.Tail) == '...ab'
    assert URLBase.pprint(
        "abcdefghijk", privacy=True, mode=PrivacyMode.Tail) == '...hijk'

    # Quoting settings
    assert URLBase.pprint(" ", privacy=False, safe='') == '%20'
    assert URLBase.pprint(" ", privacy=False, quote=False, safe='') == ' '


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_apprise_tagging(mock_post, mock_get):
    """
    API: Apprise() object tagging functionality

    """
    def do_notify(server, *args, **kwargs):
        return server.notify(*args, **kwargs)

    apprise_tagging_test(mock_post, mock_get, do_notify)


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_apprise_tagging_async(mock_post, mock_get):
    """
    API: Apprise() object tagging functionality asynchronous methods

    """
    def do_notify(server, *args, **kwargs):
        return py3aio.tosync(server.async_notify(*args, **kwargs))

    apprise_tagging_test(mock_post, mock_get, do_notify)


def apprise_tagging_test(mock_post, mock_get, do_notify):
    # A request
    robj = mock.Mock()
    setattr(robj, 'raw', mock.Mock())
    # Allow raw.read() calls
    robj.raw.read.return_value = ''
    robj.text = ''
    robj.content = ''
    mock_get.return_value = robj
    mock_post.return_value = robj

    # Simulate a successful notification
    mock_get.return_value.status_code = requests.codes.ok
    mock_post.return_value.status_code = requests.codes.ok

    # Create our object
    a = Apprise()

    # An invalid addition can't add the tag
    assert a.add('averyinvalidschema://localhost', tag='uhoh') is False
    assert a.add({
        'schema': 'averyinvalidschema',
        'host': 'localhost'}, tag='uhoh') is False

    # Add entry and assign it to a tag called 'awesome'
    assert a.add('json://localhost/path1/', tag='awesome') is True
    assert a.add({
        'schema': 'json',
        'host': 'localhost',
        'fullpath': '/path1/'}, tag='awesome') is True

    # Add another notification and assign it to a tag called 'awesome'
    # and another tag called 'local'
    assert a.add('json://localhost/path2/', tag=['mmost', 'awesome']) is True

    # notify the awesome tag; this would notify both services behind the
    # scenes
    assert do_notify(
        a, title="my title", body="my body", tag='awesome') is True

    # notify all of the tags
    assert do_notify(
        a, title="my title", body="my body", tag=['awesome', 'mmost']) is True

    # When we query against our loaded notifications for a tag that simply
    # isn't assigned to anything, we return None.  None (different then False)
    # tells us that we litterally had nothing to query.  We didn't fail...
    # but we also didn't do anything...
    assert do_notify(
        a, title="my title", body="my body", tag='missing') is None

    # Now to test the ability to and and/or notifications
    a = Apprise()

    # Add a tag by tuple
    assert a.add('json://localhost/tagA/', tag=("TagA", )) is True
    # Add 2 tags by string
    assert a.add('json://localhost/tagAB/', tag="TagA, TagB") is True
    # Add a tag using a set
    assert a.add('json://localhost/tagB/', tag=set(["TagB"])) is True
    # Add a tag by string (again)
    assert a.add('json://localhost/tagC/', tag="TagC") is True
    # Add 2 tags using a list
    assert a.add('json://localhost/tagCD/', tag=["TagC", "TagD"]) is True
    # Add a tag by string (again)
    assert a.add('json://localhost/tagD/', tag="TagD") is True
    # add a tag set by set (again)
    assert a.add('json://localhost/tagCDE/',
                 tag=set(["TagC", "TagD", "TagE"])) is True

    # Expression: TagC and TagD
    # Matches the following only:
    #   - json://localhost/tagCD/
    #   - json://localhost/tagCDE/
    assert do_notify(
        a, title="my title", body="my body", tag=[('TagC', 'TagD')]) is True

    # Expression: (TagY and TagZ) or TagX
    # Matches nothing, None is returned in this case
    assert do_notify(
        a, title="my title", body="my body",
        tag=[('TagY', 'TagZ'), 'TagX']) is None

    # Expression: (TagY and TagZ) or TagA
    # Matches the following only:
    #   - json://localhost/tagAB/
    assert do_notify(
        a, title="my title", body="my body",
        tag=[('TagY', 'TagZ'), 'TagA']) is True

    # Expression: (TagE and TagD) or TagB
    # Matches the following only:
    #   - json://localhost/tagCDE/
    #   - json://localhost/tagAB/
    #   - json://localhost/tagB/
    assert do_notify(
        a, title="my title", body="my body",
        tag=[('TagE', 'TagD'), 'TagB']) is True

    # Garbage Entries in tag field just get stripped out. the below
    # is the same as notifying no tags at all. Since we have not added
    # any entries that do not have tags (that we can match against)
    # we fail.  None is returned as a way of letting us know that we
    # had Notifications to notify, but since none of them matched our tag
    # none were notified.
    assert do_notify(
        a, title="my title", body="my body",
        tag=[(object, ), ]) is None


def test_apprise_schemas(tmpdir):
    """
    API: Apprise().schema() tests

    """
    # Caling load matix a second time which is an internal function causes it
    # to skip over content already loaded into our matrix and thefore accesses
    # other if/else parts of the code that aren't otherwise called
    __load_matrix()

    a = Apprise()

    # no items
    assert len(a) == 0

    class TextNotification(NotifyBase):
        # set our default notification format
        notify_format = NotifyFormat.TEXT

        # Garbage Protocol Entries
        protocol = None

        secure_protocol = (None, object)

    class HtmlNotification(NotifyBase):

        protocol = ('html', 'htm')

        secure_protocol = ('htmls', 'htms')

    class MarkDownNotification(NotifyBase):

        protocol = 'markdown'

        secure_protocol = 'markdowns'

    # Store our notifications into our schema map
    common.NOTIFY_SCHEMA_MAP['text'] = TextNotification
    common.NOTIFY_SCHEMA_MAP['html'] = HtmlNotification
    common.NOTIFY_SCHEMA_MAP['markdown'] = MarkDownNotification

    schemas = URLBase.schemas(TextNotification)
    assert isinstance(schemas, set) is True
    # We didn't define a protocol or secure protocol
    assert len(schemas) == 0

    schemas = URLBase.schemas(HtmlNotification)
    assert isinstance(schemas, set) is True
    assert len(schemas) == 4
    assert 'html' in schemas
    assert 'htm' in schemas
    assert 'htmls' in schemas
    assert 'htms' in schemas

    # Invalid entries do not disrupt schema calls
    for garbage in (object(), None, 42):
        schemas = URLBase.schemas(garbage)
        assert isinstance(schemas, set) is True
        assert len(schemas) == 0


def test_apprise_notify_formats(tmpdir):
    """
    API: Apprise() Input Formats tests

    """
    # Caling load matix a second time which is an internal function causes it
    # to skip over content already loaded into our matrix and thefore accesses
    # other if/else parts of the code that aren't otherwise called
    __load_matrix()

    a = Apprise()

    # no items
    assert len(a) == 0

    class TextNotification(NotifyBase):
        # set our default notification format
        notify_format = NotifyFormat.TEXT

        def __init__(self, **kwargs):
            super(TextNotification, self).__init__()

        def notify(self, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # Support URL
            return ''

    class HtmlNotification(NotifyBase):

        # set our default notification format
        notify_format = NotifyFormat.HTML

        def __init__(self, **kwargs):
            super(HtmlNotification, self).__init__()

        def notify(self, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # Support URL
            return ''

    class MarkDownNotification(NotifyBase):

        # set our default notification format
        notify_format = NotifyFormat.MARKDOWN

        def __init__(self, **kwargs):
            super(MarkDownNotification, self).__init__()

        def notify(self, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # Support URL
            return ''

    # Store our notifications into our schema map
    common.NOTIFY_SCHEMA_MAP['text'] = TextNotification
    common.NOTIFY_SCHEMA_MAP['html'] = HtmlNotification
    common.NOTIFY_SCHEMA_MAP['markdown'] = MarkDownNotification

    # Test Markdown; the above calls the markdown because our good://
    # defined plugin above was defined to default to HTML which triggers
    # a markdown to take place if the body_format specified on the notify
    # call
    assert a.add('html://localhost') is True
    assert a.add('html://another.server') is True
    assert a.add('html://and.another') is True
    assert a.add('text://localhost') is True
    assert a.add('text://another.server') is True
    assert a.add('text://and.another') is True
    assert a.add('markdown://localhost') is True
    assert a.add('markdown://another.server') is True
    assert a.add('markdown://and.another') is True

    assert len(a) == 9

    assert a.notify(
        title="markdown", body="## Testing Markdown",
        body_format=NotifyFormat.MARKDOWN) is True

    assert a.notify(
        title="text", body="Testing Text",
        body_format=NotifyFormat.TEXT) is True

    assert a.notify(
        title="html", body="<b>HTML</b>",
        body_format=NotifyFormat.HTML) is True


def test_apprise_asset(tmpdir):
    """
    API: AppriseAsset() object

    """
    a = AppriseAsset(theme='light')
    # Default theme
    assert a.theme == 'light'

    # Invalid kw handling
    with pytest.raises(AttributeError):
        AppriseAsset(invalid_kw='value')

    a = AppriseAsset(
        theme='dark',
        image_path_mask='/{THEME}/{TYPE}-{XY}{EXTENSION}',
        image_url_mask='http://localhost/{THEME}/{TYPE}-{XY}{EXTENSION}',
    )

    a.default_html_color = '#abcabc'

    assert a.color('invalid', tuple) == (171, 202, 188)
    assert a.color(NotifyType.INFO, tuple) == (58, 163, 227)

    assert a.color('invalid', int) == 11258556
    assert a.color(NotifyType.INFO, int) == 3843043

    assert a.color('invalid', None) == '#abcabc'
    assert a.color(NotifyType.INFO, None) == '#3AA3E3'
    # None is the default
    assert a.color(NotifyType.INFO) == '#3AA3E3'

    # Invalid Type
    with pytest.raises(ValueError):
        # The exception we expect since dict is not supported
        a.color(NotifyType.INFO, dict)

    assert a.image_url(NotifyType.INFO, NotifyImageSize.XY_256) == \
        'http://localhost/dark/info-256x256.png'

    assert a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=False) == '/dark/info-256x256.png'

    # This path doesn't exist so image_raw will fail (since we just
    # randompyl picked it for testing)
    assert a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is None

    assert a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is None

    # Create a new object (with our default settings)
    a = AppriseAsset()

    # Our default configuration can access our file
    assert a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is not None

    assert a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is not None

    # Create a temporary directory
    sub = tmpdir.mkdir("great.theme")

    # Write a file
    sub.join("{0}-{1}.png".format(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
    )).write("the content doesn't matter for testing.")

    # Create an asset that will reference our file we just created
    a = AppriseAsset(
        theme='great.theme',
        image_path_mask='%s/{THEME}/{TYPE}-{XY}.png' % dirname(sub.strpath),
    )

    # We'll be able to read file we just created
    assert a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is not None

    # We can retrieve the filename at this point even with must_exist set
    # to True
    assert a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is not None

    # Test case where we can't access the image file
    with mock.patch('builtins.open', side_effect=OSError()):
        assert a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is None

    # Our content is retrivable again
    assert a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is not None

    # Disable all image references
    a = AppriseAsset(image_path_mask=False, image_url_mask=False)

    # We always return none in these calls now
    assert a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is None
    assert a.image_url(NotifyType.INFO, NotifyImageSize.XY_256) is None
    assert a.image_path(NotifyType.INFO, NotifyImageSize.XY_256,
                        must_exist=False) is None
    assert a.image_path(NotifyType.INFO, NotifyImageSize.XY_256,
                        must_exist=True) is None

    # Test our default extension out
    a = AppriseAsset(
        image_path_mask='/{THEME}/{TYPE}-{XY}{EXTENSION}',
        image_url_mask='http://localhost/{THEME}/{TYPE}-{XY}{EXTENSION}',
        default_extension='.jpeg',
    )
    assert a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=False) == '/default/info-256x256.jpeg'

    assert a.image_url(
        NotifyType.INFO,
        NotifyImageSize.XY_256) == \
        'http://localhost/default/info-256x256.jpeg'

    # extension support
    assert a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_128,
        must_exist=False,
        extension='.ico') == '/default/info-128x128.ico'

    assert a.image_url(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        extension='.test') == \
        'http://localhost/default/info-256x256.test'


def test_apprise_disabled_plugins():
    """
    API: Apprise() Disabled Plugin States

    """
    # Reset our matrix
    __reset_matrix()

    class TestDisabled01Notification(NotifyBase):
        """
        This class is used to test a pre-disabled state
        """

        # Just flat out disable our service
        enabled = False

        # we'll use this as a key to make our service easier to find
        # in the next part of the testing
        service_name = 'na01'

        def url(self, **kwargs):
            # Support URL
            return ''

        def notify(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    common.NOTIFY_SCHEMA_MAP['na01'] = TestDisabled01Notification

    class TestDisabled02Notification(NotifyBase):
        """
        This class is used to test a post-disabled state
        """

        # we'll use this as a key to make our service easier to find
        # in the next part of the testing
        service_name = 'na02'

        def __init__(self, *args, **kwargs):
            super(TestDisabled02Notification, self).__init__(**kwargs)

            # enable state changes **AFTER** we initialize
            self.enabled = False

        def url(self, **kwargs):
            # Support URL
            return ''

        def notify(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    common.NOTIFY_SCHEMA_MAP['na02'] = TestDisabled02Notification

    # Create our Apprise instance
    a = Apprise()

    result = a.details(lang='ca-en', show_disabled=True)
    assert isinstance(result, dict)
    assert 'schemas' in result
    assert len(result['schemas']) == 2

    # our na01 is disabled right from the get-go
    entry = next((x for x in result['schemas']
                  if x['service_name'] == 'na01'), None)
    assert entry is not None
    assert entry['enabled'] is False

    plugin = a.instantiate('na01://localhost')
    # Object is just flat out disabled... nothing is instatiated
    assert plugin is None

    # our na02 isn't however until it's initialized; as a result
    # it get's returned in our result set
    entry = next((x for x in result['schemas']
                  if x['service_name'] == 'na02'), None)
    assert entry is not None
    assert entry['enabled'] is True

    plugin = a.instantiate('na02://localhost')
    # Object isn't disabled until the __init__() call.  But this is still
    # enough to not instantiate the object:
    assert plugin is None

    # If we choose to filter our disabled, we can't unfortunately filter those
    # that go disabled after instantiation, but we do filter out any that are
    # already known to not be enabled:
    result = a.details(lang='ca-en', show_disabled=False)
    assert isinstance(result, dict)
    assert 'schemas' in result
    assert len(result['schemas']) == 1

    # We'll add a good notification to our list
    class TesEnabled01Notification(NotifyBase):
        """
        This class is just a simple enabled one
        """

        # we'll use this as a key to make our service easier to find
        # in the next part of the testing
        service_name = 'good'

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    common.NOTIFY_SCHEMA_MAP['good'] = TesEnabled01Notification

    # The last thing we'll simulate is a case where the plugin is just
    # disabled at a later time long into it's life.  this is just to allow
    # administrators to stop the flow of their notifications for their own
    # given reasons.
    plugin = a.instantiate('good://localhost')
    assert isinstance(plugin, NotifyBase)

    # we'll toggle our state
    plugin.enabled = False

    # As a result, we can now no longer send a notification:
    assert plugin.notify("My Message") is False

    # As just a proof of how you can toggle the state back:
    plugin.enabled = True

    # our notifications will go okay now
    assert plugin.notify("My Message") is True

    # Reset our matrix
    __reset_matrix()
    __load_matrix()


def test_apprise_details():
    """
    API: Apprise() Details

    """
    # Reset our matrix
    __reset_matrix()

    # This is a made up class that is just used to verify
    class TestDetailNotification(NotifyBase):
        """
        This class is used to test various configurations supported
        """

        # Minimum requirements for a plugin to produce details
        service_name = 'Detail Testing'

        # The default simple (insecure) protocol (used by NotifyMail)
        protocol = 'details'

        # Set test_bool flag
        always_true = True
        always_false = False

        # Define object templates
        templates = (
            '{schema}://{host}',
            '{schema}://{host}:{port}',
            '{schema}://{user}@{host}:{port}',
            '{schema}://{user}:{pass}@{host}:{port}',
        )

        # Define our tokens; these are the minimum tokens required required to
        # be passed into this function (as arguments). The syntax appends any
        # previously defined in the base package and builds onto them
        template_tokens = dict(NotifyBase.template_tokens, **{
            'notype': {
                # Nothing defined is still valid
            },
            'regex_test01': {
                'name': _('RegexTest'),
                'type': 'string',
                'regex': r'[A-Z0-9]',
            },
            'regex_test02': {
                'name': _('RegexTest'),
                # Support regex options too
                'regex': (r'[A-Z0-9]', 'i'),
            },
            'regex_test03': {
                'name': _('RegexTest'),
                # Support regex option without a second option
                'regex': (r'[A-Z0-9]'),
            },
            'regex_test04': {
                # this entry would just end up getting removed
                'regex': None,
            },
            # List without delimiters (causes defaults to kick in)
            'mylistA': {
                'name': 'fruit',
                'type': 'list:string',
            },
            # A list with a delimiter list
            'mylistB': {
                'name': 'softdrinks',
                'type': 'list:string',
                'delim': ['|', '-'],
            },
        })

        template_args = dict(NotifyBase.template_args, **{
            # Test _exist_if logic
            'test_exists_if_01': {
                'name': 'Always False',
                'type': 'bool',
                # Provide a default
                'default': False,
                # Base the existance of this key/value entry on the lookup
                # of this class value at runtime. Hence:
                #     if not NotifyObject.always_false
                #         del this_entry
                #
                '_exists_if': 'always_false',
            },
            # Test _exist_if logic
            'test_exists_if_02': {
                'name': 'Always True',
                'type': 'bool',
                # Provide a default
                'default': False,
                # Base the existance of this key/value entry on the lookup
                # of this class value at runtime. Hence:
                #     if not NotifyObject.always_true
                #         del this_entry
                #
                '_exists_if': 'always_true',
            },
            # alias_of testing
            'test_alias_of': {
                'alias_of': 'mylistB',
                'delim': ('-', ' ')
            }
        })

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    # Store our good detail notification in our schema map
    common.NOTIFY_SCHEMA_MAP['details'] = TestDetailNotification

    # This is a made up class that is just used to verify
    class TestReq01Notification(NotifyBase):
        """
        This class is used to test various requirement configurations
        """

        # Set some requirements
        requirements = {
            'packages_required': [
                'cryptography <= 3.4',
                'ultrasync',
            ],
            'packages_recommended': 'django',
        }

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    common.NOTIFY_SCHEMA_MAP['req01'] = TestReq01Notification

    # This is a made up class that is just used to verify
    class TestReq02Notification(NotifyBase):
        """
        This class is used to test various requirement configurations
        """

        # Just not enabled at all
        enabled = False

        # Set some requirements
        requirements = {
            # None and/or [] is implied, but jsut to show that the code won't
            # crash if explicitly set this way:
            'packages_required': None,

            'packages_recommended': [
                'cryptography <= 3.4',
            ]
        }

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    common.NOTIFY_SCHEMA_MAP['req02'] = TestReq02Notification

    # This is a made up class that is just used to verify
    class TestReq03Notification(NotifyBase):
        """
        This class is used to test various requirement configurations
        """

        # Set some requirements
        requirements = {
            # We can over-ride the default details assigned to our plugin if
            # specified
            'details': _('some specified requirement details'),

            # We can set a string value as well (it does not have to be a list)
            'packages_recommended': 'cryptography <= 3.4'
        }

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    common.NOTIFY_SCHEMA_MAP['req03'] = TestReq03Notification

    # This is a made up class that is just used to verify
    class TestReq04Notification(NotifyBase):
        """
        This class is used to test a case where our requirements is fixed
        to a None
        """

        # This is the same as saying there are no requirements
        requirements = None

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    common.NOTIFY_SCHEMA_MAP['req04'] = TestReq04Notification

    # This is a made up class that is just used to verify
    class TestReq05Notification(NotifyBase):
        """
        This class is used to test a case where only packages_recommended
        is identified
        """

        requirements = {
            # We can set a string value as well (it does not have to be a list)
            'packages_recommended': 'cryptography <= 3.4'
        }

        def url(self, **kwargs):
            # Support URL
            return ''

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    common.NOTIFY_SCHEMA_MAP['req05'] = TestReq05Notification

    # Create our Apprise instance
    a = Apprise()

    # Dictionary response
    result = a.details()
    assert isinstance(result, dict)

    # Test different variations of our call
    result = a.details(lang='ca-fr')
    assert isinstance(result, dict)
    for entry in result['schemas']:
        # Verify our key does not exist because we did not ask for it
        assert 'enabled' not in entry
        assert 'requirements' not in entry

    result = a.details(lang='us-en', show_requirements=True)
    assert isinstance(result, dict)
    for entry in result['schemas']:
        # Verify our key does not exist because we did not ask for it
        assert 'enabled' not in entry

        # Requirements are set for display
        assert 'requirements' in entry
        assert 'details' in entry['requirements']
        assert 'packages_required' in entry['requirements']
        assert 'packages_recommended' in entry['requirements']
        assert isinstance(entry['requirements']['details'], str)
        assert isinstance(entry['requirements']['packages_required'], list)
        assert isinstance(entry['requirements']['packages_recommended'], list)

    result = a.details(lang='ca-en', show_disabled=True)
    assert isinstance(result, dict)
    for entry in result['schemas']:
        # Verify that our plugin state is available to us
        assert 'enabled' in entry
        assert isinstance(entry['enabled'], bool)

        # Verify our key does not exist because we did not ask for it
        assert 'requirements' not in entry

    result = a.details(
        lang='ca-fr', show_requirements=True, show_disabled=True)
    assert isinstance(result, dict)
    for entry in result['schemas']:
        # Plugin States are set for display
        assert 'enabled' in entry
        assert isinstance(entry['enabled'], bool)

        # Requirements are set for display
        assert 'requirements' in entry
        assert 'details' in entry['requirements']
        assert 'packages_required' in entry['requirements']
        assert 'packages_recommended' in entry['requirements']
        assert isinstance(entry['requirements']['details'], str)
        assert isinstance(entry['requirements']['packages_required'], list)
        assert isinstance(entry['requirements']['packages_recommended'], list)

    # Reset our matrix
    __reset_matrix()
    __load_matrix()


def test_apprise_details_plugin_verification():
    """
    API: Apprise() Details Plugin Verification

    """

    # Reset our matrix
    __reset_matrix()
    __load_matrix()

    a = Apprise()

    # Details object
    details = a.details()

    # Dictionary response
    assert isinstance(details, dict)

    # Details object with language defined:
    details = a.details(lang='en')

    # Dictionary response
    assert isinstance(details, dict)

    # Details object with unsupported language:
    details = a.details(lang='xx')

    # Dictionary response
    assert isinstance(details, dict)

    # Apprise version
    assert 'version' in details
    assert details.get('version') == __version__

    # Defined schemas identify each plugin
    assert 'schemas' in details
    assert isinstance(details.get('schemas'), list)

    # We have an entry per defined plugin
    assert 'asset' in details
    assert isinstance(details.get('asset'), dict)
    assert 'app_id' in details['asset']
    assert 'app_desc' in details['asset']
    assert 'default_extension' in details['asset']
    assert 'theme' in details['asset']
    assert 'image_path_mask' in details['asset']
    assert 'image_url_mask' in details['asset']
    assert 'image_url_logo' in details['asset']

    # Valid Type Regular Expression Checker
    # Case Sensitive and MUST match the following:
    is_valid_type_re = re.compile(
        r'((choice|list):)?(string|bool|int|float)')

    # match tokens found in templates so we can cross reference them back
    # to see if they have a matching argument
    template_token_re = re.compile(r'{([^}]+)}[^{]*?(?=$|{)')

    # Define acceptable map_to arguments that can be tied in with the
    # kwargs function definitions.
    valid_kwargs = set([
        # General Parameters
        'user', 'password', 'port', 'host', 'schema', 'fullpath',
        # NotifyBase parameters:
        'format', 'overflow',
        # URLBase parameters:
        'verify', 'cto', 'rto',
    ])

    # Valid Schema Entries:
    valid_schema_keys = (
        'name', 'private', 'required', 'type', 'values', 'min', 'max',
        'regex', 'default', 'list', 'delim', 'prefix', 'map_to', 'alias_of',
    )
    for entry in details['schemas']:

        # Track the map_to entries (if specified); We need to make sure that
        # these properly map back
        map_to_entries = set()

        # Track the alias_of entries
        map_to_aliases = set()

        # A Service Name MUST be defined
        assert 'service_name' in entry
        assert isinstance(
            entry['service_name'], (str, LazyTranslation))

        # Acquire our protocols
        protocols = parse_list(
            entry['protocols'], entry['secure_protocols'])

        # At least one schema/protocol MUST be defined
        assert len(protocols) > 0

        # our details
        assert 'details' in entry
        assert isinstance(entry['details'], dict)

        # All schema details should include args
        for section in ['kwargs', 'args', 'tokens']:
            assert section in entry['details']
            assert isinstance(entry['details'][section], dict)

            for key, arg in entry['details'][section].items():
                # Validate keys (case-sensitive)
                assert len([k for k in arg.keys()
                            if k not in valid_schema_keys]) == 0

                # Test our argument
                assert isinstance(arg, dict)

                if 'alias_of' not in arg:
                    # Minimum requirement of an argument
                    assert 'name' in arg
                    assert isinstance(arg['name'], str)

                    assert 'type' in arg
                    assert isinstance(arg['type'], str)
                    assert is_valid_type_re.match(arg['type']) is not None

                    if 'min' in arg:
                        assert arg['type'].endswith('float') \
                            or arg['type'].endswith('int')
                        assert isinstance(arg['min'], (int, float))

                        if 'max' in arg:
                            # If a min and max was specified, at least check
                            # to confirm the min is less then the max
                            assert arg['min'] < arg['max']

                    if 'max' in arg:
                        assert arg['type'].endswith('float') \
                            or arg['type'].endswith('int')
                        assert isinstance(arg['max'], (int, float))

                    if 'private' in arg:
                        assert isinstance(arg['private'], bool)

                    if 'required' in arg:
                        assert isinstance(arg['required'], bool)

                    if 'prefix' in arg:
                        assert isinstance(arg['prefix'], str)
                        if section == 'kwargs':
                            # The only acceptable prefix types for kwargs
                            assert arg['prefix'] in (':', '+', '-')

                    else:
                        # kwargs requires that the 'prefix' is defined
                        assert section != 'kwargs'

                    if 'map_to' in arg:
                        # must be a string
                        assert isinstance(arg['map_to'], str)
                        # Track our map_to object
                        map_to_entries.add(arg['map_to'])

                    else:
                        map_to_entries.add(key)

                    # Some verification
                    if arg['type'].startswith('choice'):

                        # choice:bool is redundant and should be swapped to
                        # just bool
                        assert not arg['type'].endswith('bool')

                        # Choices require that a values list is provided
                        assert 'values' in arg
                        assert isinstance(arg['values'], (list, tuple))
                        assert len(arg['values']) > 0

                        # Test default
                        if 'default' in arg:
                            # if a default is provided on a choice object,
                            # it better be in the list of values
                            assert arg['default'] in arg['values']

                    if arg['type'].startswith('bool'):
                        # Boolean choices are less restrictive but require a
                        # default value
                        assert 'default' in arg
                        assert isinstance(arg['default'], bool)

                    if 'regex' in arg:
                        # Regex must ALWAYS be in the format (regex, option)
                        assert isinstance(arg['regex'], (tuple, list))
                        assert len(arg['regex']) == 2
                        assert isinstance(arg['regex'][0], str)
                        assert arg['regex'][1] is None or isinstance(
                            arg['regex'][1], str)

                        # Compile the regular expression to verify that it is
                        # valid
                        try:
                            re.compile(arg['regex'][0])
                        except:
                            assert '{} is an invalid regex'\
                                .format(arg['regex'][0])

                        # Regex should always start and/or end with ^/$
                        assert re.match(
                            r'^\^.+?$', arg['regex'][0]) is not None
                        assert re.match(
                            r'^.+?\$$', arg['regex'][0]) is not None

                    if arg['type'].startswith('list'):
                        # Delimiters MUST be defined
                        assert 'delim' in arg
                        assert isinstance(arg['delim'], (list, tuple))
                        assert len(arg['delim']) > 0

                else:  # alias_of is in the object
                    # Ensure we're not already in the tokens section
                    # The alias_of object has no value here
                    assert section != 'tokens'

                    # must be a string
                    assert isinstance(
                        arg['alias_of'], (str, list, tuple, set))

                    aliases = [arg['alias_of']] \
                        if isinstance(arg['alias_of'], str) \
                        else arg['alias_of']

                    for alias_of in aliases:
                        # Track our alias_of object
                        map_to_aliases.add(alias_of)

                        # We can't be an alias_of ourselves
                        if key == alias_of:
                            # This is acceptable as long as we exist in the
                            # tokens table because that is truely what we map
                            # back to
                            assert key in entry['details']['tokens']

                        else:
                            # Throw the problem into an assert tag for
                            # debugging purposes... the mapping is not
                            # acceptable
                            assert key != alias_of

                        # alias_of always references back to tokens
                        assert \
                            alias_of in entry['details']['tokens'] or \
                            alias_of in entry['details']['args']

                        # Find a list directive in our tokens
                        t_match = entry['details']['tokens']\
                            .get(alias_of, {})\
                            .get('type', '').startswith('list')

                        a_match = entry['details']['args']\
                            .get(alias_of, {})\
                            .get('type', '').startswith('list')

                        if not (t_match or a_match):
                            # Ensure the only token we have is the alias_of
                            # hence record should look like as example):
                            # {
                            #    'token': {
                            #      'alias_of': 'apitoken',
                            #    },
                            # }
                            #
                            # Or if it can represent more then one entry; in
                            # this case, one must define a name (to define
                            # grouping).
                            # {
                            #    'token': {
                            #      'name': 'Tokens',
                            #      'alias_of': ('apitoken', 'webtoken'),
                            #    },
                            # }
                            if isinstance(arg['alias_of'], str):
                                assert len(entry['details'][section][key]) == 1
                            else:  # is tuple,list, or set
                                assert len(entry['details'][section][key]) == 2
                                # Must have a name defined to define grouping
                                assert 'name' in entry['details'][section][key]

                        else:
                            # We're a list, we allow up to 2 variables
                            # Obviously we have the alias_of entry; that's why
                            # were at this part of the code.  But we can
                            # additionally provide a 'delim' over-ride.
                            assert len(entry['details'][section][key]) <= 2
                            if len(entry['details'][section][key]) == 2:
                                # Verify that it is in fact the 'delim' tag
                                assert 'delim' in \
                                    entry['details'][section][key]
                                # If we do have a delim value set, it must be
                                # of a list/set/tuple type
                                assert isinstance(
                                    entry['details'][section][key]['delim'],
                                    (tuple, set, list),
                                )

        spec = inspect.getfullargspec(
            common.NOTIFY_SCHEMA_MAP[protocols[0]].__init__)

        function_args = \
            (set(parse_list(spec.varkw)) - set(['kwargs'])) \
            | (set(spec.args) - set(['self'])) | valid_kwargs

        # Iterate over our map_to_entries and make sure that everything
        # maps to a function argument
        for arg in map_to_entries:
            if arg not in function_args:
                # This print statement just makes the error easier to
                # troubleshoot
                raise AssertionError(
                    '{}.__init__() expects a {}=None entry according to '
                    'template configuration'
                    .format(
                        common.NOTIFY_SCHEMA_MAP[protocols[0]].__name__, arg))

        # Iterate over all of the function arguments and make sure that
        # it maps back to a key
        function_args -= valid_kwargs
        for arg in function_args:
            if arg not in map_to_entries:
                raise AssertionError(
                    '{}.__init__({}) found but not defined in the '
                    'template configuration'
                    .format(
                        common.NOTIFY_SCHEMA_MAP[protocols[0]].__name__, arg))

        # Iterate over our map_to_aliases and make sure they were defined in
        # either the as a token or arg
        for arg in map_to_aliases:
            assert arg in set(entry['details']['args'].keys()) \
                | set(entry['details']['tokens'].keys())

        # Template verification
        assert 'templates' in entry['details']
        assert isinstance(entry['details']['templates'], (set, tuple, list))

        # Iterate over our templates and parse our arguments
        for template in entry['details']['templates']:
            # Ensure we've properly opened and closed all of our tokens
            assert template.count('{') == template.count('}')

            expected_tokens = template.count('}')
            args = template_token_re.findall(template)
            assert expected_tokens == len(args)

            # Build a cross reference set of our current defined objects
            defined_tokens = set()
            for key, arg in entry['details']['tokens'].items():
                defined_tokens.add(key)
                if 'alias_of' in arg:
                    defined_tokens.add(arg['alias_of'])

            # We want to make sure all of our defined tokens have been
            # accounted for in at least one defined template
            for arg in args:
                assert arg in set(entry['details']['args'].keys()) \
                    | set(entry['details']['tokens'].keys())

                # The reverse of the above; make sure that each entry defined
                # in the template_tokens is accounted for in at least one of
                # the defined templates
                assert arg in defined_tokens


@mock.patch('requests.post')
@mock.patch('apprise.py3compat.asyncio.notify', wraps=py3aio.notify)
def test_apprise_async_mode(mock_async_notify, mock_post, tmpdir):
    """
    API: Apprise() async_mode tests

    """
    mock_post.return_value.status_code = requests.codes.ok

    # Define some servers
    servers = [
        'xml://localhost',
        'json://localhost',
    ]

    # Default Async Mode is to be enabled
    asset = AppriseAsset()
    assert asset.async_mode is True

    # Load our asset
    a = Apprise(asset=asset)

    # add our servers
    a.add(servers=servers)

    # 2 servers loaded
    assert len(a) == 2

    # Our servers should carry this flag
    for server in a:
        assert server.asset.async_mode is True

    # Send Notifications Asyncronously
    assert a.notify("async") is True

    # Verify our async code got executed
    assert mock_async_notify.call_count == 1
    mock_async_notify.reset_mock()

    # Provide an over-ride now
    asset = AppriseAsset(async_mode=False)
    assert asset.async_mode is False

    # Load our asset
    a = Apprise(asset=asset)

    # Verify our configuration kept
    assert a.asset.async_mode is False

    # add our servers
    a.add(servers=servers)

    # 2 servers loaded
    assert len(a) == 2

    # Our servers should carry this flag
    for server in a:
        assert server.asset.async_mode is False

    # Send Notifications Syncronously
    assert a.notify("sync") is True
    # Verify our async code got called
    assert mock_async_notify.call_count == 1
    mock_async_notify.reset_mock()

    # another way of looking a our false set asset configuration
    assert a[0].asset.async_mode is False
    assert a[1].asset.async_mode is False

    # Adjust 1 of the servers async_mode settings
    a[0].asset.async_mode = True
    assert a[0].asset.async_mode is True

    # They all share the same object, so this gets toggled too
    assert a[1].asset.async_mode is True

    # We'll just change this one
    a[1].asset = AppriseAsset(async_mode=False)
    assert a[0].asset.async_mode is True
    assert a[1].asset.async_mode is False

    # Send 1 Notification Syncronously, the other Asyncronously
    assert a.notify("a mixed batch") is True

    # Verify our async code got called
    assert mock_async_notify.call_count == 1
    mock_async_notify.reset_mock()


def test_notify_matrix_dynamic_importing(tmpdir):
    """
    API: Apprise() Notify Matrix Importing

    """

    # Make our new path valid
    suite = tmpdir.mkdir("apprise_notify_test_suite")
    suite.join("__init__.py").write('')

    module_name = 'badnotify'

    # Update our path to point to our new test suite
    sys.path.insert(0, str(suite))

    # Create a base area to work within
    base = suite.mkdir(module_name)
    base.join("__init__.py").write('')

    # Test no app_id
    base.join('NotifyBadFile1.py').write(
        """
class NotifyBadFile1:
    pass""")

    # No class of the same name
    base.join('NotifyBadFile2.py').write(
        """
class BadClassName:
    pass""")

    # Exception thrown
    base.join('NotifyBadFile3.py').write("""raise ImportError()""")

    # Utilizes a schema:// already occupied (as string)
    base.join('NotifyGoober.py').write(
        """
from apprise import NotifyBase
class NotifyGoober(NotifyBase):
    # This class tests the fact we have a new class name, but we're
    # trying to over-ride items previously used

    # The default simple (insecure) protocol (used by NotifyMail)
    protocol = ('mailto', 'goober')

    # The default secure protocol (used by NotifyMail)
    secure_protocol = 'mailtos'

    @staticmethod
    def parse_url(url, *args, **kwargs):
        # always parseable
        return ConfigBase.parse_url(url, verify_host=False)""")

    # Utilizes a schema:// already occupied (as tuple)
    base.join('NotifyBugger.py').write("""
from apprise import NotifyBase
class NotifyBugger(NotifyBase):
    # This class tests the fact we have a new class name, but we're
    # trying to over-ride items previously used

    # The default simple (insecure) protocol (used by NotifyMail), the other
    # isn't
    protocol = ('mailto', 'bugger-test' )

    # The default secure protocol (used by NotifyMail), the other isn't
    secure_protocol = ('mailtos', ['garbage'])

    @staticmethod
    def parse_url(url, *args, **kwargs):
        # always parseable
        return ConfigBase.parse_url(url, verify_host=False)""")

    __load_matrix(path=str(base), name=module_name)
