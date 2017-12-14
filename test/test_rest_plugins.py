# -*- coding: utf-8 -*-
#
# REST Based Plugins - Unit Tests
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

from apprise import plugins
from apprise import NotifyType
from apprise import Apprise
from apprise import AppriseAsset
import requests
import mock


TEST_URLS = (
    ##################################
    # NotifyBoxcar
    ##################################
    ('boxcar://', {
        'instance': None,
    }),
    # No secret specified
    ('boxcar://%s' % ('a' * 64), {
        'instance': None,
    }),
    # An invalid access and secret key specified
    ('boxcar://access.key/secret.key/', {
        'instance': plugins.NotifyBoxcar,
        # Thrown because there were no recipients specified
        'exception': TypeError,
    }),
    # Provide both an access and a secret
    ('boxcar://%s/%s' % ('a' * 64, 'b' * 64), {
        'instance': plugins.NotifyBoxcar,
        'requests_response_code': requests.codes.created,
    }),
    # Test without image set
    ('boxcar://%s/%s' % ('a' * 64, 'b' * 64), {
        'instance': plugins.NotifyBoxcar,
        'requests_response_code': requests.codes.created,
        # don't include an image by default
        'include_image': False,
    }),
    # our access, secret and device are all 64 characters
    # which is what we're doing here
    ('boxcar://%s/%s/@tag1/tag2///%s/' % (
        'a' * 64, 'b' * 64, 'd' * 64), {
        'instance': plugins.NotifyBoxcar,
        'requests_response_code': requests.codes.created,
    }),
    # An invalid tag
    ('boxcar://%s/%s/@%s' % ('a' * 64, 'b' * 64, 't' * 64), {
        'instance': plugins.NotifyBoxcar,
        'requests_response_code': requests.codes.created,
    }),
    ('boxcar://:@/', {
        'instance': None,
    }),
    ('boxcar://%s/%s/' % ('a' * 64, 'b' * 64), {
        'instance': plugins.NotifyBoxcar,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('boxcar://%s/%s/' % ('a' * 64, 'b' * 64), {
        'instance': plugins.NotifyBoxcar,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('boxcar://%s/%s/' % ('a' * 64, 'b' * 64), {
        'instance': plugins.NotifyBoxcar,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),

    ##################################
    # NotifyFaast
    ##################################
    ('faast://', {
        'instance': None,
    }),
    # Auth Token specified
    ('faast://%s' % ('a' * 32), {
        'instance': plugins.NotifyFaast,
    }),
    ('faast://%s' % ('a' * 32), {
        'instance': plugins.NotifyFaast,
        # don't include an image by default
        'include_image': False,
    }),
    ('faast://:@/', {
        'instance': None,
    }),
    ('faast://%s' % ('a' * 32), {
        'instance': plugins.NotifyFaast,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('faast://%s' % ('a' * 32), {
        'instance': plugins.NotifyFaast,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('faast://%s' % ('a' * 32), {
        'instance': plugins.NotifyFaast,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),

    ##################################
    # NotifyJoin
    ##################################
    ('join://', {
        'instance': None,
    }),
    # APIkey; no device
    ('join://%s' % ('a' * 32), {
        'instance': plugins.NotifyJoin,
    }),
    # Invalid APIKey
    ('join://%s' % ('a' * 24), {
        'instance': None,
        # Missing a channel
        'exception': TypeError,
    }),
    # APIKey + device
    ('join://%s/%s' % ('a' * 32, 'd' * 32), {
        'instance': plugins.NotifyJoin,
        # don't include an image by default
        'include_image': False,
    }),
    # APIKey + 2 devices
    ('join://%s/%s/%s' % ('a' * 32, 'd' * 32, 'e' * 32), {
        'instance': plugins.NotifyJoin,
        # don't include an image by default
        'include_image': False,
    }),
    # APIKey + 1 device and 1 group
    ('join://%s/%s/%s' % ('a' * 32, 'd' * 32, 'group.chrome'), {
        'instance': plugins.NotifyJoin,
    }),
    # APIKey + bad device
    ('join://%s/%s' % ('a' * 32, 'd' * 10), {
        'instance': plugins.NotifyJoin,
    }),
    # APIKey + bad url
    ('join://:@/', {
        'instance': None,
    }),
    ('join://%s' % ('a' * 32), {
        'instance': plugins.NotifyJoin,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('join://%s' % ('a' * 32), {
        'instance': plugins.NotifyJoin,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    # apikey = a
    ('join://%s' % ('a' * 32), {
        'instance': plugins.NotifyJoin,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),

    ##################################
    # NotifyJSON
    ##################################
    ('json://', {
        'instance': None,
    }),
    ('jsons://', {
        'instance': None,
    }),
    ('json://localhost', {
        'instance': plugins.NotifyJSON,
    }),
    ('json://user:pass@localhost', {
        'instance': plugins.NotifyJSON,
    }),
    ('json://localhost:8080', {
        'instance': plugins.NotifyJSON,
    }),
    ('json://user:pass@localhost:8080', {
        'instance': plugins.NotifyJSON,
    }),
    ('jsons://localhost', {
        'instance': plugins.NotifyJSON,
    }),
    ('jsons://user:pass@localhost', {
        'instance': plugins.NotifyJSON,
    }),
    ('jsons://localhost:8080/path/', {
        'instance': plugins.NotifyJSON,
    }),
    ('jsons://user:pass@localhost:8080', {
        'instance': plugins.NotifyJSON,
    }),
    ('json://:@/', {
        'instance': None,
    }),
    ('json://user:pass@localhost:8081', {
        'instance': plugins.NotifyJSON,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('json://user:pass@localhost:8082', {
        'instance': plugins.NotifyJSON,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('json://user:pass@localhost:8083', {
        'instance': plugins.NotifyJSON,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),

    ##################################
    # NotifyKODI
    ##################################
    ('kodi://', {
        'instance': None,
    }),
    ('kodis://', {
        'instance': None,
    }),
    ('kodi://localhost', {
        'instance': plugins.NotifyXBMC,
    }),
    ('kodi://user:pass@localhost', {
        'instance': plugins.NotifyXBMC,
    }),
    ('kodi://localhost:8080', {
        'instance': plugins.NotifyXBMC,
    }),
    ('kodi://user:pass@localhost:8080', {
        'instance': plugins.NotifyXBMC,
    }),
    ('kodis://localhost', {
        'instance': plugins.NotifyXBMC,
    }),
    ('kodis://user:pass@localhost', {
        'instance': plugins.NotifyXBMC,
    }),
    ('kodis://localhost:8080/path/', {
        'instance': plugins.NotifyXBMC,
    }),
    ('kodis://user:pass@localhost:8080', {
        'instance': plugins.NotifyXBMC,
    }),
    ('kodi://localhost', {
        'instance': plugins.NotifyXBMC,
        # Experement with different notification types
        'notify_type': NotifyType.WARNING,
    }),
    ('kodi://localhost', {
        'instance': plugins.NotifyXBMC,
        # Experement with different notification types
        'notify_type': NotifyType.FAILURE,
    }),
    ('kodis://localhost:443', {
        'instance': plugins.NotifyXBMC,
        # don't include an image by default
        'include_image': False,
    }),
    ('kodi://:@/', {
        'instance': None,
    }),
    ('kodi://user:pass@localhost:8081', {
        'instance': plugins.NotifyXBMC,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('kodi://user:pass@localhost:8082', {
        'instance': plugins.NotifyXBMC,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('kodi://user:pass@localhost:8083', {
        'instance': plugins.NotifyXBMC,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),

    ##################################
    # NotifyMatterMost
    ##################################
    ('mmost://', {
        'instance': None,
    }),
    ('mmosts://', {
        'instance': None,
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMatterMost,
    }),
    ('mmost://user@localhost/3ccdd113474722377935511fc85d3dd4?channel=test', {
        'instance': plugins.NotifyMatterMost,
    }),
    ('mmost://localhost:8080/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMatterMost,
    }),
    ('mmost://localhost:0/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMatterMost,
    }),
    ('mmost://localhost:invalid-port/3ccdd113474722377935511fc85d3dd4', {
        'instance': None,
    }),
    ('mmosts://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMatterMost,
    }),
    ('mmosts://localhost', {
        'instance': plugins.NotifyMatterMost,
        # Thrown because there was no webhook id specified
        'exception': TypeError,
    }),
    ('mmost://localhost/bad-web-hook', {
        'instance': plugins.NotifyMatterMost,
        # Thrown because the webhook is not in a valid format
        'exception': TypeError,
    }),
    ('mmost://:@/', {
        'instance': None,
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMatterMost,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMatterMost,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMatterMost,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),

    ##################################
    # NotifyMyAndroid
    ##################################
    ('nma://', {
        'instance': None,
    }),
    # APIkey; no device
    ('nma://%s' % ('a' * 48), {
        'instance': plugins.NotifyMyAndroid,
    }),
    # Invalid APIKey
    ('nma://%s' % ('a' * 24), {
        'instance': None,
        # Missing a channel
        'exception': TypeError,
    }),
    # APIKey
    ('nma://%s' % ('a' * 48), {
        'instance': plugins.NotifyMyAndroid,
        # don't include an image by default
        'include_image': False,
    }),
    # APIKey + with image
    ('nma://%s' % ('a' * 48), {
        'instance': plugins.NotifyMyAndroid,
    }),
    # bad url
    ('nma://:@/', {
        'instance': None,
    }),
    ('nma://%s' % ('a' * 48), {
        'instance': plugins.NotifyMyAndroid,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('nma://%s' % ('a' * 48), {
        'instance': plugins.NotifyMyAndroid,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    # apikey = a
    ('nma://%s' % ('a' * 48), {
        'instance': plugins.NotifyMyAndroid,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),

    ##################################
    # NotifySlack
    ##################################
    ('slack://', {
        'instance': None,
    }),
    ('slack://:@/', {
        'instance': None,
    }),
    ('slack://T1JJ3T3L2', {
        # Just Token 1 provided
        'instance': None,
    }),
    ('slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#hmm/#-invalid-', {
        # No username specified; this is still okay as we sub in
        # default; The one invalid channel is skipped when sending a message
        'instance': plugins.NotifySlack,
    }),
    ('slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#channel', {
        # No username specified; this is still okay as we sub in
        # default; The one invalid channel is skipped when sending a message
        'instance': plugins.NotifySlack,
        # don't include an image by default
        'include_image': False,
    }),
    ('slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/+id/%20/@id/', {
        # + encoded id,
        # @ userid
        'instance': plugins.NotifySlack,
    }),
    ('slack://username@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#nuxref', {
        'instance': plugins.NotifySlack,
    }),
    ('slack://username@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ', {
        # Missing a channel
        'exception': TypeError,
    }),
    ('slack://username@INVALID/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#cool', {
        # invalid 1st Token
        'exception': TypeError,
    }),
    ('slack://username@T1JJ3T3L2/INVALID/TIiajkdnlazkcOXrIdevi7FQ/#great', {
        # invalid 2rd Token
        'exception': TypeError,
    }),
    ('slack://username@T1JJ3T3L2/A1BRTD4JD/INVALID/#channel', {
        # invalid 3rd Token
        'exception': TypeError,
    }),
    ('slack://l2g@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#usenet', {
        'instance': plugins.NotifySlack,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('slack://respect@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#a', {
        'instance': plugins.NotifySlack,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('slack://notify@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#b', {
        'instance': plugins.NotifySlack,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),

    ##################################
    # NotifyKODI
    ##################################
    ('xbmc://', {
        'instance': None,
    }),
    ('xbmc://localhost', {
        'instance': plugins.NotifyXBMC,
    }),
    ('xbmc://user:pass@localhost', {
        'instance': plugins.NotifyXBMC,
    }),
    ('xbmc://localhost:8080', {
        'instance': plugins.NotifyXBMC,
    }),
    ('xbmc://user:pass@localhost:8080', {
        'instance': plugins.NotifyXBMC,
    }),
    ('xbmc://localhost', {
        'instance': plugins.NotifyXBMC,
        # don't include an image by default
        'include_image': False,
    }),
    ('xbmc://localhost', {
        'instance': plugins.NotifyXBMC,
        # Experement with different notification types
        'notify_type': NotifyType.WARNING,
    }),
    ('xbmc://localhost', {
        'instance': plugins.NotifyXBMC,
        # Experement with different notification types
        'notify_type': NotifyType.FAILURE,
    }),
    ('xbmc://:@/', {
        'instance': None,
    }),
    ('xbmc://user:pass@localhost:8081', {
        'instance': plugins.NotifyXBMC,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('xbmc://user:pass@localhost:8082', {
        'instance': plugins.NotifyXBMC,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('xbmc://user:pass@localhost:8083', {
        'instance': plugins.NotifyXBMC,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),

    ##################################
    # NotifyXML
    ##################################
    ('xml://', {
        'instance': None,
    }),
    ('xmls://', {
        'instance': None,
    }),
    ('xml://localhost', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://user:pass@localhost', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://localhost:8080', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://user:pass@localhost:8080', {
        'instance': plugins.NotifyXML,
    }),
    ('xmls://localhost', {
        'instance': plugins.NotifyXML,
    }),
    ('xmls://user:pass@localhost', {
        'instance': plugins.NotifyXML,
    }),
    ('xmls://localhost:8080/path/', {
        'instance': plugins.NotifyXML,
    }),
    ('xmls://user:pass@localhost:8080', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://:@/', {
        'instance': None,
    }),
    ('xml://user:pass@localhost:8081', {
        'instance': plugins.NotifyXML,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('xml://user:pass@localhost:8082', {
        'instance': plugins.NotifyXML,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('xml://user:pass@localhost:8083', {
        'instance': plugins.NotifyXML,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_rest_plugins(mock_post, mock_get):
    """
    API: REST Based Plugins()

    """

    # iterate over our dictionary and test it out
    for (url, meta) in TEST_URLS:

        # Our expected instance
        instance = meta.get('instance', None)

        # Our expected exception
        exception = meta.get('exception', None)

        # Our expected server objects
        self = meta.get('self', None)

        # Our expected Query response (True, False, or exception type)
        response = meta.get('response', True)

        # Allow us to force the server response code to be something other then
        # the defaults
        requests_response_code = meta.get(
            'requests_response_code',
            requests.codes.ok if response else requests.codes.not_found,
        )

        # Allow notification type override, otherwise default to INFO
        notify_type = meta.get('notify_type', NotifyType.INFO)

        # Whether or not we should include an image with our request; unless
        # otherwise specified, we assume that images are to be included
        include_image = meta.get('include_image', True)
        if include_image:
            # a default asset
            asset = AppriseAsset()

        else:
            # Disable images
            asset = AppriseAsset(image_path_mask=False, image_url_mask=False)

        test_requests_exceptions = meta.get(
            'test_requests_exceptions', False)

        # A request
        robj = mock.Mock()
        setattr(robj, 'raw', mock.Mock())
        # Allow raw.read() calls
        robj.raw.read.return_value = ''
        mock_get.return_value = robj
        mock_post.return_value = robj

        if test_requests_exceptions is False:
            # Handle our default response
            mock_post.return_value.status_code = requests_response_code
            mock_get.return_value.status_code = requests_response_code
            mock_post.side_effect = None
            mock_get.side_effect = None

        else:
            # Handle exception testing; first we turn the boolean flag ito
            # a list of exceptions
            test_requests_exceptions = (
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

        try:
            obj = Apprise.instantiate(
                url, asset=asset, suppress_exceptions=False)

            # Make sure we weren't expecting an exception and just didn't get
            # one.
            assert exception is None

            if obj is None:
                # We're done (assuming this is what we were expecting)
                assert instance is None
                continue

            if instance is None:
                # Expected None but didn't get it
                print('%s instantiated %s' % (url, str(obj)))
                assert(False)

            assert(isinstance(obj, instance))

            if self:
                # Iterate over our expected entries inside of our object
                for key, val in self.items():
                    # Test that our object has the desired key
                    assert(hasattr(key, obj))
                    assert(getattr(key, obj) == val)

            try:
                if test_requests_exceptions is False:
                    # check that we're as expected
                    assert obj.notify(
                        title='test', body='body',
                        notify_type=notify_type) == response

                else:
                    for exception in test_requests_exceptions:
                        mock_post.side_effect = exception
                        mock_get.side_effect = exception
                        try:
                            assert obj.notify(
                                title='test', body='body',
                                notify_type=NotifyType.INFO) is False

                        except AssertionError:
                            # Don't mess with these entries
                            raise

                        except Exception as e:
                            # We can't handle this exception type
                            print('%s / %s' % (url, str(e)))
                            assert False

            except AssertionError:
                # Don't mess with these entries
                print('%s AssertionError' % url)
                raise

            except Exception as e:
                # Check that we were expecting this exception to happen
                assert isinstance(e, response)

        except AssertionError:
            # Don't mess with these entries
            print('%s AssertionError' % url)
            raise

        except Exception as e:
            # Handle our exception
            print('%s / %s' % (url, str(e)))
            assert(exception is not None)
            assert(isinstance(e, exception))


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_notify_boxcar_plugin(mock_post, mock_get):
    """
    API: NotifyBoxcar() Extra Checks

    """
    # Generate some generic message types
    device = 'A' * 64
    tag = '@B' * 63

    access = '-' * 64
    secret = '_' * 64

    # Initializes the plugin with recipients set to None
    plugins.NotifyBoxcar(access=access, secret=secret, recipients=None)

    # Initializes the plugin with a valid access, but invalid access key
    try:
        plugins.NotifyBoxcar(access=None, secret=secret, recipients=None)
        assert(False)

    except TypeError:
        # We should throw an exception for knowingly having an invalid
        assert(True)

    # Initializes the plugin with a valid access, but invalid secret key
    try:
        plugins.NotifyBoxcar(access=access, secret='invalid', recipients=None)
        assert(False)

    except TypeError:
        # We should throw an exception for knowingly having an invalid key
        assert(True)

    # Initializes the plugin with a valid access, but invalid secret
    try:
        plugins.NotifyBoxcar(access=access, secret=None, recipients=None)
        assert(False)

    except TypeError:
        # We should throw an exception for knowingly having an invalid
        assert(True)

    # Initializes the plugin with recipients list
    # the below also tests our the variation of recipient types
    plugins.NotifyBoxcar(
        access=access, secret=secret, recipients=[device, tag])

    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.created
    mock_get.return_value.status_code = requests.codes.created

    # Test notifications without a body or a title
    p = plugins.NotifyBoxcar(access=access, secret=secret, recipients=None)
    p.notify(body=None, title=None, notify_type=NotifyType.INFO) is True


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_notify_join_plugin(mock_post, mock_get):
    """
    API: NotifyJoin() Extra Checks

    """
    # Generate some generic message types
    device = 'A' * 32
    group = 'group.chrome'
    apikey = 'a' * 32

    # Initializes the plugin with devices set to a string
    plugins.NotifyJoin(apikey=apikey, devices=group)

    # Initializes the plugin with devices set to None
    plugins.NotifyJoin(apikey=apikey, devices=None)

    # Initializes the plugin with devices set to a set
    p = plugins.NotifyJoin(apikey=apikey, devices=[group, device])

    # Prepare our mock responses
    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.created
    mock_get.return_value.status_code = requests.codes.created

    # Test notifications without a body or a title; nothing to send
    # so we return False
    p.notify(body=None, title=None, notify_type=NotifyType.INFO) is False


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_notify_slack_plugin(mock_post, mock_get):
    """
    API: NotifySlack() Extra Checks

    """

    # Initialize some generic (but valid) tokens
    token_a = 'A' * 9
    token_b = 'B' * 9
    token_c = 'c' * 24

    # Support strings
    channels = 'chan1,#chan2,+id,@user,,,'

    obj = plugins.NotifySlack(
        token_a=token_a, token_b=token_b, token_c=token_c, channels=channels)
    assert(len(obj.channels) == 4)
    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok

    # Empty Channel list
    try:
        plugins.NotifySlack(
            token_a=token_a, token_b=token_b, token_c=token_c,
            channels=None)
        assert(False)

    except TypeError:
        # we'll thrown because an empty list of channels was provided
        assert(True)

    # Test include_image
    obj = plugins.NotifySlack(
        token_a=token_a, token_b=token_b, token_c=token_c, channels=channels,
        include_image=True)

    # This call includes an image with it's payload:
    assert obj.notify(title='title', body='body',
                      notify_type=NotifyType.INFO) is True
