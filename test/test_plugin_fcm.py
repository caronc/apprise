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
import io
import os
import sys
import mock
import pytest
import requests
import json
from apprise import Apprise
from apprise import plugins
from helpers import AppriseURLTester

try:
    from apprise.plugins.NotifyFCM.oauth import GoogleOAuth
    from cryptography.exceptions import UnsupportedAlgorithm

except ImportError:
    # No problem; there is no cryptography support
    pass

try:
    from json.decoder import JSONDecodeError

except ImportError:
    # Python v2.7 Backwards Compatibility support
    JSONDecodeError = ValueError

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Test files for KeyFile Directory
PRIVATE_KEYFILE_DIR = os.path.join(os.path.dirname(__file__), 'var', 'fcm')

# Our Testing URLs
apprise_url_tests = (
    ('fcm://', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('fcm://:@/', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('fcm://project@%20%20/', {
        # invalid apikey
        'instance': TypeError,
    }),
    ('fcm://apikey/', {
        # no project id specified so we operate in legacy mode
        'instance': plugins.NotifyFCM,
        # but there are no targets specified so we return False
        'notify_response': False,
    }),
    ('fcm://apikey/device', {
        # Valid device
        'instance': plugins.NotifyFCM,
        'privacy_url': 'fcm://a...y/device',
    }),
    ('fcm://apikey/#topic', {
        # Valid topic
        'instance': plugins.NotifyFCM,
        'privacy_url': 'fcm://a...y/%23topic',
    }),
    ('fcm://apikey/device?mode=invalid', {
        # Valid device, invalid mode
        'instance': TypeError,
    }),
    ('fcm://apikey/#topic1/device/%20/', {
        # Valid topic, valid device, and invalid entry
        'instance': plugins.NotifyFCM,
    }),
    ('fcm://apikey?to=#topic1,device', {
        # Test to=
        'instance': plugins.NotifyFCM,
    }),
    ('fcm://?apikey=abc123&to=device', {
        # Test apikey= to=
        'instance': plugins.NotifyFCM,
    }),
    ('fcm://%20?to=device&keyfile=/invalid/path', {
        # invalid Project ID
        'instance': TypeError,
    }),
    ('fcm://project_id?to=device&keyfile=/invalid/path', {
        # Test to= and auto detection of oauth mode
        'instance': plugins.NotifyFCM,
        # we'll fail to send our notification as a result
        'response': False,
    }),
    ('fcm://?to=device&project=project_id&keyfile=/invalid/path', {
        # Test project= & to= and auto detection of oauth mode
        'instance': plugins.NotifyFCM,
        # we'll fail to send our notification as a result
        'response': False,
    }),
    ('fcm://project_id?to=device&mode=oauth2', {
        # no keyfile was specified
        'instance': TypeError,
    }),
    ('fcm://project_id?to=device&mode=oauth2&keyfile=/invalid/path', {
        # Same test as above except we explicitly set our oauth2 mode
        # Test to= and auto detection of oauth mode
        'instance': plugins.NotifyFCM,
        # we'll fail to send our notification as a result
        'response': False,
    }),
    ('fcm://apikey/#topic1/device/?mode=legacy', {
        'instance': plugins.NotifyFCM,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('fcm://apikey/#topic1/device/?mode=legacy', {
        'instance': plugins.NotifyFCM,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
    ('fcm://project/#topic1/device/?mode=oauth2&keyfile=file://{}'.format(
        os.path.join(
            os.path.dirname(__file__), 'var', 'fcm',
            'service_account.json')), {
                'instance': plugins.NotifyFCM,
                # throw a bizzare code forcing us to fail to look it up
                'response': False,
                'requests_response_code': 999,
    }),
    ('fcm://projectid/#topic1/device/?mode=oauth2&keyfile=file://{}'.format(
        os.path.join(
            os.path.dirname(__file__), 'var', 'fcm',
            'service_account.json')), {
                'instance': plugins.NotifyFCM,
                # Throws a series of connection and transfer exceptions when
                # this flag is set and tests that we gracfully handle them
                'test_requests_exceptions': True,
    }),
)


@pytest.mark.skipif(
    'cryptography' not in sys.modules, reason="Requires cryptography")
def test_plugin_fcm_urls():
    """
    NotifyFCM() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@pytest.mark.skipif(
    'cryptography' not in sys.modules, reason="Requires cryptography")
@mock.patch('requests.post')
def test_plugin_fcm_general(mock_post):
    """
    NotifyFCM() General Checks

    """

    # Valid Keyfile
    path = os.path.join(PRIVATE_KEYFILE_DIR, 'service_account.json')

    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare a good response
    response = mock.Mock()
    response.content = json.dumps({
        "access_token": "ya29.c.abcd",
        "expires_in": 3599,
        "token_type": "Bearer",
    })
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Test having a valid keyfile, but not a valid project id match
    obj = Apprise.instantiate(
        'fcm://invalid_project_id/device/?keyfile={}'.format(str(path)))
    # we'll fail as a result
    assert obj.notify("test") is False

    # Test our call count
    assert mock_post.call_count == 0

    # Now we test using a valid Project ID but we can't open our file
    obj = Apprise.instantiate(
        'fcm://mock-project-id/device/?keyfile={}'.format(str(path)))

    with mock.patch('io.open', side_effect=OSError):
        # we'll fail as a result
        assert obj.notify("test") is False

    # Test our call count
    assert mock_post.call_count == 0

    # Now we test using a valid Project ID
    obj = Apprise.instantiate(
        'fcm://mock-project-id/device/#topic/?keyfile={}'.format(str(path)))

    # we'll fail as a result
    assert obj.notify("test") is True

    # Test our call count
    assert mock_post.call_count == 3
    assert mock_post.call_args_list[0][0][0] == \
        'https://accounts.google.com/o/oauth2/token'
    assert mock_post.call_args_list[1][0][0] == \
        'https://fcm.googleapis.com/v1/projects/mock-project-id/messages:send'
    assert mock_post.call_args_list[2][0][0] == \
        'https://fcm.googleapis.com/v1/projects/mock-project-id/messages:send'


@pytest.mark.skipif(
    'cryptography' not in sys.modules, reason="Requires cryptography")
@mock.patch('requests.post')
def test_plugin_fcm_keyfile_parse(mock_post):
    """
    NotifyFCM() KeyFile Tests
    """

    # Prepare a good response
    response = mock.Mock()
    response.content = json.dumps({
        "access_token": "ya29.c.abcd",
        "expires_in": 3599,
        "token_type": "Bearer",
    })
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    path = os.path.join(PRIVATE_KEYFILE_DIR, 'service_account.json')
    oauth = GoogleOAuth()
    # We can not get an Access Token without content loaded
    assert oauth.access_token is None

    # Load our content
    assert oauth.load(path) is True
    assert oauth.access_token is not None

    # Test our call count
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'https://accounts.google.com/o/oauth2/token'

    mock_post.reset_mock()
    # a second call uses cache since our token hasn't expired yet
    assert oauth.access_token is not None
    assert mock_post.call_count == 0

    # Same test case without expires_in entry
    mock_post.reset_mock()
    response.content = json.dumps({
        "access_token": "ya29.c.abcd",
        "token_type": "Bearer",
    })

    oauth = GoogleOAuth()
    assert oauth.load(path) is True
    assert oauth.access_token is not None

    # Test our call count
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'https://accounts.google.com/o/oauth2/token'

    # Test user-agent override
    mock_post.reset_mock()
    oauth = GoogleOAuth(user_agent="test-agent-override")
    assert oauth.load(path) is True
    assert oauth.access_token is not None
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'https://accounts.google.com/o/oauth2/token'

    #
    # Test some errors that can get thrown when trying to handle
    # the service_account.json file
    #

    # Reset our object
    mock_post.reset_mock()

    # Now we test a case where we can't access the file we've been pointed to:
    oauth = GoogleOAuth()
    with mock.patch('io.open', side_effect=OSError):
        # We will fail to retrieve our Access Token
        assert oauth.load(path) is False
        assert oauth.access_token is None

    oauth = GoogleOAuth()
    with mock.patch('json.loads', side_effect=([], )):
        # We will fail to retrieve our Access Token since we did not parse
        # a dictionary
        assert oauth.load(path) is False
        assert oauth.access_token is None

    # Case where we can't load the PEM key:
    oauth = GoogleOAuth()
    with mock.patch(
            'cryptography.hazmat.primitives.serialization'
            '.load_pem_private_key',
            side_effect=ValueError("")):
        assert oauth.load(path) is False
        assert oauth.access_token is None

    # Case where we can't load the PEM key:
    oauth = GoogleOAuth()
    with mock.patch(
            'cryptography.hazmat.primitives.serialization'
            '.load_pem_private_key',
            side_effect=TypeError("")):
        assert oauth.load(path) is False
        assert oauth.access_token is None

    # Case where we can't load the PEM key:
    oauth = GoogleOAuth()
    with mock.patch(
            'cryptography.hazmat.primitives.serialization'
            '.load_pem_private_key',
            side_effect=UnsupportedAlgorithm("")):
        # Note: This test should be te
        assert oauth.load(path) is False
        assert oauth.access_token is None

    # Not one call was made to the web
    assert mock_post.call_count == 0

    #
    # Test some web errors that can occur when speaking upstream
    # with Google to get our token generated
    #
    response.status_code = requests.codes.internal_server_error

    mock_post.reset_mock()
    oauth = GoogleOAuth()
    assert oauth.load(path) is True

    # We'll fail due to an bad web response
    assert oauth.access_token is None

    # Return our status code to how it was
    response.status_code = requests.codes.ok

    # No access token
    bad_response_1 = mock.Mock()
    bad_response_1.content = json.dumps({
        "expires_in": 3599,
        "token_type": "Bearer",
    })

    # Invalid JSON
    bad_response_2 = mock.Mock()
    bad_response_2.content = '{'

    mock_post.return_value = None
    # Throw an exception on the first call to requests.post()
    for side_effect in (
            requests.RequestException(), bad_response_1, bad_response_2):
        mock_post.side_effect = side_effect

        # Test all of our bad side effects
        oauth = GoogleOAuth()
        assert oauth.load(path) is True

        # We'll fail due to an bad web response
        assert oauth.access_token is None


@pytest.mark.skipif(
    'cryptography' not in sys.modules, reason="Requires cryptography")
def test_plugin_fcm_bad_keyfile_parse():
    """
    NotifyFCM() KeyFile Bad Service Account Type Tests
    """

    path = os.path.join(PRIVATE_KEYFILE_DIR, 'service_account-bad-type.json')
    oauth = GoogleOAuth()
    assert oauth.load(path) is False


@pytest.mark.skipif(
    'cryptography' not in sys.modules, reason="Requires cryptography")
def test_plugin_fcm_keyfile_missing_entries_parse(tmpdir):
    """
    NotifyFCM() KeyFile Missing Entries Test
    """

    # Prepare a base keyfile reference to use
    path = os.path.join(PRIVATE_KEYFILE_DIR, 'service_account.json')
    with io.open(path, mode="r", encoding='utf-8') as fp:
        content = json.loads(fp.read())

    path = tmpdir.join('fcm_keyfile.json')

    # Test that we fail to load if the following keys are missing:
    for entry in (
            'client_email', 'private_key_id', 'private_key', 'type',
            'project_id'):

        # Ensure the key actually exists in our file
        assert entry in content

        # Create a copy of our content
        content_copy = content.copy()

        # Remove our entry we expect to validate against
        del content_copy[entry]
        assert entry not in content_copy

        path.write(json.dumps(content_copy))

        oauth = GoogleOAuth()
        assert oauth.load(str(path)) is False

    # Now write ourselves a bad JSON file
    path.write('{')
    oauth = GoogleOAuth()
    assert oauth.load(str(path)) is False


@pytest.mark.skipif(
    'cryptography' in sys.modules,
    reason="Requires that cryptography NOT be installed")
def test_plugin_fcm_cryptography_import_error():
    """
    NotifyFCM Cryptography loading failure
    """

    # Prepare a base keyfile reference to use
    path = os.path.join(PRIVATE_KEYFILE_DIR, 'service_account.json')

    # Attempt to instantiate our object
    obj = Apprise.instantiate(
        'fcm://mock-project-id/device/#topic/?keyfile={}'.format(str(path)))

    # It's not possible because our cryptography depedancy is missing
    assert obj is None
