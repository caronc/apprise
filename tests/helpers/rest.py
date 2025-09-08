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

from json import dumps

# Disable logging for a cleaner testing output
import logging
import os
from random import choice
import re
from string import ascii_uppercase as str_alpha, digits as str_num
from unittest import mock

import requests

from apprise import (
    Apprise,
    AppriseAsset,
    AppriseAttachment,
    NotifyBase,
    NotifyType,
    PersistentStoreMode,
)
from apprise.common import OverflowMode

logging.disable(logging.CRITICAL)


class AppriseURLTester:

    # Some exception handling we'll use
    req_exceptions = (
        requests.ConnectionError(0, "requests.ConnectionError() not handled"),
        requests.RequestException(
            0, "requests.RequestException() not handled"
        ),
        requests.HTTPError(0, "requests.HTTPError() not handled"),
        requests.ReadTimeout(0, "requests.ReadTimeout() not handled"),
        requests.TooManyRedirects(
            0, "requests.TooManyRedirects() not handled"
        ),
    )

    # Attachment Testing Directory
    __test_var_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "var"
    )

    # Our URLs we'll test against
    __tests = []

    # Define how many characters exist per line
    row = 80

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    def __init__(self, tests=None, *args, **kwargs):
        """Our initialization."""
        # Create a large body and title with random data
        self.body = "".join(
            choice(str_alpha + str_num + " ") for _ in range(self.body_len)
        )
        self.body = "\r\n".join([
            self.body[i : i + self.row]
            for i in range(0, len(self.body), self.row)
        ])

        # Create our title using random data
        self.title = "".join(
            choice(str_alpha + str_num) for _ in range(self.title_len)
        )

        if tests:
            self.__tests = tests

    def add(self, url, meta):
        """Adds a test suite to our object."""
        self.__tests.append({
            "url": url,
            "meta": meta,
        })

    def run_all(self, tmpdir=None):
        """Run all of our tests."""
        # iterate over our dictionary and test it out
        for url, meta in self.__tests:
            self.run(url, meta, tmpdir)

    @mock.patch("requests.get")
    @mock.patch("requests.post")
    @mock.patch("requests.request")
    def run(self, url, meta, tmpdir, mock_request, mock_post, mock_get):
        """Run a specific test."""

        # Our expected instance
        instance = meta.get("instance", None)

        # Our expected server objects
        _self = meta.get("self", None)

        # Our expected privacy url
        # Don't set this if don't need to check it's value
        privacy_url = meta.get("privacy_url")

        # Our regular expression
        url_matches = meta.get("url_matches")

        # Detect our storage path (used to set persistent storage
        # mode
        storage_path = (
            tmpdir
            if tmpdir and isinstance(tmpdir, str) and os.path.isdir(tmpdir)
            else None
        )

        # Our storage mode to set
        storage_mode = meta.get(
            "storage_mode",
            (
                PersistentStoreMode.MEMORY
                if not storage_path
                else PersistentStoreMode.AUTO
            ),
        )

        # Debug Mode
        pdb = meta.get("pdb", False)

        # Whether or not we should include an image with our request; unless
        # otherwise specified, we assume that images are to be included
        include_image = meta.get("include_image", True)
        if include_image:
            # a default asset
            asset = AppriseAsset(
                storage_mode=storage_mode,
                storage_path=storage_path,
            )

        else:
            # Disable images
            asset = AppriseAsset(
                image_path_mask=False,
                image_url_mask=False,
                storage_mode=storage_mode,
                storage_path=storage_path,
            )
            asset.image_url_logo = None

        # Mock our request object
        robj = mock.Mock()
        robj.content = ""
        mock_get.return_value = robj
        mock_post.return_value = robj
        mock_request.return_value = robj

        if pdb:
            # Makes it easier to debug with this peice of code
            # just add `pdb': True to the call that is failing
            import pdb

            pdb.set_trace()

        try:
            # We can now instantiate our object:
            obj = Apprise.instantiate(
                url, asset=asset, suppress_exceptions=False
            )

        except Exception as e:
            # Handle our exception
            if instance is None:
                raise e

            if not isinstance(e, instance):
                raise e

            # We're okay if we get here
            return

        if obj is None:
            if instance is not None:
                # We're done (assuming this is what we were
                # expecting)
                raise AssertionError()
            # We're done because we got the results we expected
            return

        if instance is None:
            # Expected None but didn't get it
            raise AssertionError()

        if not isinstance(obj, instance):
            raise AssertionError()

        if isinstance(obj, NotifyBase):
            # Ensure we are not performing any type of thorttling
            obj.request_rate_per_sec = 0

            # We loaded okay; now lets make sure we can reverse
            # this url
            assert isinstance(obj.url(), str) is True

            # Test that we support a url identifier
            url_id = obj.url_id()

            # It can be either disabled or a string; nothing else
            assert isinstance(url_id, str) or (
                url_id is None and obj.url_identifier is False
            )

            # Verify we can acquire a target count as an integer
            assert isinstance(len(obj), int)

            # Test url() with privacy=True
            assert isinstance(obj.url(privacy=True), str) is True

            # Some Simple Invalid Instance Testing
            assert instance.parse_url(None) is None
            assert instance.parse_url(object) is None
            assert instance.parse_url(42) is None

            # Assess that our privacy url is as expected
            if privacy_url and not obj.url(privacy=True).startswith(
                privacy_url
            ):
                raise AssertionError(
                    "Privacy URL:"
                    f" '{obj.url(privacy=True)[:len(privacy_url)]}' !="
                    f" expected '{privacy_url}'"
                )

            if url_matches:
                # Assess that our URL matches a set regex
                assert re.search(url_matches, obj.url())

            # Instantiate the exact same object again using the URL
            # from the one that was already created properly
            obj_cmp = Apprise.instantiate(obj.url())

            if not isinstance(obj_cmp, NotifyBase):
                raise AssertionError(
                    f"URL: {url} generated an un-reloadable "
                    f"url() of {obj.url()}"
                )

            # Our new object should produce the same url identifier
            elif obj.url_identifier != obj_cmp.url_identifier:
                raise AssertionError(
                    f"URL Identifier: '{obj_cmp.url_identifier}' != expected"
                    f" '{obj.url_identifier}'"
                )

            # Back our check up
            if obj.url_id() != obj_cmp.url_id():
                raise AssertionError(
                    f"URL ID(): '{obj_cmp.url_id()}' != expected"
                    f" '{obj.url_id()}'"
                )

            # Verify there is no change from the old and the new
            if len(obj) != len(obj_cmp):
                raise AssertionError(
                    f"Target miscount {len(obj)} != {len(obj_cmp)}"
                )

            # Tidy our object
            del obj_cmp
            del instance

        if _self:
            # Iterate over our expected entries inside of our
            # object
            for key, val in _self.items():
                # Test that our object has the desired key
                assert hasattr(obj, key) is True
                assert getattr(obj, key) == val

        try:
            self.__notify(url, obj, meta, asset)

        except AssertionError:
            # Don't mess with these entries
            raise

        # Tidy our object and allow any possible defined destructors to
        # be executed.
        del obj

    @mock.patch("requests.get")
    @mock.patch("requests.post")
    @mock.patch("requests.head")
    @mock.patch("requests.put")
    @mock.patch("requests.delete")
    @mock.patch("requests.patch")
    @mock.patch("requests.request")
    def __notify(
        self,
        url,
        obj,
        meta,
        asset,
        mock_request,
        mock_patch,
        mock_del,
        mock_put,
        mock_head,
        mock_post,
        mock_get,
    ):
        """Perform notification testing against object specified."""
        #
        # Prepare our options
        #

        # Allow notification type override, otherwise default to INFO
        notify_type = meta.get("notify_type", NotifyType.INFO)

        # Whether or not we're testing exceptions or not
        test_requests_exceptions = meta.get("test_requests_exceptions", False)

        # Our expected Query response (True, False, or exception type)
        response = meta.get("response", True)

        # Our expected Notify response (True or False)
        notify_response = meta.get("notify_response", response)

        # Our expected Notify Attachment response (True or False)
        attach_response = meta.get("attach_response", notify_response)

        # Test attachments
        # Don't set this if don't need to check it's value
        check_attachments = meta.get("check_attachments", True)

        # Allow us to force the server response code to be something other then
        # the defaults
        requests_response_code = meta.get(
            "requests_response_code",
            requests.codes.ok if response else requests.codes.not_found,
        )

        # Allow us to force the server response text to be something other then
        # the defaults
        requests_response_text = meta.get("requests_response_text")
        requests_response_content = None

        if isinstance(requests_response_text, str):
            requests_response_content = requests_response_text.encode("utf-8")

        elif isinstance(requests_response_text, bytes):
            requests_response_content = requests_response_text
            requests_response_text = requests_response_text.decode("utf-8")

        elif not isinstance(requests_response_text, str):
            # Convert to string
            requests_response_text = dumps(requests_response_text)
            requests_response_content = requests_response_text.encode("utf-8")

        else:
            requests_response_content = ""
            requests_response_text = ""

        # A request
        robj = mock.Mock()
        robj.content = ""
        robj.text = ""
        mock_get.return_value = robj
        mock_post.return_value = robj
        mock_head.return_value = robj
        mock_patch.return_value = robj
        mock_del.return_value = robj
        mock_put.return_value = robj
        mock_request.return_value = robj

        if test_requests_exceptions is False:
            # Handle our default response
            mock_put.return_value.status_code = requests_response_code
            mock_head.return_value.status_code = requests_response_code
            mock_del.return_value.status_code = requests_response_code
            mock_post.return_value.status_code = requests_response_code
            mock_get.return_value.status_code = requests_response_code
            mock_patch.return_value.status_code = requests_response_code
            mock_request.return_value.status_code = requests_response_code

            # Handle our default text response
            mock_get.return_value.content = requests_response_content
            mock_post.return_value.content = requests_response_content
            mock_del.return_value.content = requests_response_content
            mock_put.return_value.content = requests_response_content
            mock_head.return_value.content = requests_response_content
            mock_patch.return_value.content = requests_response_content
            mock_request.return_value.content = requests_response_content

            mock_get.return_value.text = requests_response_text
            mock_post.return_value.text = requests_response_text
            mock_put.return_value.text = requests_response_text
            mock_del.return_value.text = requests_response_text
            mock_head.return_value.text = requests_response_text
            mock_patch.return_value.text = requests_response_text
            mock_request.return_value.text = requests_response_text

            # Ensure there is no side effect set
            mock_post.side_effect = None
            mock_del.side_effect = None
            mock_put.side_effect = None
            mock_head.side_effect = None
            mock_get.side_effect = None
            mock_patch.side_effect = None
            mock_request.side_effect = None

        else:
            # Handle exception testing; first we turn the boolean flag
            # into a list of exceptions
            test_requests_exceptions = self.req_exceptions

        try:
            if test_requests_exceptions is False:

                # Verify we can acquire a target count as an integer
                targets = len(obj)

                # check that we're as expected
                _resp = obj.notify(
                    body=self.body, title=self.title, notify_type=notify_type
                )
                if _resp != notify_response:
                    raise AssertionError()

                if notify_response:
                    # If we successfully got a response, there must have been
                    # at least 1 target present
                    assert targets > 0

                # check that this doesn't change using different overflow
                # methods
                assert (
                    obj.notify(
                        body=self.body,
                        title=self.title,
                        notify_type=notify_type,
                        overflow=OverflowMode.UPSTREAM,
                    )
                    == notify_response
                )
                assert (
                    obj.notify(
                        body=self.body,
                        title=self.title,
                        notify_type=notify_type,
                        overflow=OverflowMode.TRUNCATE,
                    )
                    == notify_response
                )
                assert (
                    obj.notify(
                        body=self.body,
                        title=self.title,
                        notify_type=notify_type,
                        overflow=OverflowMode.SPLIT,
                    )
                    == notify_response
                )

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
                assert (
                    obj.notify(
                        body=self.body,
                        title=self.title,
                        notify_type=notify_type,
                    )
                    == notify_response
                )

                # App ID only
                asset.app_id = app_id
                asset.app_desc = None

                # Notify should still work
                assert (
                    obj.notify(
                        body=self.body,
                        title=self.title,
                        notify_type=notify_type,
                    )
                    == notify_response
                )

                # App Desc only
                asset.app_id = None
                asset.app_desc = app_desc

                # Notify should still work
                assert (
                    obj.notify(
                        body=self.body,
                        title=self.title,
                        notify_type=notify_type,
                    )
                    == notify_response
                )

                # Restore
                asset.app_id = app_id
                asset.app_desc = app_desc

                if check_attachments:
                    # Test single attachment support; even if the service
                    # doesn't support attachments, it should still
                    # gracefully ignore the data
                    attach = os.path.join(
                        self.__test_var_dir, "apprise-test.gif"
                    )
                    assert (
                        obj.notify(
                            body=self.body,
                            title=self.title,
                            notify_type=notify_type,
                            attach=attach,
                        )
                        == attach_response
                    )

                    # Same results should apply to a list of attachments
                    attach = AppriseAttachment((
                        os.path.join(self.__test_var_dir, "apprise-test.gif"),
                        os.path.join(self.__test_var_dir, "apprise-test.png"),
                        os.path.join(self.__test_var_dir, "apprise-test.jpeg"),
                    ))

                    assert (
                        obj.notify(
                            body=self.body,
                            title=self.title,
                            notify_type=notify_type,
                            attach=attach,
                        )
                        == attach_response
                    )

                    if obj.attachment_support:
                        #
                        # Services that support attachments should support
                        # sending a attachment (or more) without a body or
                        # title specified:
                        #
                        assert (
                            obj.notify(
                                body=None,
                                title=None,
                                notify_type=notify_type,
                                attach=attach,
                            )
                            == attach_response
                        )

                        # Turn off attachment support on the notifications
                        # that support it so we can test that any logic we
                        # have ot test against this flag is ran
                        obj.attachment_support = False

                        #
                        # Notifications should still transmit as normal if
                        # Attachment support is flipped off
                        #
                        assert (
                            obj.notify(
                                body=self.body,
                                title=self.title,
                                notify_type=notify_type,
                                attach=attach,
                            )
                            == notify_response
                        )

                        #
                        # We should not be able to send a message without a
                        # body or title in this circumstance
                        #
                        assert (
                            obj.notify(
                                body=None,
                                title=None,
                                notify_type=notify_type,
                                attach=attach,
                            )
                            is False
                        )

                        # Toggle Back
                        obj.attachment_support = True

                    else:  # No Attachment support
                        #
                        # We should not be able to send a message without a
                        # body or title in this circumstance
                        #
                        assert (
                            obj.notify(
                                body=None,
                                title=None,
                                notify_type=notify_type,
                                attach=attach,
                            )
                            is False
                        )
            else:

                for _exception in self.req_exceptions:
                    mock_post.side_effect = _exception
                    mock_head.side_effect = _exception
                    mock_del.side_effect = _exception
                    mock_put.side_effect = _exception
                    mock_get.side_effect = _exception
                    mock_patch.side_effect = _exception
                    mock_request.side_effect = _exception

                    try:
                        assert (
                            obj.notify(
                                body=self.body,
                                title=self.title,
                                notify_type=notify_type,
                            )
                            is False
                        )

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
                raise e  # noqa: B904 - intentional re-raising in test helper

        #
        # Do the test again but without a title defined
        #
        try:
            if test_requests_exceptions is False:
                # check that we're as expected
                assert (
                    obj.notify(body="body", notify_type=notify_type)
                    == notify_response
                )

            else:
                for _exception in self.req_exceptions:
                    mock_post.side_effect = _exception
                    mock_del.side_effect = _exception
                    mock_put.side_effect = _exception
                    mock_head.side_effect = _exception
                    mock_get.side_effect = _exception
                    mock_patch.side_effect = _exception
                    mock_request.side_effect = _exception

                    try:
                        assert (
                            obj.notify(body=self.body, notify_type=notify_type)
                            is False
                        )

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
