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

from datetime import datetime
from json import dumps, loads

# Disable logging for a cleaner testing output
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.office365 import NotifyOffice365

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyOffice365
    ##################################
    (
        "o365://",
        {
            # Missing tenant, client_id, secret, and targets!
            "instance": TypeError,
        },
    ),
    (
        "o365://:@/",
        {
            # invalid url
            "instance": TypeError,
        },
    ),
    (
        "o365://{aid}/{tenant}/{cid}/{secret}/{targets}".format(
            # invalid tenant
            tenant=",",
            cid="ab-cd-ef-gh",
            aid="user@example.com",
            secret="abcd/123/3343/@jack/test",
            targets="/".join(["email1@test.ca"]),
        ),
        {
            # Expected failure
            "instance": TypeError,
        },
    ),
    (
        "o365://{aid}/{tenant}/{cid}/{secret}/{targets}".format(
            tenant="tenant",
            # invalid client id
            cid="ab.",
            aid="user2@example.com",
            secret="abcd/123/3343/@jack/test",
            targets="/".join(["email1@test.ca"]),
        ),
        {
            # Expected failure
            "instance": TypeError,
        },
    ),
    (
        "o365://{tenant}/{cid}/{secret}/{targets}".format(
            # email not required if mode is set to self
            tenant="tenant",
            cid="ab-cd-ef-gh",
            secret="abcd/123/3343/@jack/test",
            targets="/".join(["email1@test.ca"]),
        ),
        {
            # We're valid and good to go
            "instance": NotifyOffice365,
            # Test what happens if a batch send fails to return a messageCount
            "requests_response_text": {
                "expires_in": 2000,
                "access_token": "abcd1234",
                "mail": "user@example.ca",
            },
        },
    ),
    (
        "o365://{aid}/{tenant}/{cid}/{secret}/{targets}".format(
            tenant="tenant",
            cid="ab-cd-ef-gh",
            aid="user@example.edu",
            secret="abcd/123/3343/@jack/test",
            targets="/".join(["email1@test.ca"]),
        ),
        {
            # We're valid and good to go
            "instance": NotifyOffice365,
            # Test what happens if a batch send fails to return a messageCount
            "requests_response_text": {
                "expires_in": 2000,
                "access_token": "abcd1234",
                # For 'From:' Lookup
                "mail": "user@example.ca",
            },
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": (
                "azure://user@example.edu/t...t/a...h/****/email1@test.ca/"
            ),
        },
    ),
    (
        "o365://{aid}/{tenant}/{cid}/{secret}/{targets}".format(
            tenant="tenant",
            cid="ab-cd-ef-gh",
            # Source can also be Object ID
            aid="hg-fe-dc-ba",
            secret="abcd/123/3343/@jack/test",
            targets="/".join(["email1@test.ca"]),
        ),
        {
            # We're valid and good to go
            "instance": NotifyOffice365,
            # Test what happens if a batch send fails to return a messageCount
            "requests_response_text": {
                "expires_in": 2000,
                "access_token": "abcd1234",
                "mail": "user@example.ca",
                "displayName": "John",
            },
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": (
                "azure://hg-fe-dc-ba/t...t/a...h/****/email1@test.ca/"
            ),
        },
    ),
    # ObjectID Specified, but no targets
    (
        "o365://{aid}/{tenant}/{cid}/{secret}/".format(
            tenant="tenant",
            cid="ab-cd-ef-gh",
            # Source can also be Object ID
            aid="hg-fe-dc-ba",
            secret="abcd/123/3343/@jack/test",
        ),
        {
            # We're valid and good to go
            "instance": NotifyOffice365,
            # Test what happens if a batch send fails to return a messageCount
            "requests_response_text": {
                "expires_in": 2000,
                "access_token": "abcd1234",
                "mail": "user@example.ca",
            },
            # No emails detected
            "notify_response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "azure://hg-fe-dc-ba/t...t/a...h/****",
        },
    ),
    # ObjectID Specified, but no targets
    (
        "o365://{aid}/{tenant}/{cid}/{secret}/".format(
            tenant="tenant",
            cid="ab-cd-ef-gh",
            # Source can also be Object ID
            aid="hg-fe-dc-ba",
            secret="abcd/123/3343/@jack/test",
        ),
        {
            # We're valid and good to go
            "instance": NotifyOffice365,
            # Test what happens if a batch send fails to return a messageCount
            "requests_response_text": {
                "expires_in": 2000,
                "access_token": "abcd1234",
                "userPrincipalName": "user@example.ca",
            },
            # No emails detected
            "notify_response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "azure://hg-fe-dc-ba/t...t/a...h/****",
        },
    ),
    # test our arguments
    (
        "o365://_/?oauth_id={cid}&oauth_secret={secret}&tenant={tenant}"
        "&to={targets}&from={aid}".format(
            tenant="tenant",
            cid="ab-cd-ef-gh",
            aid="user@example.ca",
            secret="abcd/123/3343/@jack/test",
            targets="email1@test.ca",
        ),
        {
            # We're valid and good to go
            "instance": NotifyOffice365,
            # Test what happens if a batch send fails to return a messageCount
            "requests_response_text": {
                "expires_in": 2000,
                "access_token": "abcd1234",
                "mail": "user@example.ca",
            },
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": (
                "azure://user@example.ca/t...t/a...h/****/email1@test.ca/"
            ),
        },
    ),
    # Test invalid JSON (no tenant defaults to email domain)
    (
        "o365://{aid}/{tenant}/{cid}/{secret}/{targets}".format(
            tenant="tenant",
            cid="ab-cd-ef-gh",
            aid="user@example.com",
            secret="abcd/123/3343/@jack/test",
            targets="/".join(["email1@test.ca"]),
        ),
        {
            # We're valid and good to go
            "instance": NotifyOffice365,
            # invalid JSON response
            "requests_response_text": "{",
            "notify_response": False,
        },
    ),
    # No Targets specified
    (
        "o365://{aid}/{tenant}/{cid}/{secret}".format(
            tenant="tenant",
            cid="ab-cd-ef-gh",
            aid="user@example.com",
            secret="abcd/123/3343/@jack/test",
        ),
        {
            # We're valid and good to go
            "instance": NotifyOffice365,
            # There were no targets to notify; so we use our own email
            "requests_response_text": {
                "expires_in": 2000,
                "access_token": "abcd1234",
                "userPrincipalName": "user@example.ca",
            },
        },
    ),
    (
        "o365://{aid}/{tenant}/{cid}/{secret}/{targets}".format(
            tenant="tenant",
            cid="zz-zz-zz-zz",
            aid="user@example.com",
            secret="abcd/abc/dcba/@john/test",
            targets="/".join(["email1@test.ca"]),
        ),
        {
            "instance": NotifyOffice365,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "o365://{tenant}:{aid}/{cid}/{secret}/{targets}".format(
            tenant="tenant",
            cid="01-12-23-34",
            aid="user@example.com",
            secret="abcd/321/4321/@test/test",
            targets="/".join(["email1@test.ca"]),
        ),
        {
            "instance": NotifyOffice365,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_office365_urls():
    """NotifyOffice365() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_office365_general(mock_get, mock_post):
    """NotifyOffice365() General Testing."""

    # Initialize some generic (but valid) tokens
    email = "user@example.net"
    tenant = "ff-gg-hh-ii-jj"
    client_id = "aa-bb-cc-dd-ee"
    secret = "abcd/1234/abcd@ajd@/test"
    targets = "target@example.com"

    # Prepare Mock return object
    payload = {
        "token_type": "Bearer",
        "expires_in": 6000,
        "access_token": "abcd1234",
        # For 'From:' Lookup
        "mail": "abc@example.ca",
        # For our Draft Email ID:
        "id": "draft-id-no",
    }
    response = mock.Mock()
    response.content = dumps(payload)
    response.status_code = requests.codes.ok
    mock_post.return_value = response
    mock_get.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate(f"o365://{email}/{tenant}/{secret}/{targets}")

    assert isinstance(obj, NotifyOffice365)

    # Test our URL generation
    assert isinstance(obj.url(), str)

    # Test our notification
    assert obj.notify(title="title", body="test") is True

    # Instantiate our object
    obj = Apprise.instantiate(
        "o365://{email}/{tenant}/{client_id}/{secret}/{targets}"
        "?bcc={bcc}&cc={cc}".format(
            tenant=tenant,
            email=email,
            client_id=client_id,
            secret=secret,
            targets=targets,
            # Test the cc and bcc list (use good and bad email)
            cc="Chuck Norris cnorris@yahoo.ca, Sauron@lotr.me, invalid@!",
            bcc="Bruce Willis bwillis@hotmail.com, Frodo@lotr.me invalid@!",
        )
    )

    assert isinstance(obj, NotifyOffice365)

    # Test our URL generation
    assert isinstance(obj.url(), str)

    # Test our notification
    assert obj.notify(title="title", body="test") is True

    with pytest.raises(TypeError):
        # No secret
        NotifyOffice365(
            email=email,
            client_id=client_id,
            tenant=tenant,
            secret=None,
            targets=None,
        )

    # One of the targets are invalid
    obj = NotifyOffice365(
        email=email,
        client_id=client_id,
        tenant=tenant,
        secret=secret,
        targets=("Management abc@gmail.com", "garbage"),
    )
    # Test our notification (this will work and only notify abc@gmail.com)
    assert obj.notify(title="title", body="test") is True

    # all of the targets are invalid
    obj = NotifyOffice365(
        email=email,
        client_id=client_id,
        tenant=tenant,
        secret=secret,
        targets=("invalid", "garbage"),
    )

    # Test our notification (which will fail because of no entries)
    assert obj.notify(title="title", body="test") is False


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_office365_authentication(mock_get, mock_post):
    """NotifyOffice365() Authentication Testing."""

    # Initialize some generic (but valid) tokens
    tenant = "ff-gg-hh-ii-jj"
    email = "user@example.net"
    client_id = "aa-bb-cc-dd-ee"
    secret = "abcd/1234/abcd@ajd@/test"
    targets = "target@example.com"

    # Prepare Mock return object
    authentication_okay = {
        "token_type": "Bearer",
        "expires_in": 6000,
        "access_token": "abcd1234",
    }
    authentication_failure = {
        "error": "invalid_scope",
        "error_description": "AADSTS70011: Blah... Blah Blah... Blah",
        "error_codes": [70011],
        "timestamp": "2020-01-09 02:02:12Z",
        "trace_id": "255d1aef-8c98-452f-ac51-23d051240864",
        "correlation_id": "fb3d2015-bc17-4bb9-bb85-30c5cf1aaaa7",
    }
    response = mock.Mock()
    response.content = dumps(authentication_okay)
    response.status_code = requests.codes.ok
    mock_post.return_value = response
    mock_get.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate(
        f"azure://{email}/{tenant}/{client_id}/{secret}/{targets}"
    )

    assert isinstance(obj, NotifyOffice365)

    # Authenticate
    assert obj.authenticate() is True

    # We're already authenticated
    assert obj.authenticate() is True

    # Expire our token
    obj.token_expiry = datetime.now()

    # Re-authentiate
    assert obj.authenticate() is True

    # Change our response
    response.status_code = 400

    # We'll fail to send a notification now...
    assert obj.notify(title="title", body="test") is False

    # Expire our token
    obj.token_expiry = datetime.now()

    # Set a failure response
    response.content = dumps(authentication_failure)

    # We will fail to authenticate at this point
    assert obj.authenticate() is False

    # Notifications will also fail in this case
    assert obj.notify(title="title", body="test") is False

    # We will fail to authenticate with invalid data

    invalid_auth_entries = authentication_okay.copy()
    invalid_auth_entries["expires_in"] = "garbage"
    response.content = dumps(invalid_auth_entries)
    response.status_code = requests.codes.ok
    assert obj.authenticate() is False

    invalid_auth_entries["expires_in"] = None
    response.content = dumps(invalid_auth_entries)
    assert obj.authenticate() is False

    invalid_auth_entries["expires_in"] = ""
    response.content = dumps(invalid_auth_entries)
    assert obj.authenticate() is False

    del invalid_auth_entries["expires_in"]
    response.content = dumps(invalid_auth_entries)
    assert obj.authenticate() is False


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_office365_queries(mock_post, mock_get, mock_put):
    """NotifyOffice365() General Queries."""

    # Initialize some generic (but valid) tokens
    source = "abc-1234-object-id"
    tenant = "ff-gg-hh-ii-jj"
    client_id = "aa-bb-cc-dd-ee"
    secret = "abcd/1234/abcd@ajd@/test"
    targets = "target@example.ca"

    # Prepare Mock return object
    payload = {
        "token_type": "Bearer",
        "expires_in": 6000,
        "access_token": "abcd1234",
        # For 'From:' Lookup (email)
        "mail": "user@example.edu",
        # For 'From:' Lookup (name)
        "displayName": "John",
        # For our Draft Email ID:
        "id": "draft-id-no",
        # For FIle Uploads
        "uploadUrl": "https://my.url.path/",
    }

    okay_response = mock.Mock()
    okay_response.content = dumps(payload)
    okay_response.status_code = requests.codes.ok
    mock_post.return_value = okay_response
    mock_put.return_value = okay_response

    bad_response = mock.Mock()
    bad_response.content = dumps(payload)
    bad_response.status_code = requests.codes.forbidden

    # Assign our GET a bad response so we fail to look up the user
    mock_get.return_value = bad_response

    # Instantiate our object
    obj = Apprise.instantiate(
        f"azure://{source}/{tenant}/{client_id}{secret}/{targets}"
    )

    assert isinstance(obj, NotifyOffice365)

    # We can still send a notification even if we can't look up the email
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://graph.microsoft.com/v1.0/users/abc-1234-object-id/sendMail"
    )
    payload = loads(mock_post.call_args_list[1][1]["data"])
    assert payload == {
        "message": {
            "subject": "title",
            "body": {
                "contentType": "HTML",
                "content": "body",
            },
            "toRecipients": [
                {"emailAddress": {"address": "target@example.ca"}}
            ],
        },
        "saveToSentItems": "true",
    }
    mock_post.reset_mock()

    # Now test a case where we just couldn't get any email details from the
    # payload returned

    # Prepare Mock return object
    temp_payload = {
        "token_type": "Bearer",
        "expires_in": 6000,
        "access_token": "abcd1234",
        # For our Draft Email ID:
        "id": "draft-id-no",
        # For FIle Uploads
        "uploadUrl": "https://my.url.path/",
    }

    bad_response.content = dumps(temp_payload)
    bad_response.status_code = requests.codes.okay
    mock_get.return_value = bad_response

    obj = Apprise.instantiate(
        f"azure://{source}/{tenant}/{client_id}{secret}/{targets}"
    )

    assert isinstance(obj, NotifyOffice365)

    # We can still send a notification even if we can't look up the email
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_office365_attachments(mock_post, mock_get, mock_put):
    """NotifyOffice365() Attachments."""

    # Initialize some generic (but valid) tokens
    source = "user@example.net"
    tenant = "ff-gg-hh-ii-jj"
    client_id = "aa-bb-cc-dd-ee"
    secret = "abcd/1234/abcd@ajd@/test"
    targets = "target@example.com"

    # Prepare Mock return object
    payload = {
        "token_type": "Bearer",
        "expires_in": 6000,
        "access_token": "abcd1234",
        # For 'From:' Lookup
        "mail": "user@example.edu",
        # For our Draft Email ID:
        "id": "draft-id-no",
        # For FIle Uploads
        "uploadUrl": "https://my.url.path/",
    }
    okay_response = mock.Mock()
    okay_response.content = dumps(payload)
    okay_response.status_code = requests.codes.ok
    mock_post.return_value = okay_response
    mock_get.return_value = okay_response
    mock_put.return_value = okay_response

    # Instantiate our object
    obj = Apprise.instantiate(
        f"azure://{source}/{tenant}/{client_id}{secret}/{targets}"
    )

    assert isinstance(obj, NotifyOffice365)

    # Test Valid Attachment
    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    )
    assert (
        mock_post.call_args_list[0][1]["headers"].get("Content-Type")
        == "application/x-www-form-urlencoded"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == f"https://graph.microsoft.com/v1.0/users/{source}/sendMail"
    )
    assert (
        mock_post.call_args_list[1][1]["headers"].get("Content-Type")
        == "application/json"
    )
    mock_post.reset_mock()

    # Test Authentication Failure
    obj = Apprise.instantiate(
        "azure://{source}/{tenant}/{client_id}{secret}/{targets}".format(
            client_id=client_id,
            tenant=tenant,
            source="object-id-requiring-lookup",
            secret=secret,
            targets=targets,
        )
    )

    bad_response = mock.Mock()
    bad_response.content = dumps(payload)
    bad_response.status_code = requests.codes.forbidden
    mock_post.return_value = bad_response

    assert isinstance(obj, NotifyOffice365)
    # Authentication will fail
    assert (
        obj.notify(
            body="auth-fail", title="title", notify_type=NotifyType.INFO
        )
        is False
    )
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://login.microsoftonline.com/ff-gg-hh-ii-jj/oauth2/v2.0/token"
    )
    mock_post.reset_mock()

    #
    # Test invalid attachment
    #

    # Instantiate our object
    obj = Apprise.instantiate(
        f"azure://{source}/{tenant}/{client_id}{secret}/{targets}"
    )

    assert isinstance(obj, NotifyOffice365)

    mock_post.return_value = okay_response
    path = os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=path,
        )
        is False
    )
    assert mock_post.call_count == 0
    mock_post.reset_mock()

    with mock.patch("base64.b64encode", side_effect=OSError()):
        # We can't send the message if we fail to parse the data
        assert (
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
            is False
        )
    assert mock_post.call_count == 0
    mock_post.reset_mock()

    #
    # Test case where we can't authenticate
    #
    obj = Apprise.instantiate(
        f"azure://{source}/{tenant}/{client_id}{secret}/{targets}"
    )

    # Force a smaller attachment size forcing us to create an attachment
    obj.outlook_attachment_inline_max = 50

    assert isinstance(obj, NotifyOffice365)

    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    mock_post.return_value = bad_response
    assert obj.upload_attachment(attach[0], "id") is False
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://login.microsoftonline.com/ff-gg-hh-ii-jj/oauth2/v2.0/token"
    )

    mock_post.reset_mock()

    mock_post.side_effect = (okay_response, bad_response)
    mock_post.return_value = None
    assert obj.upload_attachment(attach[0], "id") is False
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://login.microsoftonline.com/ff-gg-hh-ii-jj/oauth2/v2.0/token"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == f"https://graph.microsoft.com/v1.0/users/{source}/"
        + "message/id/attachments/createUploadSession"
    )

    mock_post.reset_mock()
    # Return our status
    mock_post.side_effect = None

    # Prepare Mock return object
    payload_no_upload_url = {
        "token_type": "Bearer",
        "expires_in": 6000,
        "access_token": "abcd1234",
        # For 'From:' Lookup
        "mail": "user@example.edu",
        # For our Draft Email ID:
        "id": "draft-id-no",
    }
    tmp_response = mock.Mock()
    tmp_response.content = dumps(payload_no_upload_url)
    tmp_response.status_code = requests.codes.ok
    mock_post.return_value = tmp_response

    assert obj.upload_attachment(attach[0], "id") is False
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://graph.microsoft.com/v1.0/users/{source}/"
        + "message/id/attachments/createUploadSession"
    )

    mock_post.reset_mock()
    # Return our status
    mock_post.side_effect = None
    mock_post.return_value = okay_response

    obj = Apprise.instantiate(
        f"azure://{source}/{tenant}/{client_id}{secret}/{targets}"
    )

    # Force a smaller attachment size forcing us to create an attachment
    obj.outlook_attachment_inline_max = 50

    assert isinstance(obj, NotifyOffice365)

    # We now have to prepare sepparate session attachments using draft emails
    assert (
        obj.notify(
            body="body",
            title="title-test",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Large Attachments
    assert mock_post.call_count == 4
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://login.microsoftonline.com/ff-gg-hh-ii-jj/oauth2/v2.0/token"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == f"https://graph.microsoft.com/v1.0/users/{source}/messages"
    )
    assert (
        mock_post.call_args_list[2][0][0]
        == f"https://graph.microsoft.com/v1.0/users/{source}/"
        + "message/draft-id-no/attachments/createUploadSession"
    )
    assert (
        mock_post.call_args_list[3][0][0]
        == f"https://graph.microsoft.com/v1.0/users/{source}/sendMail"
    )
    mock_post.reset_mock()

    #
    # Handle another case where can't upload the attachment at all
    #
    path = os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    bad_attach = AppriseAttachment(path)
    assert obj.upload_attachment(bad_attach[0], "id") is False

    mock_post.reset_mock()
    #
    # Handle test case where we can't send the draft email after everything
    # has been prepared
    #
    mock_post.return_value = None
    mock_post.side_effect = (okay_response, okay_response, bad_response)
    assert (
        obj.notify(
            body="body",
            title="title-test",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    assert mock_post.call_count == 3
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://graph.microsoft.com/v1.0/users/{source}/messages"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == f"https://graph.microsoft.com/v1.0/users/{source}/"
        + "message/draft-id-no/attachments/createUploadSession"
    )
    assert (
        mock_post.call_args_list[2][0][0]
        == f"https://graph.microsoft.com/v1.0/users/{source}/sendMail"
    )
    mock_post.reset_mock()
    mock_post.side_effect = None
    mock_post.return_value = okay_response

    #
    # Handle test case where we can not upload chunks
    #
    mock_put.return_value = bad_response

    # We now have to prepare sepparate session attachments using draft emails
    assert (
        obj.notify(
            body="body",
            title="title-no-chunk",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://graph.microsoft.com/v1.0/users/{source}/messages"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == f"https://graph.microsoft.com/v1.0/users/{source}/"
        + "message/draft-id-no/attachments/createUploadSession"
    )

    mock_put.return_value = okay_response
    mock_post.reset_mock()

    # Prepare Mock return object
    payload_missing_id = {
        "token_type": "Bearer",
        "expires_in": 6000,
        "access_token": "abcd1234",
        # For 'From:' Lookup
        "mail": "user@example.edu",
        # For FIle Uploads
        "uploadUrl": "https://my.url.path/",
    }
    temp_response = mock.Mock()
    temp_response.content = dumps(payload_missing_id)
    temp_response.status_code = requests.codes.ok
    mock_post.return_value = temp_response

    # We could not acquire an attachment id, so we'll fail to send our
    # notification
    assert (
        obj.notify(
            body="body",
            title="title-test",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    # Large Attachments
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://graph.microsoft.com/v1.0/users/user@example.net/messages"
    )

    mock_post.reset_mock()

    # Reset attachment size
    obj.outlook_attachment_inline_max = 50 * 1024 * 1024
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # already authenticated
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://graph.microsoft.com/v1.0/users/{source}/sendMail"
    )
    mock_post.reset_mock()
