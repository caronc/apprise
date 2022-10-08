# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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
import re
import os
import requests
from unittest import mock

from json import dumps
from random import choice
from string import ascii_uppercase as str_alpha
from string import digits as str_num

from apprise import plugins
from apprise import NotifyType
from apprise import Apprise
from apprise import AppriseAsset
from apprise import AppriseAttachment
from apprise.common import OverflowMode

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


class AppriseURLTester:

    # Some exception handling we'll use
    req_exceptions = (
        requests.ConnectionError(
            0, 'requests.ConnectionError() not handled'),
        requests.RequestException(
            0, 'requests.RequestException() not handled'),
        requests.HTTPError(
            0, 'requests.HTTPError() not handled'),
        requests.ReadTimeout(
            0, 'requests.ReadTimeout() not handled'),
        requests.TooManyRedirects(
            0, 'requests.TooManyRedirects() not handled'),
    )

    # Attachment Testing Directory
    __test_var_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'var')

    # Our URLs we'll test against
    __tests = []

    # Define how many characters exist per line
    row = 80

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    def __init__(self, tests=None, *args, **kwargs):
        """
        Our initialization
        """
        # Create a large body and title with random data
        self.body = ''.join(
            choice(str_alpha + str_num + ' ') for _ in range(self.body_len))
        self.body = '\r\n'.join(
            [self.body[i: i + self.row]
             for i in range(0, len(self.body), self.row)])

        # Create our title using random data
        self.title = ''.join(
            choice(str_alpha + str_num) for _ in range(self.title_len))

        if tests:
            self.__tests = tests

    def add(self, url, meta):
        """
        Adds a test suite to our object
        """
        self.__tests.append({
            'url': url,
            'meta': meta,
        })

    def run_all(self):
        """
        Run all of our tests
        """
        # iterate over our dictionary and test it out
        for (url, meta) in self.__tests:
            self.run(url, meta)

    @mock.patch('requests.get')
    @mock.patch('requests.post')
    def run(self, url, meta, mock_post, mock_get):
        """
        Run a specific test
        """
        # Disable Throttling to speed testing
        plugins.NotifyBase.request_rate_per_sec = 0

        # Our expected instance
        instance = meta.get('instance', None)

        # Our expected server objects
        _self = meta.get('self', None)

        # Our expected Query response (True, False, or exception type)
        response = meta.get('response', True)

        # Our expected privacy url
        # Don't set this if don't need to check it's value
        privacy_url = meta.get('privacy_url')

        # Our regular expression
        url_matches = meta.get('url_matches')

        # Allow us to force the server response code to be something other then
        # the defaults
        requests_response_code = meta.get(
            'requests_response_code',
            requests.codes.ok if response else requests.codes.not_found,
        )

        # Allow us to force the server response text to be something other then
        # the defaults
        requests_response_text = meta.get('requests_response_text')
        if not isinstance(requests_response_text, str):
            # Convert to string
            requests_response_text = dumps(requests_response_text)

        # Whether or not we should include an image with our request; unless
        # otherwise specified, we assume that images are to be included
        include_image = meta.get('include_image', True)
        if include_image:
            # a default asset
            asset = AppriseAsset()

        else:
            # Disable images
            asset = AppriseAsset(image_path_mask=False, image_url_mask=False)
            asset.image_url_logo = None

        test_requests_exceptions = meta.get(
            'test_requests_exceptions', False)

        # Mock our request object
        robj = mock.Mock()
        robj.content = u''
        mock_get.return_value = robj
        mock_post.return_value = robj

        if test_requests_exceptions is False:
            # Handle our default response
            mock_post.return_value.status_code = requests_response_code
            mock_get.return_value.status_code = requests_response_code

            # Handle our default text response
            mock_get.return_value.content = requests_response_text
            mock_post.return_value.content = requests_response_text
            mock_get.return_value.text = requests_response_text
            mock_post.return_value.text = requests_response_text

            # Ensure there is no side effect set
            mock_post.side_effect = None
            mock_get.side_effect = None

        else:
            # Handle exception testing; first we turn the boolean flag
            # into a list of exceptions
            test_requests_exceptions = self.req_exceptions

        try:
            # We can now instantiate our object:
            obj = Apprise.instantiate(
                url, asset=asset, suppress_exceptions=False)

        except Exception as e:
            # Handle our exception
            if instance is None:
                print('%s %s' % (url, str(e)))
                raise e

            if not isinstance(e, instance):
                print('%s %s' % (url, str(e)))
                raise e

            # We're okay if we get here
            return

        if obj is None:
            if instance is not None:
                # We're done (assuming this is what we were
                # expecting)
                print("{} didn't instantiate itself "
                      "(we expected it to be a {})".format(
                          url, instance))
                assert False
            # We're done because we got the results we expected
            return

        if instance is None:
            # Expected None but didn't get it
            print('%s instantiated %s (but expected None)' % (
                url, str(obj)))
            assert False

        if not isinstance(obj, instance):
            print('%s instantiated %s (but expected %s)' % (
                url, type(instance), str(obj)))
            assert False

        if isinstance(obj, plugins.NotifyBase):
            # Ensure we are not performing any type of thorttling
            obj.request_rate_per_sec = 0

            # We loaded okay; now lets make sure we can reverse
            # this url
            assert isinstance(obj.url(), str) is True

            # Test url() with privacy=True
            assert isinstance(
                obj.url(privacy=True), str) is True

            # Some Simple Invalid Instance Testing
            assert instance.parse_url(None) is None
            assert instance.parse_url(object) is None
            assert instance.parse_url(42) is None

            if privacy_url:
                # Assess that our privacy url is as expected
                if not obj.url(privacy=True).startswith(privacy_url):
                    raise AssertionError(
                        "Privacy URL: '{}' != expected '{}'".format(
                            obj.url(privacy=True)[:len(privacy_url)],
                            privacy_url))

            if url_matches:
                # Assess that our URL matches a set regex
                assert re.search(url_matches, obj.url())

            # Instantiate the exact same object again using the URL
            # from the one that was already created properly
            obj_cmp = Apprise.instantiate(obj.url())

            # Our object should be the same instance as what we had
            # originally expected above.
            if not isinstance(obj_cmp, plugins.NotifyBase):
                # Assert messages are hard to trace back with the
                # way these tests work. Just printing before
                # throwing our assertion failure makes things
                # easier to debug later on
                print('TEST FAIL: {} regenerated as {}'.format(
                    url, obj.url()))
                assert False

            # Tidy our object
            del obj_cmp

        if _self:
            # Iterate over our expected entries inside of our
            # object
            for key, val in self.items():
                # Test that our object has the desired key
                assert hasattr(key, obj) is True
                assert getattr(key, obj) == val

        try:
            self.__notify(url, obj, meta, asset)

        except AssertionError:
            # Don't mess with these entries
            print('%s AssertionError' % url)
            raise

        # Tidy our object and allow any possible defined destructors to
        # be executed.
        del obj

    @mock.patch('requests.get')
    @mock.patch('requests.post')
    @mock.patch('requests.head')
    @mock.patch('requests.put')
    @mock.patch('requests.delete')
    def __notify(self, url, obj, meta, asset, mock_del, mock_put, mock_head,
                 mock_post, mock_get):
        """
        Perform notification testing against object specified
        """
        #
        # Prepare our options
        #

        # Allow notification type override, otherwise default to INFO
        notify_type = meta.get('notify_type', NotifyType.INFO)

        # Whether or not we're testing exceptions or not
        test_requests_exceptions = meta.get('test_requests_exceptions', False)

        # Our expected Query response (True, False, or exception type)
        response = meta.get('response', True)

        # Our expected Notify response (True or False)
        notify_response = meta.get('notify_response', response)

        # Our expected Notify Attachment response (True or False)
        attach_response = meta.get('attach_response', notify_response)

        # Test attachments
        # Don't set this if don't need to check it's value
        check_attachments = meta.get('check_attachments', True)

        # Allow us to force the server response code to be something other then
        # the defaults
        requests_response_code = meta.get(
            'requests_response_code',
            requests.codes.ok if response else requests.codes.not_found,
        )

        # Allow us to force the server response text to be something other then
        # the defaults
        requests_response_text = meta.get('requests_response_text')
        if not isinstance(requests_response_text, str):
            # Convert to string
            requests_response_text = dumps(requests_response_text)

        # A request
        robj = mock.Mock()
        robj.content = u''
        mock_get.return_value = robj
        mock_post.return_value = robj
        mock_head.return_value = robj
        mock_del.return_value = robj
        mock_put.return_value = robj

        if test_requests_exceptions is False:
            # Handle our default response
            mock_put.return_value.status_code = requests_response_code
            mock_head.return_value.status_code = requests_response_code
            mock_del.return_value.status_code = requests_response_code
            mock_post.return_value.status_code = requests_response_code
            mock_get.return_value.status_code = requests_response_code

            # Handle our default text response
            mock_get.return_value.content = requests_response_text
            mock_post.return_value.content = requests_response_text
            mock_del.return_value.content = requests_response_text
            mock_put.return_value.content = requests_response_text
            mock_head.return_value.content = requests_response_text

            mock_get.return_value.text = requests_response_text
            mock_post.return_value.text = requests_response_text
            mock_put.return_value.text = requests_response_text
            mock_del.return_value.text = requests_response_text
            mock_head.return_value.text = requests_response_text

            # Ensure there is no side effect set
            mock_post.side_effect = None
            mock_del.side_effect = None
            mock_put.side_effect = None
            mock_head.side_effect = None
            mock_get.side_effect = None

        else:
            # Handle exception testing; first we turn the boolean flag
            # into a list of exceptions
            test_requests_exceptions = self.req_exceptions

        try:
            if test_requests_exceptions is False:
                # Disable throttling
                obj.request_rate_per_sec = 0

                # check that we're as expected
                assert obj.notify(
                    body=self.body, title=self.title,
                    notify_type=notify_type) == notify_response

                # check that this doesn't change using different overflow
                # methods
                assert obj.notify(
                    body=self.body, title=self.title,
                    notify_type=notify_type,
                    overflow=OverflowMode.UPSTREAM) == notify_response
                assert obj.notify(
                    body=self.body, title=self.title,
                    notify_type=notify_type,
                    overflow=OverflowMode.TRUNCATE) == notify_response
                assert obj.notify(
                    body=self.body, title=self.title,
                    notify_type=notify_type,
                    overflow=OverflowMode.SPLIT) == notify_response

                #
                # Handle varations of the Asset Object missing fields
                #

                # First make a backup
                app_id = asset.app_id
                app_desc = asset.app_desc

                # now clear records
                asset.app_id = None
                asset.app_desc = None

                # Notify should still work
                assert obj.notify(
                    body=self.body, title=self.title,
                    notify_type=notify_type) == notify_response

                # App ID only
                asset.app_id = app_id
                asset.app_desc = None

                # Notify should still work
                assert obj.notify(
                    body=self.body, title=self.title,
                    notify_type=notify_type) == notify_response

                # App Desc only
                asset.app_id = None
                asset.app_desc = app_desc

                # Notify should still work
                assert obj.notify(
                    body=self.body, title=self.title,
                    notify_type=notify_type) == notify_response

                # Restore
                asset.app_id = app_id
                asset.app_desc = app_desc

                if check_attachments:
                    # Test single attachment support; even if the service
                    # doesn't support attachments, it should still
                    # gracefully ignore the data
                    attach = os.path.join(
                        self.__test_var_dir, 'apprise-test.gif')
                    assert obj.notify(
                        body=self.body, title=self.title,
                        notify_type=notify_type,
                        attach=attach) == attach_response

                    # Same results should apply to a list of attachments
                    attach = AppriseAttachment((
                        os.path.join(self.__test_var_dir, 'apprise-test.gif'),
                        os.path.join(self.__test_var_dir, 'apprise-test.png'),
                        os.path.join(self.__test_var_dir, 'apprise-test.jpeg'),
                    ))
                    assert obj.notify(
                        body=self.body, title=self.title,
                        notify_type=notify_type,
                        attach=attach) == attach_response

            else:
                # Disable throttling
                obj.request_rate_per_sec = 0

                for _exception in self.req_exceptions:
                    mock_post.side_effect = _exception
                    mock_head.side_effect = _exception
                    mock_del.side_effect = _exception
                    mock_put.side_effect = _exception
                    mock_get.side_effect = _exception

                    try:
                        assert obj.notify(
                            body=self.body, title=self.title,
                            notify_type=NotifyType.INFO) is False

                    except AssertionError:
                        # Don't mess with these entries
                        raise

                    except Exception:
                        # We can't handle this exception type
                        raise

        except AssertionError:
            # Don't mess with these entries
            raise

        except Exception as e:
            # Check that we were expecting this exception to happen
            try:
                if not isinstance(e, response):
                    raise e

            except TypeError:
                print('%s Unhandled response %s' % (url, type(e)))
                raise e

        #
        # Do the test again but without a title defined
        #
        try:
            if test_requests_exceptions is False:
                # check that we're as expected
                assert obj.notify(body='body', notify_type=notify_type) \
                    == notify_response

            else:
                for _exception in self.req_exceptions:
                    mock_post.side_effect = _exception
                    mock_del.side_effect = _exception
                    mock_put.side_effect = _exception
                    mock_head.side_effect = _exception
                    mock_get.side_effect = _exception

                    try:
                        assert obj.notify(
                            body=self.body,
                            notify_type=NotifyType.INFO) is False

                    except AssertionError:
                        # Don't mess with these entries
                        raise

                    except Exception:
                        # We can't handle this exception type
                        raise

        except AssertionError:
            # Don't mess with these entries
            raise

        except Exception as e:
            # Check that we were expecting this exception to happen
            if not isinstance(e, response):
                raise e

        return True
