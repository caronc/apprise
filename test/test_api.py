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
import six
import pytest
import requests
import mock
from os import chmod
from os import getuid
from os.path import dirname

from apprise import Apprise
from apprise import AppriseAsset
from apprise import NotifyBase
from apprise import NotifyType
from apprise import NotifyFormat
from apprise import NotifyImageSize
from apprise import __version__

from apprise.plugins import SCHEMA_MAP
from apprise.plugins import __load_matrix
from apprise.plugins import __reset_matrix
from apprise.utils import parse_list
import inspect

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_apprise():
    """
    API: Apprise() object

    """
    # Caling load matix a second time which is an internal function causes it
    # to skip over content already loaded into our matrix and thefore accesses
    # other if/else parts of the code that aren't otherwise called
    __load_matrix()

    a = Apprise()

    # no items
    assert(len(a) == 0)

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
    assert(len(a) == 2)

    # We can retrieve our URLs this way:
    assert(len(a.urls()) == 2)

    # We can add another server
    assert(
        a.add('mmosts://mattermost.server.local/'
              '3ccdd113474722377935511fc85d3dd4') is True)
    assert(len(a) == 3)

    # We can pop an object off of our stack by it's indexed value:
    obj = a.pop(0)
    assert(isinstance(obj, NotifyBase) is True)
    assert(len(a) == 2)

    # We can retrieve elements from our list too by reference:
    assert(isinstance(a[0].url(), six.string_types) is True)

    # We can iterate over our list too:
    count = 0
    for o in a:
        assert(isinstance(o.url(), six.string_types) is True)
        count += 1
    # verify that we did indeed iterate over each element
    assert(len(a) == count)

    # We can empty our set
    a.clear()
    assert(len(a) == 0)

    # An invalid schema
    assert(
        a.add('this is not a parseable url at all') is False)
    assert(len(a) == 0)

    # An unsupported schema
    assert(
        a.add('invalid://we.just.do.not.support.this.plugin.type') is False)
    assert(len(a) == 0)

    # A poorly formatted URL
    assert(
        a.add('json://user:@@@:bad?no.good') is False)
    assert(len(a) == 0)

    # Add a server with our asset we created earlier
    assert(
        a.add('mmosts://mattermost.server.local/'
              '3ccdd113474722377935511fc85d3dd4', asset=asset) is True)

    # Clear our server listings again
    a.clear()

    # No servers to notify
    assert(a.notify(title="my title", body="my body") is False)

    class BadNotification(NotifyBase):
        def __init__(self, **kwargs):
            super(BadNotification, self).__init__(**kwargs)

            # We fail whenever we're initialized
            raise TypeError()

        def url(self):
            # Support URL
            return ''

    class GoodNotification(NotifyBase):
        def __init__(self, **kwargs):
            super(GoodNotification, self).__init__(
                notify_format=NotifyFormat.HTML, **kwargs)

        def url(self):
            # Support URL
            return ''

        def notify(self, **kwargs):
            # Pretend everything is okay
            return True

    # Store our bad notification in our schema map
    SCHEMA_MAP['bad'] = BadNotification

    # Store our good notification in our schema map
    SCHEMA_MAP['good'] = GoodNotification

    # Just to explain what is happening here, we would have parsed the
    # url properly but failed when we went to go and create an instance
    # of it.
    assert(a.add('bad://localhost') is False)
    assert(len(a) == 0)

    assert(a.add('good://localhost') is True)
    assert(len(a) == 1)

    # Bad Notification Type is still allowed as it is presumed the user
    # know's what their doing
    assert(a.notify(
        title="my title", body="my body", notify_type='bad') is True)

    # No Title/Body combo's
    assert(a.notify(title=None, body=None) is False)
    assert(a.notify(title='', body=None) is False)
    assert(a.notify(title=None, body='') is False)

    # As long as one is present, we're good
    assert(a.notify(title=None, body='present') is True)
    assert(a.notify(title='present', body=None) is True)
    assert(a.notify(title="present", body="present") is True)

    # Clear our server listings again
    a.clear()

    class ThrowNotification(NotifyBase):
        def notify(self, **kwargs):
            # Pretend everything is okay
            raise TypeError()

        def url(self):
            # Support URL
            return ''

    class RuntimeNotification(NotifyBase):
        def notify(self, **kwargs):
            # Pretend everything is okay
            raise RuntimeError()

        def url(self):
            # Support URL
            return ''

    class FailNotification(NotifyBase):

        def notify(self, **kwargs):
            # Pretend everything is okay
            return False

        def url(self):
            # Support URL
            return ''

    # Store our bad notification in our schema map
    SCHEMA_MAP['throw'] = ThrowNotification

    # Store our good notification in our schema map
    SCHEMA_MAP['fail'] = FailNotification

    # Store our good notification in our schema map
    SCHEMA_MAP['runtime'] = RuntimeNotification

    assert(a.add('runtime://localhost') is True)
    assert(a.add('throw://localhost') is True)
    assert(a.add('fail://localhost') is True)
    assert(len(a) == 3)

    # Test when our notify both throws an exception and or just
    # simply returns False
    assert(a.notify(title="present", body="present") is False)

    # Create a Notification that throws an unexected exception
    class ThrowInstantiateNotification(NotifyBase):
        def __init__(self, **kwargs):
            # Pretend everything is okay
            raise TypeError()

        def url(self):
            # Support URL
            return ''

    SCHEMA_MAP['throw'] = ThrowInstantiateNotification

    # Reset our object
    a.clear()
    assert(len(a) == 0)

    # Instantiate a bad object
    plugin = a.instantiate(object, tag="bad_object")
    assert plugin is None

    # Instantiate a good object
    plugin = a.instantiate('good://localhost', tag="good")
    assert(isinstance(plugin, NotifyBase))

    # Test simple tagging inside of the object
    assert("good" in plugin)
    assert("bad" not in plugin)

    # the in (__contains__ override) is based on or'ed content; so although
    # 'bad' isn't tagged as being in the plugin, 'good' is, so the return
    # value of this is True
    assert(["bad", "good"] in plugin)
    assert(set(["bad", "good"]) in plugin)
    assert(("bad", "good") in plugin)

    # We an add already substatiated instances into our Apprise object
    a.add(plugin)
    assert(len(a) == 1)

    # We can add entries as a list too (to add more then one)
    a.add([plugin, plugin, plugin])
    assert(len(a) == 4)

    # Reset our object again
    a.clear()
    try:
        a.instantiate('throw://localhost', suppress_exceptions=False)
        assert(False)

    except TypeError:
        assert(True)
    assert(len(a) == 0)

    assert(a.instantiate(
        'throw://localhost', suppress_exceptions=True) is None)
    assert(len(a) == 0)

    #
    # We rince and repeat the same tests as above, however we do them
    # using the dict version
    #

    # Reset our object
    a.clear()
    assert(len(a) == 0)

    # Instantiate a good object
    plugin = a.instantiate({
        'schema': 'good',
        'host': 'localhost'}, tag="good")
    assert(isinstance(plugin, NotifyBase))

    # Test simple tagging inside of the object
    assert("good" in plugin)
    assert("bad" not in plugin)

    # the in (__contains__ override) is based on or'ed content; so although
    # 'bad' isn't tagged as being in the plugin, 'good' is, so the return
    # value of this is True
    assert(["bad", "good"] in plugin)
    assert(set(["bad", "good"]) in plugin)
    assert(("bad", "good") in plugin)

    # We an add already substatiated instances into our Apprise object
    a.add(plugin)
    assert(len(a) == 1)

    # We can add entries as a list too (to add more then one)
    a.add([plugin, plugin, plugin])
    assert(len(a) == 4)

    # Reset our object again
    a.clear()
    try:
        a.instantiate({
            'schema': 'throw',
            'host': 'localhost'}, suppress_exceptions=False)
        assert(False)

    except TypeError:
        assert(True)
    assert(len(a) == 0)

    assert(a.instantiate({
        'schema': 'throw',
        'host': 'localhost'}, suppress_exceptions=True) is None)
    assert(len(a) == 0)


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_apprise_tagging(mock_post, mock_get):
    """
    API: Apprise() object tagging functionality

    """

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
    assert(a.add('averyinvalidschema://localhost', tag='uhoh') is False)
    assert(a.add({
        'schema': 'averyinvalidschema',
        'host': 'localhost'}, tag='uhoh') is False)

    # Add entry and assign it to a tag called 'awesome'
    assert(a.add('json://localhost/path1/', tag='awesome') is True)
    assert(a.add({
        'schema': 'json',
        'host': 'localhost',
        'fullpath': '/path1/'}, tag='awesome') is True)

    # Add another notification and assign it to a tag called 'awesome'
    # and another tag called 'local'
    assert(a.add('json://localhost/path2/', tag=['mmost', 'awesome']) is True)

    # notify the awesome tag; this would notify both services behind the
    # scenes
    assert(a.notify(title="my title", body="my body", tag='awesome') is True)

    # notify all of the tags
    assert(a.notify(
        title="my title", body="my body", tag=['awesome', 'mmost']) is True)

    # there is nothing to notify using tags 'missing'. However we intentionally
    # don't fail as there is value in identifying a tag that simply have
    # nothing to notify from while the object itself contains items
    assert(a.notify(
        title="my title", body="my body", tag='missing') is True)

    # Now to test the ability to and and/or notifications
    a = Apprise()

    # Add a tag by tuple
    assert(a.add('json://localhost/tagA/', tag=("TagA", )) is True)
    # Add 2 tags by string
    assert(a.add('json://localhost/tagAB/', tag="TagA, TagB") is True)
    # Add a tag using a set
    assert(a.add('json://localhost/tagB/', tag=set(["TagB"])) is True)
    # Add a tag by string (again)
    assert(a.add('json://localhost/tagC/', tag="TagC") is True)
    # Add 2 tags using a list
    assert(a.add('json://localhost/tagCD/', tag=["TagC", "TagD"]) is True)
    # Add a tag by string (again)
    assert(a.add('json://localhost/tagD/', tag="TagD") is True)
    # add a tag set by set (again)
    assert(a.add('json://localhost/tagCDE/',
           tag=set(["TagC", "TagD", "TagE"])) is True)

    # Expression: TagC and TagD
    # Matches the following only:
    #   - json://localhost/tagCD/
    #   - json://localhost/tagCDE/
    assert(a.notify(
        title="my title", body="my body", tag=[('TagC', 'TagD')]) is True)

    # Expression: (TagY and TagZ) or TagX
    # Matches nothing
    assert(a.notify(
        title="my title", body="my body",
        tag=[('TagY', 'TagZ'), 'TagX']) is True)

    # Expression: (TagY and TagZ) or TagA
    # Matches the following only:
    #   - json://localhost/tagAB/
    assert(a.notify(
        title="my title", body="my body",
        tag=[('TagY', 'TagZ'), 'TagA']) is True)

    # Expression: (TagE and TagD) or TagB
    # Matches the following only:
    #   - json://localhost/tagCDE/
    #   - json://localhost/tagAB/
    #   - json://localhost/tagB/
    assert(a.notify(
        title="my title", body="my body",
        tag=[('TagE', 'TagD'), 'TagB']) is True)

    # Garbage Entries
    assert(a.notify(
        title="my title", body="my body",
        tag=[(object, ), ]) is True)


def test_apprise_notify_formats(tmpdir):
    """
    API: Apprise() TextFormat tests

    """
    # Caling load matix a second time which is an internal function causes it
    # to skip over content already loaded into our matrix and thefore accesses
    # other if/else parts of the code that aren't otherwise called
    __load_matrix()

    a = Apprise()

    # no items
    assert(len(a) == 0)

    class TextNotification(NotifyBase):
        # set our default notification format
        notify_format = NotifyFormat.TEXT

        def __init__(self, **kwargs):
            super(TextNotification, self).__init__()

        def notify(self, **kwargs):
            # Pretend everything is okay
            return True

        def url(self):
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

        def url(self):
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

        def url(self):
            # Support URL
            return ''

    # Store our notifications into our schema map
    SCHEMA_MAP['text'] = TextNotification
    SCHEMA_MAP['html'] = HtmlNotification
    SCHEMA_MAP['markdown'] = MarkDownNotification

    # Test Markdown; the above calls the markdown because our good://
    # defined plugin above was defined to default to HTML which triggers
    # a markdown to take place if the body_format specified on the notify
    # call
    assert(a.add('html://localhost') is True)
    assert(a.add('html://another.server') is True)
    assert(a.add('html://and.another') is True)
    assert(a.add('text://localhost') is True)
    assert(a.add('text://another.server') is True)
    assert(a.add('text://and.another') is True)
    assert(a.add('markdown://localhost') is True)
    assert(a.add('markdown://another.server') is True)
    assert(a.add('markdown://and.another') is True)

    assert(len(a) == 9)

    assert(a.notify(title="markdown", body="## Testing Markdown",
           body_format=NotifyFormat.MARKDOWN) is True)

    assert(a.notify(title="text", body="Testing Text",
           body_format=NotifyFormat.TEXT) is True)

    assert(a.notify(title="html", body="<b>HTML</b>",
           body_format=NotifyFormat.HTML) is True)


def test_apprise_asset(tmpdir):
    """
    API: AppriseAsset() object

    """
    a = AppriseAsset(theme=None)
    # Default theme
    assert(a.theme == 'default')

    a = AppriseAsset(
        theme='dark',
        image_path_mask='/{THEME}/{TYPE}-{XY}{EXTENSION}',
        image_url_mask='http://localhost/{THEME}/{TYPE}-{XY}{EXTENSION}',
    )

    a.default_html_color = '#abcabc'
    a.html_notify_map[NotifyType.INFO] = '#aaaaaa'

    assert(a.color('invalid', tuple) == (171, 202, 188))
    assert(a.color(NotifyType.INFO, tuple) == (170, 170, 170))

    assert(a.color('invalid', int) == 11258556)
    assert(a.color(NotifyType.INFO, int) == 11184810)

    assert(a.color('invalid', None) == '#abcabc')
    assert(a.color(NotifyType.INFO, None) == '#aaaaaa')
    # None is the default
    assert(a.color(NotifyType.INFO) == '#aaaaaa')

    # Invalid Type
    try:
        a.color(NotifyType.INFO, dict)
        # We should not get here (exception should be thrown)
        assert(False)

    except ValueError:
        # The exception we expect since dict is not supported
        assert(True)

    except Exception:
        # Any other exception is not good
        assert(False)

    assert(a.image_url(NotifyType.INFO, NotifyImageSize.XY_256) ==
           'http://localhost/dark/info-256x256.png')

    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=False) == '/dark/info-256x256.png')

    # This path doesn't exist so image_raw will fail (since we just
    # randompyl picked it for testing)
    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is None)

    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is None)

    # Create a new object (with our default settings)
    a = AppriseAsset()

    # Our default configuration can access our file
    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is not None)

    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is not None)

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
    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is not None)

    # We can retrieve the filename at this point even with must_exist set
    # to True
    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is not None)

    # If we make the file un-readable however, we won't be able to read it
    # This test is just showing that we won't throw an exception
    if getuid() == 0:
        # Root always over-rides 0x000 permission settings making the below
        # tests futile
        pytest.skip('The Root user can not run file permission tests.')

    chmod(dirname(sub.strpath), 0o000)
    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is None)

    # Our path doesn't exist anymore using this logic
    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is None)

    # Return our permission so we don't have any problems with our cleanup
    chmod(dirname(sub.strpath), 0o700)

    # Our content is retrivable again
    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is not None)

    # our file path is accessible again too
    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is not None)

    # We do the same test, but set the permission on the file
    chmod(a.image_path(NotifyType.INFO, NotifyImageSize.XY_256), 0o000)

    # our path will still exist in this case
    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=True) is not None)

    # but we will not be able to open it
    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is None)

    # Restore our permissions
    chmod(a.image_path(NotifyType.INFO, NotifyImageSize.XY_256), 0o640)

    # Disable all image references
    a = AppriseAsset(image_path_mask=False, image_url_mask=False)

    # We always return none in these calls now
    assert(a.image_raw(NotifyType.INFO, NotifyImageSize.XY_256) is None)
    assert(a.image_url(NotifyType.INFO, NotifyImageSize.XY_256) is None)
    assert(a.image_path(NotifyType.INFO, NotifyImageSize.XY_256,
           must_exist=False) is None)
    assert(a.image_path(NotifyType.INFO, NotifyImageSize.XY_256,
           must_exist=True) is None)

    # Test our default extension out
    a = AppriseAsset(
        image_path_mask='/{THEME}/{TYPE}-{XY}{EXTENSION}',
        image_url_mask='http://localhost/{THEME}/{TYPE}-{XY}{EXTENSION}',
        default_extension='.jpeg',
    )
    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        must_exist=False) == '/default/info-256x256.jpeg')

    assert(a.image_url(
        NotifyType.INFO,
        NotifyImageSize.XY_256) == 'http://localhost/'
                                   'default/info-256x256.jpeg')

    # extension support
    assert(a.image_path(
        NotifyType.INFO,
        NotifyImageSize.XY_128,
        must_exist=False,
        extension='.ico') == '/default/info-128x128.ico')

    assert(a.image_url(
        NotifyType.INFO,
        NotifyImageSize.XY_256,
        extension='.test') == 'http://localhost/'
                              'default/info-256x256.test')


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
        })

        def url(self):
            # Support URL
            return ''

        def notify(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    # Store our good detail notification in our schema map
    SCHEMA_MAP['details'] = TestDetailNotification

    # Create our Apprise instance
    a = Apprise()

    # Dictionary response
    assert isinstance(a.details(), dict)

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
        # URL prepared kwargs
        'user', 'password', 'port', 'host', 'schema', 'fullpath',
        # URLBase and NotifyBase args:
        'verify', 'format', 'overflow',
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
        assert isinstance(entry['service_name'], six.string_types)

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
                    assert isinstance(arg['name'], six.string_types)

                    assert 'type' in arg
                    assert isinstance(arg['type'], six.string_types)
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
                        assert isinstance(arg['prefix'], six.string_types)
                        if section == 'kwargs':
                            # The only acceptable prefix types for kwargs
                            assert arg['prefix'] in ('+', '-')

                    else:
                        # kwargs requires that the 'prefix' is defined
                        assert section != 'kwargs'

                    if 'map_to' in arg:
                        # must be a string
                        assert isinstance(arg['map_to'], six.string_types)
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
                        assert isinstance(arg['regex'][0], six.string_types)
                        assert arg['regex'][1] is None or isinstance(
                            arg['regex'][1], six.string_types)

                        # Compile the regular expression to verify that it is
                        # valid
                        try:
                            re.compile(arg['regex'][0])
                        except:
                            assert '{} is an invalid regex'\
                                .format(arg['regex'][0])

                        # Regex should never start and/or end with ^/$; leave
                        # that up to the user making use of the regex instead
                        assert re.match(r'^[()\s]*\^', arg['regex'][0]) is None
                        assert re.match(r'[()\s$]*\$', arg['regex'][0]) is None

                    if arg['type'].startswith('list'):
                        # Delimiters MUST be defined
                        assert 'delim' in arg
                        assert isinstance(arg['delim'], (list, tuple))
                        assert len(arg['delim']) > 0

                else:  # alias_of is in the object
                    # must be a string
                    assert isinstance(arg['alias_of'], six.string_types)
                    # Track our alias_of object
                    map_to_aliases.add(arg['alias_of'])
                    # We should never map to ourselves
                    assert arg['alias_of'] != key
                    # 2 entries (name, and alias_of only!)
                    assert len(entry['details'][section][key]) == 1

        # inspect our object
        spec = inspect.getargspec(SCHEMA_MAP[protocols[0]].__init__)

        function_args = \
            (set(parse_list(spec.keywords)) - set(['kwargs'])) \
            | (set(spec.args) - set(['self'])) | valid_kwargs

        # Iterate over our map_to_entries and make sure that everything
        # maps to a function argument
        for arg in map_to_entries:
            if arg not in function_args:
                # This print statement just makes the error easier to
                # troubleshoot
                print('{}:// template/arg/func reference missing error.'
                      .format(protocols[0]))
            assert arg in function_args

        # Iterate over all of the function arguments and make sure that
        # it maps back to a key
        function_args -= valid_kwargs
        for arg in function_args:
            if arg not in map_to_entries:
                # This print statement just makes the error easier to
                # troubleshoot
                print('{}:// template/func/arg reference missing error.'
                      .format(protocols[0]))
            assert arg in map_to_entries

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
class NotifyBadFile1(object):
    pass""")

    # No class of the same name
    base.join('NotifyBadFile2.py').write(
        """
class BadClassName(object):
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
    protocol = 'mailto'

    # The default secure protocol (used by NotifyMail)
    secure_protocol = 'mailtos'""")

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
    secure_protocol = ('mailtos', 'bugger-tests')""")

    __load_matrix(path=str(base), name=module_name)
