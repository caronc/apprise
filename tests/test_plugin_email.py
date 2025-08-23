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
from email.header import decode_header
from inspect import cleandoc
import logging
import os
import re
import shutil
import smtplib
import sys
from unittest import mock

import pytest

from apprise import (
    Apprise,
    AppriseAsset,
    AppriseAttachment,
    AttachBase,
    NotifyBase,
    NotifyType,
    PersistentStoreMode,
    utils,
)
from apprise.config import ConfigBase
from apprise.exception import AppriseException
from apprise.plugins import email

try:
    import pgpy
except ImportError:
    pgpy = None

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

TEST_URLS = (
    ##################################
    # NotifyEmail
    ##################################
    (
        "mailto://",
        {
            "instance": TypeError,
        },
    ),
    (
        "mailtos://",
        {
            "instance": TypeError,
        },
    ),
    (
        "mailto://:@/",
        {
            "instance": TypeError,
        },
    ),
    # No Username
    (
        "mailtos://:pass@nuxref.com:567",
        {
            # Can't prepare a To address using this expression
            "instance": TypeError,
        },
    ),
    (
        # invalid Timezone
        "mailto://user:pass@fastmail.com?tz=invalid",
        {
            # An error is thrown for this
            "instance": TypeError,
        },
    ),
    # Pre-Configured Email Services
    (
        "mailto://user:pass@gmail.com",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailto://user:pass@hotmail.com",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailto://user:pass@live.com",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailto://user:pass@prontomail.com",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailto://user:pass@yahoo.com",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailto://user:pass@yahoo.ca",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailto://user:pass@fastmail.com?tz=UTC",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailto://user:pass@sendgrid.com",
        {
            "instance": email.NotifyEmail,
        },
    ),
    # Yandex
    (
        "mailto://user:pass@yandex.com",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailto://user:pass@yandex.ru",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailto://user:pass@yandex.fr",
        {
            "instance": email.NotifyEmail,
        },
    ),
    # Custom Emails
    (
        "mailtos://user:pass@nuxref.com:567",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailto://user:pass@nuxref.com?mode=ssl",
        {
            # mailto:// with mode=ssl causes us to convert to ssl
            "instance": email.NotifyEmail,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mailtos://user:****@nuxref.com",
        },
    ),
    (
        "mailto://user:pass@nuxref.com:567?format=html",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailtos://user:pass@nuxref.com:567?to=l2g@nuxref.com",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailtos://user:pass@domain.com?user=admin@mail-domain.com",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailtos://%20@domain.com?user=admin@mail-domain.com",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailtos://%20@domain.com?user=admin@mail-domain.com?pgp=yes",
        {
            # Test pgp flag
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailtos://user:pass@nuxref.com:567/l2g@nuxref.com",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        (
            "mailto://user:pass@example.com:2525?user=l2g@example.com"
            "&pass=l2g@apprise!is!Awesome"
        ),
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        (
            "mailto://user:pass@example.com:2525?user=l2g@example.com"
            "&pass=l2g@apprise!is!Awesome&format=text"
        ),
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        # Test Carbon Copy
        (
            "mailtos://user:pass@example.com?smtp=smtp.example.com"
            "&name=l2g&cc=noreply@example.com,test@example.com"
        ),
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        # Test Blind Carbon Copy
        (
            "mailtos://user:pass@example.com?smtp=smtp.example.com"
            "&name=l2g&bcc=noreply@example.com,test@example.com"
        ),
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        # Test Carbon Copy with bad email
        (
            "mailtos://user:pass@example.com?smtp=smtp.example.com"
            "&name=l2g&cc=noreply@example.com,@"
        ),
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        # Test Blind Carbon Copy with bad email
        (
            "mailtos://user:pass@example.com?smtp=smtp.example.com"
            "&name=l2g&bcc=noreply@example.com,@"
        ),
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        # Test Reply To
        (
            "mailtos://user:pass@example.com?smtp=smtp.example.com"
            "&name=l2g&reply=test@example.com,test2@example.com"
        ),
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        # Test Reply To with bad email
        (
            "mailtos://user:pass@example.com?smtp=smtp.example.com"
            "&name=l2g&reply=test@example.com,@"
        ),
        {
            "instance": email.NotifyEmail,
        },
    ),
    # headers
    (
        (
            "mailto://user:pass@localhost.localdomain"
            "?+X-Customer-Campaign-ID=Apprise"
        ),
        {
            "instance": email.NotifyEmail,
        },
    ),
    # No Password
    (
        "mailtos://user:@nuxref.com",
        {
            "instance": email.NotifyEmail,
        },
    ),
    # Invalid From Address; but just gets put as the from name instead
    # Hence the below generats From: "@ <user@nuxref.com>"
    (
        "mailtos://user:pass@nuxref.com?from=@",
        {
            "instance": email.NotifyEmail,
        },
    ),
    # Invalid From Address
    (
        "mailtos://nuxref.com?user=&pass=.",
        {
            "instance": TypeError,
        },
    ),
    # Invalid To Address is accepted, but we won't be able to properly email
    # using the notify() call
    (
        "mailtos://user:pass@nuxref.com?to=@",
        {
            "instance": email.NotifyEmail,
            "response": False,
        },
    ),
    # Valid URL, but can't structure a proper email
    (
        'mailtos://nuxref.com?user=%20"&pass=.',
        {
            "instance": TypeError,
        },
    ),
    # Invalid From (and To) Address
    (
        "mailtos://nuxref.com?to=test",
        {
            "instance": TypeError,
        },
    ),
    # Invalid Secure Mode
    (
        "mailtos://user:pass@example.com?mode=notamode",
        {
            "instance": TypeError,
        },
    ),
    # STARTTLS flag checking
    (
        "mailtos://user:pass@gmail.com?mode=starttls",
        {
            "instance": email.NotifyEmail,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mailtos://user:****@gmail.com",
        },
    ),
    # SSL flag checking
    (
        "mailtos://user:pass@gmail.com?mode=ssl",
        {
            "instance": email.NotifyEmail,
        },
    ),
    # Can make a To address using what we have (l2g@nuxref.com)
    (
        "mailtos://nuxref.com?user=l2g&pass=.",
        {
            "instance": email.NotifyEmail,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mailtos://l2g:****@nuxref.com",
        },
    ),
    (
        "mailto://user:pass@localhost:2525",
        {
            "instance": email.NotifyEmail,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_smtplib_exceptions": True,
        },
    ),
    # Use of both 'name' and 'from' together; these are synonymous
    (
        (
            "mailtos://user:pass@nuxref.com?"
            "from=jack@gmail.com&name=Jason<jason@gmail.com>"
        ),
        {"instance": email.NotifyEmail},
    ),
    # Test no auth at all
    (
        "mailto://localhost?from=test@example.com&to=test@example.com",
        {
            "instance": email.NotifyEmail,
            "privacy_url": "mailto://localhost",
        },
    ),
    # Test multi-emails where some are bad
    (
        "mailto://user:pass@localhost/test@example.com/test2@/$@!/",
        {
            "instance": email.NotifyEmail,
            "privacy_url": "mailto://user:****@localhost/",
        },
    ),
    (
        "mailto://user:pass@localhost/?bcc=test2@,$@!/",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailto://user:pass@localhost/?cc=test2@,$@!/",
        {
            "instance": email.NotifyEmail,
        },
    ),
    (
        "mailto://user:pass@localhost/?reply=test2@,$@!/",
        {
            "instance": email.NotifyEmail,
        },
    ),
)


@mock.patch("smtplib.SMTP")
@mock.patch("smtplib.SMTP_SSL")
def test_plugin_email(mock_smtp, mock_smtpssl):
    """NotifyEmail() General Checks."""

    # iterate over our dictionary and test it out
    for url, meta in TEST_URLS:

        # Our expected instance
        instance = meta.get("instance", None)

        # Our expected server objects
        self = meta.get("self", None)

        # Our expected Query response (True, False, or exception type)
        response = meta.get("response", True)

        # Our expected privacy url
        # Don't set this if don't need to check it's value
        privacy_url = meta.get("privacy_url")

        test_smtplib_exceptions = meta.get("test_smtplib_exceptions", False)

        # Our mock of our socket action
        mock_socket = mock.Mock()
        mock_socket.starttls.return_value = True
        mock_socket.login.return_value = True

        # Create a mock SMTP Object
        mock_smtp.return_value = mock_socket
        mock_smtpssl.return_value = mock_socket

        if test_smtplib_exceptions:
            # Handle exception testing; first we turn the boolean flag ito
            # a list of exceptions
            test_smtplib_exceptions = (
                smtplib.SMTPHeloError(
                    0, "smtplib.SMTPHeloError() not handled"
                ),
                smtplib.SMTPException(
                    0, "smtplib.SMTPException() not handled"
                ),
                RuntimeError(0, "smtplib.HTTPError() not handled"),
                smtplib.SMTPRecipientsRefused(
                    "smtplib.SMTPRecipientsRefused() not handled"
                ),
                smtplib.SMTPSenderRefused(
                    0,
                    "smtplib.SMTPSenderRefused() not handled",
                    "addr@example.com",
                ),
                smtplib.SMTPDataError(
                    0, "smtplib.SMTPDataError() not handled"
                ),
                smtplib.SMTPServerDisconnected(
                    "smtplib.SMTPServerDisconnected() not handled"
                ),
            )

        try:
            obj = Apprise.instantiate(url, suppress_exceptions=False)

            if obj is None:
                # We're done (assuming this is what we were expecting)
                assert instance is None
                continue

            if instance is None:
                # Expected None but didn't get it
                raise AssertionError()

            assert isinstance(obj, instance)

            if isinstance(obj, NotifyBase):
                # We loaded okay; now lets make sure we can reverse this url
                assert isinstance(obj.url(), str)

                # Get our URL Identifier
                assert isinstance(obj.url_id(), str)

                # Verify we can acquire a target count as an integer
                assert isinstance(len(obj), int)

                # Test url() with privacy=True
                assert isinstance(obj.url(privacy=True), str)

                # Some Simple Invalid Instance Testing
                assert instance.parse_url(None) is None
                assert instance.parse_url(object) is None
                assert instance.parse_url(42) is None

                if privacy_url:
                    # Assess that our privacy url is as expected
                    assert obj.url(privacy=True).startswith(privacy_url)

                # Instantiate the exact same object again using the URL from
                # the one that was already created properly
                obj_cmp = Apprise.instantiate(obj.url())

                # Our object should be the same instance as what we had
                # originally expected above.
                if not isinstance(obj_cmp, NotifyBase):
                    # Assert messages are hard to trace back with the way
                    # these tests work. Just printing before throwing our
                    # assertion failure makes things easier to debug later on
                    raise AssertionError()

                # Verify there is no change from the old and the new
                assert len(obj) == len(obj_cmp), (
                    f"{len(obj)} targets found in "
                    f"{obj.url(privacy=True)}, "
                    f"But {len(obj_cmp)} targets found in "
                    f"{obj_cmp.url(privacy=True)}"
                )
            if self:
                # Iterate over our expected entries inside of our object
                for key, val in self.items():
                    # Test that our object has the desired key
                    assert hasattr(key, obj)
                    assert getattr(key, obj) == val

            try:
                if test_smtplib_exceptions is False:
                    # Verify we can acquire a target count as an integer
                    targets = len(obj)

                    # check that we're as expected
                    assert (
                        obj.notify(
                            title="test",
                            body="body",
                            notify_type=NotifyType.INFO,
                        )
                        == response
                    )

                    if response:
                        # If we successfully got a response, there must have
                        # been at least 1 target present
                        assert targets > 0

                else:
                    for exception in test_smtplib_exceptions:
                        mock_socket.sendmail.side_effect = exception
                        try:
                            assert (
                                obj.notify(
                                    title="test",
                                    body="body",
                                    notify_type=NotifyType.INFO,
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
                if not isinstance(e, response):
                    raise

        except AssertionError:
            # Don't mess with these entries
            raise

        except Exception as e:
            # Handle our exception
            if instance is None:
                raise

            if not isinstance(e, instance):
                raise


@mock.patch("smtplib.SMTP")
@mock.patch("smtplib.SMTP_SSL")
def test_plugin_email_webbase_lookup(mock_smtp, mock_smtpssl):
    """NotifyEmail() Web Based Lookup Tests."""

    # Insert a test email at the head of our table
    email.templates.EMAIL_TEMPLATES = (
        *(
            (
                "Testing Lookup",
                re.compile(r"^(?P<id>[^@]+)@(?P<domain>l2g\.com)$", re.I),
                {
                    "port": 123,
                    "smtp_host": "smtp.l2g.com",
                    "secure": True,
                    "login_type": (email.WebBaseLogin.USERID,),
                },
            ),
        ),
        *email.templates.EMAIL_TEMPLATES,
    )

    obj = Apprise.instantiate(
        "mailto://user:pass@l2g.com",
        suppress_exceptions=True,
    )

    assert isinstance(obj, email.NotifyEmail)
    assert len(obj.targets) == 1
    assert (False, "user@l2g.com") in obj.targets
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == "user@l2g.com"
    assert obj.password == "pass"
    assert obj.user == "user"
    assert obj.secure is True
    assert obj.port == 123
    assert obj.smtp_host == "smtp.l2g.com"

    # We get the same results if an email is identified as the username
    # because the USERID variable forces that we can't use an email
    obj = Apprise.instantiate(
        "mailto://_:pass@l2g.com?user=user@test.com", suppress_exceptions=True
    )
    assert obj.user == "user"


@mock.patch("smtplib.SMTP")
def test_plugin_email_smtplib_init_fail(mock_smtplib):
    """NotifyEmail() Test exception handling when calling smtplib.SMTP()"""

    obj = Apprise.instantiate(
        "mailto://user:pass@gmail.com", suppress_exceptions=False
    )
    assert isinstance(obj, email.NotifyEmail)

    # Support Exception handling of smtplib.SMTP
    mock_smtplib.side_effect = RuntimeError("Test")

    assert (
        obj.notify(body="body", title="test", notify_type=NotifyType.INFO)
        is False
    )

    # A handled and expected exception
    mock_smtplib.side_effect = smtplib.SMTPException("Test")
    assert (
        obj.notify(body="body", title="test", notify_type=NotifyType.INFO)
        is False
    )


@mock.patch("smtplib.SMTP")
def test_plugin_email_smtplib_send_okay(mock_smtplib):
    """NotifyEmail() Test a successfully sent email."""

    # Defaults to HTML
    obj = Apprise.instantiate(
        "mailto://user:pass@gmail.com", suppress_exceptions=False
    )
    assert isinstance(obj, email.NotifyEmail)

    # Support an email simulation where we can correctly quit
    mock_smtplib.starttls.return_value = True
    mock_smtplib.login.return_value = True
    mock_smtplib.sendmail.return_value = True
    mock_smtplib.quit.return_value = True

    assert (
        obj.notify(body="body", title="test", notify_type=NotifyType.INFO)
        is True
    )

    # Set Text
    obj = Apprise.instantiate(
        "mailto://user:pass@gmail.com?format=text", suppress_exceptions=False
    )
    assert isinstance(obj, email.NotifyEmail)

    assert (
        obj.notify(body="body", title="test", notify_type=NotifyType.INFO)
        is True
    )

    # Create an apprise object to work with as well
    a = Apprise()
    assert a.add("mailto://user:pass@gmail.com?format=text")

    # Send Attachment with success
    attach = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    assert (
        obj.notify(
            body="body",
            title="test",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # same results happen from our Apprise object
    assert a.notify(body="body", title="test", attach=attach) is True

    # test using an Apprise Attachment object
    assert (
        obj.notify(
            body="body",
            title="test",
            notify_type=NotifyType.INFO,
            attach=AppriseAttachment(attach),
        )
        is True
    )

    # same results happen from our Apprise object
    assert (
        a.notify(body="body", title="test", attach=AppriseAttachment(attach))
        is True
    )

    max_file_size = AttachBase.max_file_size
    # Now do a case where the file can't be sent

    AttachBase.max_file_size = 1
    assert (
        obj.notify(
            body="body",
            title="test",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    # same results happen from our Apprise object
    assert a.notify(body="body", title="test", attach=attach) is False

    # Restore value
    AttachBase.max_file_size = max_file_size


@mock.patch("smtplib.SMTP")
def test_plugin_email_smtplib_send_multiple_recipients(mock_smtplib):
    """Verify that NotifyEmail() will use a single SMTP session for submitting
    multiple emails."""

    # Defaults to HTML
    obj = Apprise.instantiate(
        "mailto://user:pass@mail.example.org?"
        "to=foo@example.net,bar@example.com&"
        "cc=baz@example.org&bcc=qux@example.org",
        suppress_exceptions=False,
    )
    assert isinstance(obj, email.NotifyEmail)

    assert (
        obj.notify(body="body", title="test", notify_type=NotifyType.INFO)
        is True
    )

    assert mock_smtplib.mock_calls == [
        mock.call("mail.example.org", 25, None, timeout=15),
        mock.call().login("user", "pass"),
        mock.call().sendmail(
            "user@mail.example.org",
            ["foo@example.net", "baz@example.org", "qux@example.org"],
            mock.ANY,
        ),
        mock.call().sendmail(
            "user@mail.example.org",
            ["bar@example.com", "baz@example.org", "qux@example.org"],
            mock.ANY,
        ),
        mock.call().quit(),
    ]

    # No from= used in the above
    assert re.match(r".*from=.*", obj.url()) is None
    # No mode= as this isn't a secure connection
    assert re.match(r".*mode=.*", obj.url()) is None
    # No smtp= as the SMTP server is the same as the hostname in this case
    assert re.match(r".*smtp=.*", obj.url()) is None
    # URL is assembled based on provided user
    assert (
        re.match(r"^mailto://user:pass\@mail.example.org/.*", obj.url())
        is not None
    )

    # Verify our added emails are still part of the URL
    assert re.match(r".*/foo%40example.net[/?].*", obj.url()) is not None
    assert re.match(r".*/bar%40example.com[/?].*", obj.url()) is not None

    assert re.match(r".*bcc=qux%40example.org.*", obj.url()) is not None
    assert re.match(r".*cc=baz%40example.org.*", obj.url()) is not None


@mock.patch("smtplib.SMTP")
def test_plugin_email_timezone(mock_smtp):
    """NotifyEmail() Timezone Handling"""

    response = mock.Mock()
    mock_smtp.return_value = response

    # Loads America/Toronto
    results = email.NotifyEmail.parse_url(
        "mailtos://user:pass123@hotmail.com:123"
        "?tz=Toronto"
    )
    assert isinstance(results, dict)
    # timezone is detected
    assert "tz" in results

    # Instantiate the object
    obj = email.NotifyEmail(**results)
    assert isinstance(obj, email.NotifyEmail)
    assert obj.tzinfo.key == "America/Toronto"
    # Verify our URL has defined our timezone
    # %2F = escaped '/'
    assert "tz=America%2FToronto" in obj.url()

    # No Timezone setup/default
    results = email.NotifyEmail.parse_url(
        "mailtos://user:pass123@hotmail.com:1235"
    )
    assert "tz" not in results

    # Instantiate the object
    obj = email.NotifyEmail(**results)
    assert isinstance(obj, email.NotifyEmail)
    # Defaults to our system
    assert obj.tzinfo == datetime.now().astimezone().tzinfo
    assert "tz=" not in obj.url()

    # Now we'll work with an Asset to identify how it can hold
    # our default global variable (initialization proves case
    # insensitive initialization is supported)
    asset = AppriseAsset(timezone="aMErica/vanCOUver")

    # Instatiate our object once again using the same variable set
    # as above
    obj = email.NotifyEmail(**results, asset=asset)
    # Defaults to our system
    # lower() is required since Mac and Window are not case sensitive and will
    # See output as it was passed in and not corrected per IANA
    assert obj.tzinfo.key.lower() == "america/vancouver"
    assert "tz=" not in obj.url()

    # Having ourselves a default variable also does not prevent
    # anyone from defining their own over-ride is still supported:

    # Loads America/Montreal
    results = email.NotifyEmail.parse_url(
        "mailtos://user:pass123@hotmail.com:321"
        "?tz=Montreal"
    )
    assert isinstance(results, dict)
    # timezone is detected
    assert "tz" in results

    # Instantiate the object
    obj = email.NotifyEmail(**results)
    assert isinstance(obj, email.NotifyEmail)
    assert obj.tzinfo.key == "America/Montreal"
    # Verify our URL has defined our timezone
    # %2F = escaped '/'
    assert "tz=America%2FMontreal" in obj.url()


@mock.patch("smtplib.SMTP")
def test_plugin_email_smtplib_internationalization(mock_smtp):
    """NotifyEmail() Internationalization Handling."""

    # i18n test
    email_url = "".join([
        "mailto://user:pass@gmail.com?",
        "name=Например%20так",  # noqa: RUF001
    ])

    obj = Apprise.instantiate(
        email_url,
        suppress_exceptions=False,
    )

    assert isinstance(obj, email.NotifyEmail)

    class SMTPMock:
        def sendmail(self, *args, **kwargs):
            """Over-ride sendmail calls so we can check our our
            internationalization formatting went."""

            match_subject = re.search(
                r"\n?(?P<line>Subject: (?P<subject>(.+?)))\n(?:[a-z0-9-]+:)",
                args[2],
                re.I | re.M | re.S,
            )
            assert match_subject is not None

            match_from = re.search(
                r"^(?P<line>From: (?P<name>.+) <(?P<email>[^>]+)>)$",
                args[2],
                re.I | re.M,
            )
            assert match_from is not None

            # Verify our output was correctly stored
            assert match_from.group("email") == "user@gmail.com"

            assert (
                decode_header(match_from.group("name"))[0][0].decode("utf-8")
                == "Например так"
            )

            assert (
                decode_header(match_subject.group("subject"))[0][0].decode(
                    "utf-8"
                )
                == "دعونا نجعل العالم مكانا أفضل."
            )

        # Dummy Function
        def quit(self, *args, **kwargs):
            return True

        # Dummy Function
        def starttls(self, *args, **kwargs):
            return True

        # Dummy Function
        def login(self, *args, **kwargs):
            return True

    # Prepare our object we will test our generated email against
    mock_smtp.return_value = SMTPMock()

    # Further test encoding through the message content as well
    assert (
        obj.notify(
            # Google Translated to Arabic:
            #  "Let's make the world a better place."
            title="دعونا نجعل العالم مكانا أفضل.",
            # Google Translated to Hungarian: "One line of code at a time.'
            body="Egy sor kódot egyszerre.",
            notify_type=NotifyType.INFO,
        )
        is True
    )


def test_plugin_email_url_escaping():
    """NotifyEmail() Test that user/passwords are properly escaped from URL."""
    # quote(' %20')
    passwd = "%20%2520"

    # Basically we want to check that ' ' equates to %20 and % equates to %25
    # So the above translates to ' %20' (a space in front of %20).  We want
    # to verify the handling of the password escaping and when it happens.
    # a very bad response would be '  ' (double space)
    obj = email.NotifyEmail.parse_url(
        f"mailto://user:{passwd}@gmail.com?format=text"
    )

    assert isinstance(obj, dict)
    assert "password" in obj

    # Escaping doesn't happen at this stage because we want to leave this to
    # the plugins discretion
    assert obj.get("password") == "%20%2520"

    obj = Apprise.instantiate(
        f"mailto://user:{passwd}@gmail.com?format=text",
        suppress_exceptions=False,
    )
    assert isinstance(obj, email.NotifyEmail)

    # The password is escaped only 'once'
    assert obj.password == " %20"


def test_plugin_email_url_variations():
    """NotifyEmail() Test URL variations to ensure parsing is correct."""
    # Test variations of username required to be an email address
    # user@example.com
    obj = Apprise.instantiate(
        "mailto://{user}:{passwd}@example.com?smtp=example.com".format(
            user="apprise%40example21.ca", passwd="abcd123"
        ),
        suppress_exceptions=False,
    )
    assert isinstance(obj, email.NotifyEmail)

    assert obj.password == "abcd123"
    assert obj.user == "apprise@example21.ca"

    # No from= used in the above
    assert re.match(r".*from=.*", obj.url()) is None
    # No mode= as this isn't a secure connection
    assert re.match(r".*mode=.*", obj.url()) is None
    # No smtp= as the SMTP server is the same as the hostname in this case
    # even though it was explicitly specified
    assert re.match(r".*smtp=.*", obj.url()) is None
    # URL is assembled based on provided user
    assert (
        re.match(r"^mailto://apprise:abcd123\@example.com/.*", obj.url())
        is not None
    )

    # test username specified in the url body (as an argument)
    # this always over-rides the entry at the front of the url
    obj = Apprise.instantiate(
        "mailto://_:{passwd}@example.com?user={user}".format(
            user="apprise%40example21.ca", passwd="abcd123"
        ),
        suppress_exceptions=False,
    )
    assert isinstance(obj, email.NotifyEmail)

    assert obj.password == "abcd123"
    assert obj.user == "apprise@example21.ca"

    # No from= used in the above
    assert re.match(r".*from=.*", obj.url()) is None
    # No mode= as this isn't a secure connection
    assert re.match(r".*mode=.*", obj.url()) is None
    # No smtp= as the SMTP server is the same as the hostname in this case
    assert re.match(r".*smtp=.*", obj.url()) is None
    # URL is assembled based on provided user
    assert (
        re.match(r"^mailto://apprise:abcd123\@example.com/.*", obj.url())
        is not None
    )

    # test user and password specified in the url body (as an argument)
    # this always over-rides the entries at the front of the url
    obj = Apprise.instantiate(
        "mailtos://_:_@example.com?user={user}&pass={passwd}".format(
            user="apprise%40example21.ca", passwd="abcd123"
        ),
        suppress_exceptions=False,
    )
    assert isinstance(obj, email.NotifyEmail)

    assert obj.password == "abcd123"
    assert obj.user == "apprise@example21.ca"
    assert len(obj.targets) == 1
    assert (False, "apprise@example.com") in obj.targets
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == "apprise@example.com"
    assert obj.targets[0][0] is False
    assert obj.targets[0][1] == obj.from_addr[1]

    # No from= used in the above
    assert re.match(r".*from=.*", obj.url()) is None
    # Default mode is starttls
    assert re.match(r".*mode=starttls.*", obj.url()) is not None
    # No smtp= as the SMTP server is the same as the hostname in this case
    assert re.match(r".*smtp=.*", obj.url()) is None
    # URL is assembled based on provided user
    assert (
        re.match(r"^mailtos://apprise:abcd123\@example.com/.*", obj.url())
        is not None
    )

    # test user and password specified in the url body (as an argument)
    # this always over-rides the entries at the front of the url
    # this is similar to the previous test except we're only specifying
    # this information in the kwargs
    obj = Apprise.instantiate(
        "mailto://example.com?user={user}&pass={passwd}".format(
            user="apprise%40example21.ca", passwd="abcd123"
        ),
        suppress_exceptions=False,
    )
    assert isinstance(obj, email.NotifyEmail)

    assert obj.password == "abcd123"
    assert obj.user == "apprise@example21.ca"
    assert len(obj.targets) == 1
    assert (False, "apprise@example.com") in obj.targets
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == "apprise@example.com"
    assert obj.targets[0][0] is False
    assert obj.targets[0][1] == obj.from_addr[1]
    assert obj.smtp_host == "example.com"

    # No from= used in the above
    assert re.match(r".*from=.*", obj.url()) is None
    # No mode= as this isn't a secure connection
    assert re.match(r".*mode=.*", obj.url()) is None
    # No smtp= as the SMTP server is the same as the hostname in this case
    assert re.match(r".*smtp=.*", obj.url()) is None
    # URL is assembled based on provided user
    assert (
        re.match(r"^mailto://apprise:abcd123\@example.com/.*", obj.url())
        is not None
    )

    # test a complicated example
    obj = Apprise.instantiate(
        "mailtos://{user}:{passwd}@{host}:{port}"
        "?smtp={smtp_host}&format=text&from=Charles<{this}>&to={that}".format(
            user="apprise%40example21.ca",
            passwd="abcd123",
            host="example.com",
            port=1234,
            this="from@example.jp",
            that="to@example.jp",
            smtp_host="smtp.example.edu",
        ),
        suppress_exceptions=False,
    )
    assert isinstance(obj, email.NotifyEmail)

    assert obj.password == "abcd123"
    assert obj.user == "apprise@example21.ca"
    assert obj.host == "example.com"
    assert obj.port == 1234
    assert obj.smtp_host == "smtp.example.edu"
    assert len(obj.targets) == 1
    assert (False, "to@example.jp") in obj.targets
    assert obj.from_addr[0] == "Charles"
    assert obj.from_addr[1] == "from@example.jp"
    assert (
        re.match(r".*from=Charles\+%3Cfrom%40example.jp%3E.*", obj.url())
        is not None
    )

    # Test Tagging under various urll encodings
    for toaddr in (
        "/john.smith+mytag@domain.com",
        "?to=john.smith+mytag@domain.com",
        "/john.smith%2Bmytag@domain.com",
        "?to=john.smith%2Bmytag@domain.com",
    ):

        obj = Apprise.instantiate(f"mailto://user:pass@domain.com{toaddr}")
        assert isinstance(obj, email.NotifyEmail)
        assert obj.password == "pass"
        assert obj.user == "user"
        assert obj.host == "domain.com"
        assert obj.from_addr[0] == obj.app_id
        assert obj.from_addr[1] == "user@domain.com"
        assert len(obj.targets) == 1
        assert obj.targets[0][0] is False
        assert obj.targets[0][1] == "john.smith+mytag@domain.com"


def test_plugin_email_dict_variations():
    """NotifyEmail() Test email dictionary variations to ensure parsing is
    correct."""
    # Test variations of username required to be an email address
    # user@example.com
    obj = Apprise.instantiate(
        {
            "schema": "mailto",
            "user": "apprise@example.com",
            "password": "abd123",
            "host": "example.com",
        },
        suppress_exceptions=False,
    )
    assert isinstance(obj, email.NotifyEmail)


@mock.patch("smtplib.SMTP_SSL")
@mock.patch("smtplib.SMTP")
def test_plugin_email_url_parsing(mock_smtp, mock_smtp_ssl):
    """NotifyEmail() Test email url parsing."""

    response = mock.Mock()
    mock_smtp_ssl.return_value = response
    mock_smtp.return_value = response

    # Test variations of username required to be an email address
    # user@example.com; we also test an over-ride port on a template driven
    # mailto:// entry
    results = email.NotifyEmail.parse_url(
        "mailtos://user:pass123@hotmail.com:444"
        "?to=user2@yahoo.com&name=test%20name"
    )
    assert isinstance(results, dict)
    assert results["from_addr"] == "test name"
    assert results["user"] == "user"
    assert results["port"] == 444
    assert results["host"] == "hotmail.com"
    assert results["password"] == "pass123"
    assert "user2@yahoo.com" in results["targets"]

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "user@hotmail.com"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "user2@yahoo.com"
    assert _msg.split("\n")[-3] == "test"

    # Our URL port was over-ridden (on template) to use 444
    # We can verify that this was correctly saved
    assert obj.url().startswith(
        "mailtos://user:pass123@hotmail.com:444/user2%40yahoo.com"
    )
    assert "mode=starttls" in obj.url()
    assert "smtp=smtp-mail.outlook.com" in obj.url()

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    # The below switches the `name` with the `to` to verify the results
    # are the same; it also verfies that the mode gets changed to SSL
    # instead of STARTTLS
    results = email.NotifyEmail.parse_url(
        "mailtos://user:pass123@hotmail.com?smtp=override.com"
        "&name=test%20name&to=user2@yahoo.com&mode=ssl"
    )
    assert isinstance(results, dict)
    assert results["from_addr"] == "test name"
    assert results["user"] == "user"
    assert results["host"] == "hotmail.com"
    assert results["password"] == "pass123"
    assert "user2@yahoo.com" in results["targets"]
    assert results["secure_mode"] == "ssl"
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 1
    assert response.starttls.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "user@hotmail.com"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "user2@yahoo.com"
    assert _msg.split("\n")[-3] == "test"

    user, pw = response.login.call_args[0]
    # the SMTP Server was ovr
    assert pw == "pass123"
    assert user == "user"

    assert obj.url().startswith(
        "mailtos://user:pass123@hotmail.com/user2%40yahoo.com"
    )
    # Test that our template over-ride worked
    assert "mode=ssl" in obj.url()
    assert "smtp=override.com" in obj.url()
    # No reply address specified
    assert "reply=" not in obj.url()

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    #
    # Test outlook/hotmail lookups
    #
    results = email.NotifyEmail.parse_url("mailtos://user:pass123@hotmail.com")
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)
    assert obj.smtp_host == "smtp-mail.outlook.com"
    # No entries in the reply_to
    assert not obj.reply_to

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == "pass123"
    assert user == "user@hotmail.com"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = email.NotifyEmail.parse_url("mailtos://user:pass123@outlook.com")
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)
    assert obj.smtp_host == "smtp.outlook.com"
    # No entries in the reply_to
    assert not obj.reply_to

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == "pass123"
    assert user == "user@outlook.com"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = email.NotifyEmail.parse_url(
        "mailtos://user:pass123@outlook.com.au"
    )
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)
    assert obj.smtp_host == "smtp.outlook.com"
    # No entries in the reply_to
    assert not obj.reply_to

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == "pass123"
    assert user == "user@outlook.com.au"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    # Consisitency Checks
    results = email.NotifyEmail.parse_url(
        "mailtos://outlook.com?smtp=smtp.outlook.com"
        "&user=user@outlook.com&pass=app.pw"
    )
    obj1 = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj1, email.NotifyEmail)
    assert obj1.smtp_host == "smtp.outlook.com"
    assert obj1.user == "user@outlook.com"
    assert obj1.password == "app.pw"
    assert obj1.secure_mode == "starttls"
    assert obj1.port == 587

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj1.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == "app.pw"
    assert user == "user@outlook.com"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = email.NotifyEmail.parse_url("mailtos://user:app.pw@outlook.com")
    obj2 = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj2, email.NotifyEmail)
    assert obj2.smtp_host == obj1.smtp_host
    assert obj2.user == obj1.user
    assert obj2.password == obj1.password
    assert obj2.secure_mode == obj1.secure_mode
    assert obj2.port == obj1.port

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj2.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == "app.pw"
    assert user == "user@outlook.com"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = email.NotifyEmail.parse_url("mailto://user:pass@comcast.net")
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)
    assert obj.smtp_host == "smtp.comcast.net"
    assert obj.user == "user@comcast.net"
    assert obj.password == "pass"
    assert obj.secure_mode == "ssl"
    assert obj.port == 465

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 1
    assert response.starttls.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == "pass"
    assert user == "user@comcast.net"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = email.NotifyEmail.parse_url("mailtos://user:pass123@live.com")
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)
    # No entries in the reply_to
    assert not obj.reply_to

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == "pass123"
    assert user == "user@live.com"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = email.NotifyEmail.parse_url("mailtos://user:pass123@hotmail.com")
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)
    # No entries in the reply_to
    assert not obj.reply_to

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == "pass123"
    assert user == "user@hotmail.com"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    #
    # Test Port Over-Riding
    #
    results = email.NotifyEmail.parse_url(
        "mailtos://abc:password@xyz.cn:465?smtp=smtp.exmail.qq.com&mode=ssl"
    )
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    # Verify our over-rides are in place
    assert obj.smtp_host == "smtp.exmail.qq.com"
    assert obj.port == 465
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == "abc@xyz.cn"
    assert obj.secure_mode == "ssl"
    # No entries in the reply_to
    assert not obj.reply_to

    # No from= used in the above
    assert re.match(r".*from=.*", obj.url()) is None
    # No Our secure connection is SSL
    assert re.match(r".*mode=ssl.*", obj.url()) is not None
    # No smtp= as the SMTP server is the same as the hostname in this case
    assert re.match(r".*smtp=smtp.exmail.qq.com.*", obj.url()) is not None
    # URL is assembled based on provided user (:465 is dropped because it
    # is a default port when using xyz.cn)
    assert (
        re.match(r"^mailtos://abc:password@xyz.cn/.*", obj.url()) is not None
    )

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 1
    assert response.starttls.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == "password"
    assert user == "abc"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = email.NotifyEmail.parse_url(
        "mailtos://abc:password@xyz.cn?"
        "smtp=smtp.exmail.qq.com&mode=ssl&port=465"
    )
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    # Verify our over-rides are in place
    assert obj.smtp_host == "smtp.exmail.qq.com"
    assert obj.port == 465
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == "abc@xyz.cn"
    assert obj.secure_mode == "ssl"
    # No entries in the reply_to
    assert not obj.reply_to

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 1
    assert response.starttls.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == "password"
    assert user == "abc"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    #
    # Test Reply-To Email
    #
    results = email.NotifyEmail.parse_url(
        "mailtos://user:pass@example.com?reply=noreply@example.com"
    )
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)
    # Verify our over-rides are in place
    assert obj.smtp_host == "example.com"
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == "user@example.com"
    assert obj.secure_mode == "starttls"
    assert obj.url().startswith("mailtos://user:pass@example.com")
    # Test that our template over-ride worked
    assert "reply=noreply%40example.com" in obj.url()

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == "pass"
    assert user == "user"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    #
    # Test Reply-To Email with Name Inline
    #
    results = email.NotifyEmail.parse_url(
        "mailtos://user:pass@example.com?reply=Chris<noreply@example.ca>"
    )
    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)
    # Verify our over-rides are in place
    assert obj.smtp_host == "example.com"
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == "user@example.com"
    assert obj.secure_mode == "starttls"
    assert obj.url().startswith("mailtos://user:pass@example.com")
    # Test that our template over-ride worked
    assert "reply=Chris+%3Cnoreply%40example.ca%3E" in obj.url()

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1

    user, pw = response.login.call_args[0]
    assert pw == "pass"
    assert user == "user"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    # Fast Mail Handling

    # Test variations of username required to be an email address
    # user@example.com; we also test an over-ride port on a template driven
    # mailto:// entry
    results = email.NotifyEmail.parse_url(
        "mailto://fastmail.com/?to=hello@concordium-explorer.nl"
        "&user=joe@mydomain.nl&pass=abc123"
        "&from=Concordium Explorer Bot<bot@concordium-explorer.nl>"
    )
    assert isinstance(results, dict)
    assert (
        results["from_addr"]
        == "Concordium Explorer Bot<bot@concordium-explorer.nl>"
    )
    assert results["user"] == "joe@mydomain.nl"
    assert results["port"] is None
    assert results["host"] == "fastmail.com"
    assert results["password"] == "abc123"
    assert "hello@concordium-explorer.nl" in results["targets"]

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 1
    assert response.starttls.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "bot@concordium-explorer.nl"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "hello@concordium-explorer.nl"
    assert _msg.split("\n")[-3] == "test"

    user, pw = response.login.call_args[0]
    assert pw == "abc123"
    assert user == "joe@mydomain.nl"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    # Issue github.com/caronc/apprise/issue/1040
    #  mailto://fastmail.com?user=username@customdomain.com \
    #          &to=username@customdomain.com&pass=password123
    #
    # should just have to be written like (to= omitted)
    #  mailto://fastmail.com?user=username@customdomain.com&pass=password123
    #
    results = email.NotifyEmail.parse_url(
        "mailto://fastmail.com?user=username@customdomain.com&pass=password123"
    )
    assert isinstance(results, dict)
    assert results["user"] == "username@customdomain.com"
    assert results["from_addr"] == ""
    assert results["port"] is None
    assert results["host"] == "fastmail.com"
    assert results["password"] == "password123"
    assert results["smtp_host"] == ""

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)
    # During instantiation, our variables get detected
    assert obj.smtp_host == "smtp.fastmail.com"
    assert obj.from_addr == ["Apprise", "username@customdomain.com"]
    assert obj.host == "customdomain.com"
    # detected from
    assert (False, "username@customdomain.com") in obj.targets

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 1
    assert response.starttls.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "username@customdomain.com"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "username@customdomain.com"
    assert _msg.split("\n")[-3] == "test"

    user, pw = response.login.call_args[0]
    assert pw == "password123"
    assert user == "username@customdomain.com"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    # Similar test as above, just showing that we can over-ride the From=
    # with these custom URLs as well and not require a full email
    results = email.NotifyEmail.parse_url(
        "mailto://fastmail.com?user=username@customdomain.com"
        "&pass=password123&from=Custom"
    )
    assert isinstance(results, dict)
    assert results["user"] == "username@customdomain.com"
    assert results["from_addr"] == "Custom"
    assert results["port"] is None
    assert results["host"] == "fastmail.com"
    assert results["password"] == "password123"
    assert results["smtp_host"] == ""

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)
    # During instantiation, our variables get detected
    assert obj.smtp_host == "smtp.fastmail.com"
    assert obj.from_addr == ["Custom", "username@customdomain.com"]
    assert obj.host == "customdomain.com"
    # detected from
    assert (False, "username@customdomain.com") in obj.targets

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 1
    assert response.starttls.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "username@customdomain.com"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "username@customdomain.com"
    assert _msg.split("\n")[-3] == "test"

    user, pw = response.login.call_args[0]
    assert pw == "password123"
    assert user == "username@customdomain.com"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    # Issue github.com/caronc/apprise/issue/941

    # mail domain = mail-domain.com
    # host domain = domain.subdomain.com
    # PASSWORD needs to be fetched since a user= was provided
    #  - this is an edge case that is tested here
    results = email.NotifyEmail.parse_url(
        "mailtos://PASSWORD@domain.subdomain.com:587?"
        "user=admin@mail-domain.com&to=mail@mail-domain.com"
    )
    assert isinstance(results, dict)
    # From_Addr could not be detected at this stage, but will be
    # handled during instantiation
    assert results["from_addr"] == ""
    assert results["user"] == "admin@mail-domain.com"
    assert results["port"] == 587
    assert results["host"] == "domain.subdomain.com"
    assert results["password"] == "PASSWORD"
    assert "mail@mail-domain.com" in results["targets"]

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    # Not that our from_address takes on 'admin@domain.subdomain.com'
    assert obj.from_addr == ["Apprise", "admin@domain.subdomain.com"]

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert response.starttls.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "admin@domain.subdomain.com"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "mail@mail-domain.com"
    assert _msg.split("\n")[-3] == "test"

    user, pw = response.login.call_args[0]
    assert user == "admin@mail-domain.com"
    assert pw == "PASSWORD"


@mock.patch("smtplib.SMTP_SSL")
@mock.patch("smtplib.SMTP")
def test_plugin_email_plus_in_toemail(mock_smtp, mock_smtp_ssl):
    """NotifyEmail() support + in To Email address."""

    response = mock.Mock()
    mock_smtp_ssl.return_value = response
    mock_smtp.return_value = response

    # We want to test the case where a + is found in the To address; we want to
    # ensure that it is supported
    results = email.NotifyEmail.parse_url(
        "mailtos://user:pass123@gmail.com"
        "?to=Plus Support<test+notification@gmail.com>"
    )
    assert isinstance(results, dict)
    assert results["user"] == "user"
    assert results["host"] == "gmail.com"
    assert results["password"] == "pass123"
    assert results["port"] is None
    assert "Plus Support<test+notification@gmail.com>" in results["targets"]

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    assert len(obj.targets) == 1
    assert ("Plus Support", "test+notification@gmail.com") in obj.targets
    assert obj.smtp_host == "smtp.gmail.com"
    assert obj.from_addr == ["Apprise", "user@gmail.com"]
    assert obj.host == "gmail.com"

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "user@gmail.com"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "test+notification@gmail.com"
    assert _msg.split("\n")[-3] == "test"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    #
    # Perform the same test where the To field jsut contains the + in the
    # address
    #
    results = email.NotifyEmail.parse_url(
        "mailtos://user:pass123@gmail.com?to=test+notification@gmail.com"
    )
    assert isinstance(results, dict)
    assert results["user"] == "user"
    assert results["host"] == "gmail.com"
    assert results["password"] == "pass123"
    assert results["port"] is None
    assert "test+notification@gmail.com" in results["targets"]

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    assert len(obj.targets) == 1
    assert (False, "test+notification@gmail.com") in obj.targets

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "user@gmail.com"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "test+notification@gmail.com"
    assert _msg.split("\n")[-3] == "test"

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    #
    # Perform the same test where the To field is in the URL itself
    #
    results = email.NotifyEmail.parse_url(
        "mailtos://user:pass123@gmail.com/test+notification@gmail.com"
    )
    assert isinstance(results, dict)
    assert results["user"] == "user"
    assert results["host"] == "gmail.com"
    assert results["password"] == "pass123"
    assert results["port"] is None
    assert "test+notification@gmail.com" in results["targets"]

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    assert len(obj.targets) == 1
    assert (False, "test+notification@gmail.com") in obj.targets

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("test") is True
    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "user@gmail.com"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "test+notification@gmail.com"
    assert _msg.split("\n")[-3] == "test"


@mock.patch("smtplib.SMTP_SSL")
@mock.patch("smtplib.SMTP")
def test_plugin_email_formatting_990(mock_smtp, mock_smtp_ssl):
    """
    NotifyEmail() GitHub Issue 990
    https://github.com/caronc/apprise/issues/990
    Email formatting not working correctly

    """

    response = mock.Mock()
    mock_smtp_ssl.return_value = response
    mock_smtp.return_value = response

    results = email.NotifyEmail.parse_url(
        "mailtos://mydomain.com?smtp=mail.local.mydomain.com"
        "&user=noreply@mydomain.com&pass=mypassword"
        "&from=noreply@mydomain.com&to=me@mydomain.com&mode=ssl&port=465"
    )

    assert isinstance(results, dict)
    assert results["user"] == "noreply@mydomain.com"
    assert results["host"] == "mydomain.com"
    assert results["smtp_host"] == "mail.local.mydomain.com"
    assert results["password"] == "mypassword"
    assert results["secure_mode"] == "ssl"
    assert results["port"] == "465"
    assert "me@mydomain.com" in results["targets"]

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    assert len(obj.targets) == 1
    assert (False, "me@mydomain.com") in obj.targets


def test_plugin_email_variables_1087():
    """
    NotifyEmail() GitHub Issue 1087
    https://github.com/caronc/apprise/issues/1087
    Email variables reported not working correctly

    """

    # Valid Configuration
    result, _ = ConfigBase.config_parse(
        cleandoc("""
    #
    # Test Email Parsing
    #
    urls:
      - mailtos://alt.lan/:
        - user: testuser@alt.lan
          pass: xxxxXXXxxx
          smtp: smtp.alt.lan
          to: alteriks@alt.lan
    """),
        asset=AppriseAsset(),
    )

    assert isinstance(result, list)
    assert len(result) == 1

    _email = result[0]
    assert _email.from_addr == ["Apprise", "testuser@alt.lan"]
    assert _email.user == "testuser@alt.lan"
    assert _email.smtp_host == "smtp.alt.lan"
    assert _email.targets == [(False, "alteriks@alt.lan")]
    assert _email.password == "xxxxXXXxxx"

    # Valid Configuration
    result, _ = ConfigBase.config_parse(
        cleandoc("""
    #
    # Test Email Parsing where qsd over-rides all
    #
    urls:
      - mailtos://alt.lan/?pass=abcd&user=joe@alt.lan:
        - user: testuser@alt.lan
          pass: xxxxXXXxxx
          smtp: smtp.alt.lan
          to: alteriks@alt.lan
    """),
        asset=AppriseAsset(),
    )

    assert isinstance(result, list)
    assert len(result) == 1

    _email = result[0]
    assert _email.from_addr == ["Apprise", "joe@alt.lan"]
    assert _email.user == "joe@alt.lan"
    assert _email.smtp_host == "smtp.alt.lan"
    assert _email.targets == [(False, "alteriks@alt.lan")]
    assert _email.password == "abcd"


@mock.patch("smtplib.SMTP_SSL")
@mock.patch("smtplib.SMTP")
def test_plugin_email_to_handling_1356(mock_smtp, mock_smtp_ssl):
    """
    NotifyEmail() GitHub Issue 1356
    https://github.com/caronc/apprise/issues/1356
    Email not correctly preparing the `to:`

    """

    response = mock.Mock()
    mock_smtp_ssl.return_value = response
    mock_smtp.return_value = response

    results = email.NotifyEmail.parse_url(
        "mailtos://smtp-relay.gmail.com?"
        "from=user@custom-domain.casa&to=alerts@anothercustomdomain.net"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["host"] == "smtp-relay.gmail.com"
    assert results["port"] is None
    assert results["from_addr"] == "user@custom-domain.casa"
    assert results["smtp_host"] == ""
    assert "alerts@anothercustomdomain.net" in results["targets"]

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    assert len(obj.targets) == 1
    assert (False, "alerts@anothercustomdomain.net") in obj.targets

    assert obj.smtp_host == "smtp-relay.gmail.com"
    assert obj.from_addr == (False, "user@custom-domain.casa")

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("body", "title") is True

    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    # No login occurs as no user/pass was provided
    assert response.login.call_count == 0
    assert response.sendmail.call_count == 1

    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "user@custom-domain.casa"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "alerts@anothercustomdomain.net"
    assert _msg.split("\n")[-3] == "body"


@mock.patch("smtplib.SMTP_SSL")
@mock.patch("smtplib.SMTP")
def test_plugin_email_variables_1334(mock_smtp, mock_smtp_ssl):
    """
    NotifyEmail() GitHub Issue 1334
    https://github.com/caronc/apprise/issues/1334
    Localhost & Local Domain default user

    """

    response = mock.Mock()
    mock_smtp_ssl.return_value = response
    mock_smtp.return_value = response

    results = email.NotifyEmail.parse_url("mailto://localhost")

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["host"] == "localhost"
    assert results["port"] is None
    assert results["from_addr"] == ""
    assert results["smtp_host"] == ""
    assert results["targets"] == []

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    assert len(obj.targets) == 1
    assert (False, "root@localhost") in obj.targets

    assert obj.smtp_host == "localhost"
    assert obj.secure is False
    assert obj.from_addr == [False, "root@localhost"]

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("body", "title") is True

    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 0
    # No login occurs as no user/pass was provided
    assert response.login.call_count == 0
    assert response.sendmail.call_count == 1

    #
    # Again, but a different variation of the localhost domain
    #
    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = email.NotifyEmail.parse_url(
        "mailtos://user@localhost.localdomain"
    )

    assert isinstance(results, dict)
    assert results["user"] == "user"
    assert results["password"] is None
    assert results["host"] == "localhost.localdomain"
    assert results["port"] is None
    assert results["from_addr"] == ""
    assert results["smtp_host"] == ""
    assert results["targets"] == []

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail)

    assert len(obj.targets) == 1
    assert (False, "user@localhost.localdomain") in obj.targets

    assert obj.smtp_host == "localhost.localdomain"
    assert obj.secure is True
    assert obj.from_addr == ["Apprise", "user@localhost.localdomain"]

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("body", "title") is True

    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    # No login occurs as no user/pass was provided
    assert response.login.call_count == 0
    assert response.sendmail.call_count == 1


@mock.patch("smtplib.SMTP_SSL")
@mock.patch("smtplib.SMTP")
def test_plugin_host_detection_from_source_email(mock_smtp, mock_smtp_ssl):
    """NotifyEmail() Discord Issue reporting that the following did not work:

    mailtos://?smtp=mobile.charter.net&pass=password&user=name@spectrum.net
    """

    response = mock.Mock()
    mock_smtp_ssl.return_value = response
    mock_smtp.return_value = response

    results = email.NotifyEmail.parse_url(
        "mailtos://spectrum.net?smtp=mobile.charter.net"
        "&pass=password&user=name@spectrum.net"
    )

    assert isinstance(results, dict)
    assert results["user"] == "name@spectrum.net"
    assert results["host"] == "spectrum.net"
    assert results["smtp_host"] == "mobile.charter.net"
    assert results["password"] == "password"

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail) is True

    assert len(obj.targets) == 1
    assert (False, "name@spectrum.net") in obj.targets
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == "name@spectrum.net"
    assert obj.password == "password"
    assert obj.user == "name@spectrum.net"
    assert obj.secure is True
    assert obj.port == 587
    assert obj.smtp_host == "mobile.charter.net"

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("body", "title") is True

    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "name@spectrum.net"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "name@spectrum.net"
    assert _msg.split("\n")[-3] == "body"

    #
    # Now let's do a shortened version of the same URL where the host isn't
    # specified but is parseable from he user login
    #
    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = email.NotifyEmail.parse_url(
        "mailtos://?smtp=mobile.charter.net"
        "&pass=password&user=name@spectrum.net"
    )

    assert isinstance(results, dict)
    assert results["user"] == "name@spectrum.net"
    assert results["host"] == ""  # No hostname defined; it's detected later
    assert results["smtp_host"] == "mobile.charter.net"
    assert results["password"] == "password"

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail) is True

    assert len(obj.targets) == 1
    assert (False, "name@spectrum.net") in obj.targets
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == "name@spectrum.net"
    assert obj.password == "password"
    assert obj.user == "name@spectrum.net"
    assert obj.secure is True
    assert obj.port == 587
    assert obj.smtp_host == "mobile.charter.net"

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("body", "title") is True

    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "name@spectrum.net"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "name@spectrum.net"
    assert _msg.split("\n")[-3] == "body"

    #
    # Now let's do a shortened version of the same URL where the host isn't
    # specified but is parseable from he user login
    #
    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = email.NotifyEmail.parse_url(
        "mailtos://?smtp=mobile.charter.net"
        "&pass=password&user=userid-without-domain"
    )

    assert isinstance(results, dict)
    assert results["user"] == "userid-without-domain"
    assert results["host"] == ""  # No hostname defined
    assert results["smtp_host"] == "mobile.charter.net"
    assert results["password"] == "password"

    with pytest.raises(TypeError):
        # We will fail
        Apprise.instantiate(results, suppress_exceptions=False)

    #
    # Now support target emails in place of the hostname
    #

    mock_smtp.reset_mock()
    mock_smtp_ssl.reset_mock()
    response.reset_mock()

    results = email.NotifyEmail.parse_url(
        "mailtos://John Doe<john%40yahoo.ca>?smtp=mobile.charter.net"
        "&pass=password&user=name@spectrum.net"
    )

    assert isinstance(results, dict)
    assert results["user"] == "name@spectrum.net"
    assert results["host"] == ""  # No hostname defined; it's detected later
    assert results["smtp_host"] == "mobile.charter.net"
    assert results["password"] == "password"

    obj = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(obj, email.NotifyEmail) is True

    assert len(obj.targets) == 1
    assert ("John Doe", "john@yahoo.ca") in obj.targets
    assert obj.from_addr[0] == obj.app_id
    assert obj.from_addr[1] == "name@spectrum.net"
    assert obj.password == "password"
    assert obj.user == "name@spectrum.net"
    assert obj.secure is True
    assert obj.port == 587
    assert obj.smtp_host == "mobile.charter.net"

    assert mock_smtp.call_count == 0
    assert mock_smtp_ssl.call_count == 0
    assert obj.notify("body", "title") is True

    assert mock_smtp.call_count == 1
    assert mock_smtp_ssl.call_count == 0
    assert response.starttls.call_count == 1
    assert response.login.call_count == 1
    assert response.sendmail.call_count == 1
    # Store our Sent Arguments
    # Syntax is:
    #  sendmail(from_addr, to_addrs, msg, mail_options=(), rcpt_options=())
    #             [0]        [1]     [2]
    _from = response.sendmail.call_args[0][0]
    _to = response.sendmail.call_args[0][1]
    _msg = response.sendmail.call_args[0][2]
    assert _from == "name@spectrum.net"
    assert isinstance(_to, list)
    assert len(_to) == 1
    assert _to[0] == "john@yahoo.ca"
    assert _msg.split("\n")[-3] == "body"


@mock.patch("smtplib.SMTP_SSL")
@mock.patch("smtplib.SMTP")
def test_plugin_email_by_ipaddr_1113(mock_smtp, mock_smtp_ssl):
    """
    NotifyEmail() GitHub Issue 1113
    https://github.com/caronc/apprise/issues/1113
    Email with ip addresses not working

    """

    response = mock.Mock()
    mock_smtp_ssl.return_value = response
    mock_smtp.return_value = response

    results = email.NotifyEmail.parse_url(
        "mailto://10.0.0.195:25/?to=alerts@example.com&from=sender@example.com"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["host"] == "10.0.0.195"
    assert results["from_addr"] == "sender@example.com"
    assert isinstance(results["targets"], list)
    assert len(results["targets"]) == 1
    assert results["targets"][0] == "alerts@example.com"
    assert results["port"] == 25

    _email = Apprise.instantiate(results, suppress_exceptions=False)
    assert isinstance(_email, email.NotifyEmail) is True

    assert len(_email.targets) == 1
    assert (False, "alerts@example.com") in _email.targets

    assert _email.from_addr == (False, "sender@example.com")
    assert _email.user is None
    assert _email.password is None
    assert _email.smtp_host == "10.0.0.195"
    assert _email.port == 25
    assert _email.targets == [(False, "alerts@example.com")]


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
@mock.patch("smtplib.SMTP_SSL")
@mock.patch("smtplib.SMTP")
def test_plugin_email_pgp(mock_smtp, mock_smtpssl, tmpdir):
    """NotifyEmail() PGP Tests."""
    # Our mock of our socket action
    mock_socket = mock.Mock()
    mock_socket.starttls.return_value = True
    mock_socket.login.return_value = True

    # Create a mock SMTP Object
    mock_smtp.return_value = mock_socket
    mock_smtpssl.return_value = mock_socket

    assert utils.pgp.PGP_SUPPORT is True
    utils.pgp.PGP_SUPPORT = False
    # Forces to run through section of code that produces a warning there is
    # no PGP
    obj = Apprise.instantiate("mailto://user:pass@nuxref.com?pgp=yes")
    # No PGP Support and set enabled
    assert obj.notify("test body") is False

    # Return the PGP status for remaining checks
    utils.pgp.PGP_SUPPORT = True

    # Initialize our email (no from name)
    obj = Apprise.instantiate("mailto://user2:pass@nuxref.com?pgp=yes")

    # Nothing to lookup
    assert obj.pgp.public_keyfile() is None
    assert obj.pgp.public_key() is None
    assert obj.pgp.encrypt("message") is False
    # Keys can not be generated in memory mode
    assert obj.pgp.keygen() is False

    # The reason... no location to store data
    assert obj.store.mode == PersistentStoreMode.MEMORY

    tmpdir0 = tmpdir.mkdir("tmp00")
    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir0),
    )

    # Prepare PGP
    obj = Apprise.instantiate(
        "mailto://pgp:pass@nuxref.com?pgp=yes", asset=asset
    )
    assert obj.store.mode == PersistentStoreMode.FLUSH

    # Still no public key
    assert obj.pgp.public_key(autogen=False) is None
    assert obj.pgp.keygen() is True
    # Now we'll have a public key
    assert isinstance(obj.pgp.public_keyfile(), str)

    # Generate warning by second call
    assert obj.pgp.keygen() is True

    # Remove newly generated files
    os.unlink(os.path.join(obj.store.path, "pgp-pub.asc"))
    os.unlink(os.path.join(obj.store.path, "pgp-prv.asc"))
    obj = Apprise.instantiate(
        "mailto://pgp:pass@nuxref.com?pgp=yes", asset=asset
    )
    assert obj.store.mode == PersistentStoreMode.FLUSH
    assert obj.pgp.keygen() is True

    # Prepare PGP while providing it a key
    obj = Apprise.instantiate(
        "mailto://pgp:pass@nuxref.com?pgp=yes&"
        f"pgpkey={obj.pgp.public_keyfile()}",
        asset=asset,
    )

    # keyfile Defined
    assert obj.pgp.pub_keyfile is not None

    # Get our key
    key = obj.pgp.public_key()

    # In this circumstance we can not generate a new key as the one provided
    # is immutable
    assert obj.pgp.keygen() is False

    # Our key is the same
    assert key is obj.pgp.public_key()

    tmpdir0 = tmpdir.mkdir("tmp00a")
    asset0 = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir0),
    )

    # Prepare Invalid PGP Key
    obj = Apprise.instantiate(
        "mailto://pgpX:pass@nuxref.com?pgp=yes", asset=asset0
    )

    # No keyfiles
    assert obj.pgp.pub_keyfile is None

    # Generate our keys
    assert obj.pgp.keygen() is True

    # Second call uses cache
    assert obj.pgp.keygen() is True

    # We will find our key
    key = obj.pgp.public_key()
    assert key is not None

    # Utilize force parameter
    assert obj.pgp.keygen(force=True) is True

    # Our key is new
    assert key != obj.pgp.public_key()
    assert obj.pgp.public_key() is not None

    # Prepare Invalid PGP Key
    obj = Apprise.instantiate(
        "mailto://pgp:pass@nuxref.com?pgp=yes&pgpkey=invalid", asset=asset
    )

    # Returns false
    assert obj.pgp.pub_keyfile is False
    assert obj.pgp.public_keyfile() is False

    tmpdir2 = tmpdir.mkdir("tmp02")
    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir2),
    )
    obj = Apprise.instantiate(
        "mailto://chris:pass@nuxref.com?pgp=yes", asset=asset
    )

    assert obj.store.mode == PersistentStoreMode.FLUSH
    assert obj.pgp.keygen() is True

    # Second call uses cache
    assert obj.pgp.keygen() is True

    # We will find our key
    assert obj.pgp.public_key() is not None

    # We do this again but even when we do a requisition for a public key
    # it will generate a new pair or keys for us once it detects we don't
    # have any
    tmpdir3 = tmpdir.mkdir("tmp03")
    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir3),
    )
    obj = Apprise.instantiate(
        "mailto://chris:pass@nuxref.com/user@example.com?pgp=yes", asset=asset
    )

    assert obj.store.mode == PersistentStoreMode.FLUSH

    # We'll have a public key object to encrypt with
    assert obj.pgp.public_key() is not None

    encrypted = obj.pgp.encrypt("hello world")
    assert encrypted.startswith("-----BEGIN PGP MESSAGE-----")
    assert encrypted.rstrip().endswith("-----END PGP MESSAGE-----")

    dir_content = os.listdir(obj.store.path)
    assert "chris-pub.asc" in dir_content
    assert "chris-prv.asc" in dir_content

    assert obj.pgp.public_keyfile().endswith("chris-pub.asc")

    assert obj.notify("test body") is True

    # The private key is not needed for sending the encrypted messages
    os.unlink(os.path.join(obj.store.path, "chris-prv.asc"))
    os.rename(
        os.path.join(obj.store.path, "chris-pub.asc"),
        os.path.join(obj.store.path, "user@example.com-pub.asc"),
    )

    assert obj.pgp.public_keyfile() is None
    assert obj.pgp.public_keyfile("not-reference@example.com") is None
    assert obj.pgp.public_keyfile("user@example.com").endswith(
        "user@example.com-pub.asc"
    )

    assert obj.pgp.public_keyfile("user@example.com").endswith(
        "user@example.com-pub.asc"
    )
    assert obj.pgp.public_keyfile("User@Example.com").endswith(
        "user@example.com-pub.asc"
    )
    assert obj.pgp.public_keyfile("unknown") is None

    shutil.copyfile(
        os.path.join(obj.store.path, "user@example.com-pub.asc"),
        os.path.join(obj.store.path, "user-pub.asc"),
    )

    assert obj.pgp.public_keyfile("user@example.com").endswith(
        "user@example.com-pub.asc"
    )
    assert obj.pgp.public_keyfile("User@Example.com").endswith(
        "user@example.com-pub.asc"
    )

    # Remove file
    os.unlink(os.path.join(obj.store.path, "user@example.com-pub.asc"))
    assert obj.pgp.public_keyfile("user@example.com").endswith("user-pub.asc")
    shutil.copyfile(
        os.path.join(obj.store.path, "user-pub.asc"),
        os.path.join(obj.store.path, "chris-pub.asc"),
    )
    # user-pub.asc still trumps still trumps
    assert obj.pgp.public_keyfile("user@example.com").endswith("user-pub.asc")
    shutil.copyfile(
        os.path.join(obj.store.path, "chris-pub.asc"),
        os.path.join(obj.store.path, "chris@nuxref.com-pub.asc"),
    )
    # user-pub still trumps
    assert obj.pgp.public_keyfile("user@example.com").endswith("user-pub.asc")
    assert obj.pgp.public_keyfile("invalid@example.com").endswith(
        "chris@nuxref.com-pub.asc"
    )

    # remove this file
    os.unlink(os.path.join(obj.store.path, "user-pub.asc"))

    # now we fall back to basic/default configuration
    assert obj.pgp.public_keyfile("user@example.com").endswith(
        "chris@nuxref.com-pub.asc"
    )
    os.unlink(os.path.join(obj.store.path, "chris@nuxref.com-pub.asc"))
    assert obj.pgp.public_keyfile("user@example.com").endswith("chris-pub.asc")

    # Testing again
    tmpdir4 = tmpdir.mkdir("tmp04")
    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir4),
    )
    obj = Apprise.instantiate(
        "mailto://chris:pass@nuxref.com/user@example.com?pgp=yes", asset=asset
    )

    with mock.patch("builtins.open", side_effect=FileNotFoundError):
        # can't open key
        assert obj.pgp.public_key() is None

    with mock.patch("builtins.open", side_effect=OSError):
        # can't open key
        assert obj.pgp.public_key() is None
        # Test unlink
        with mock.patch("os.unlink", side_effect=OSError):
            assert obj.pgp.public_key() is None

        # Key Generation will fail
        assert obj.pgp.keygen() is False

    with mock.patch("pgpy.PGPKey.new", side_effect=NameError):
        # Can't Generate keys
        assert obj.pgp.keygen() is False
        # can't open key
        assert obj.pgp.public_key() is None

    with mock.patch("pgpy.PGPKey.from_blob", side_effect=FileNotFoundError):
        # can't open key
        assert obj.pgp.public_key() is None

    with mock.patch("pgpy.PGPKey.from_blob", side_effect=OSError):
        # can't open key
        assert obj.pgp.public_key() is None

    # Can't encrypt key
    with mock.patch("pgpy.PGPKey.from_blob", side_effect=NameError):
        assert obj.pgp.public_key() is None

    with mock.patch("pgpy.PGPMessage.new", side_effect=NameError):
        assert obj.pgp.encrypt("message") is None
        # Attempts to encrypt a message
        assert obj.notify("test-encrypt") is False

    # Create new keys
    assert obj.pgp.keygen() is True
    with (
        mock.patch("os.path.isfile", return_value=False),
        mock.patch("builtins.open", side_effect=OSError),
        mock.patch("os.unlink", return_value=None),
    ):
        assert obj.pgp.keygen() is False

    # Testing again
    tmpdir5 = tmpdir.mkdir("tmp05")
    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir5),
    )
    obj = Apprise.instantiate(
        "mailto://chris:pass@nuxref.com/user@example.com?pgp=yes", asset=asset
    )

    # Catch edge case where we just can't generate the the key
    with (
        mock.patch(
            "os.path.isfile",
            side_effect=(
                # 5x False to skip through pgp.public_keyfile()
                False,
                False,
                False,
                False,
                False,
                False,
                # 1x True to pass pgp.keygen()
                True,
                # 5x False to skip through pgp.public_keyfile() second call
                False,
                False,
                False,
                False,
                False,
                False,
            ),
        ),
        mock.patch("pgpy.PGPKey.from_blob", side_effect=FileNotFoundError),
    ):
        assert obj.pgp.public_key() is None

    # Corrupt Data
    tmpdir6 = tmpdir.mkdir("tmp06")
    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir6),
    )
    obj = Apprise.instantiate(
        "mailto://chris:pass@nuxref.com/user@example.com?pgp=yes", asset=asset
    )

    shutil.copyfile(
        os.path.join(TEST_VAR_DIR, "pgp", "corrupt-pub.asc"),
        os.path.join(obj.store.path, "chris-pub.asc"),
    )

    # Key is corrupted
    assert obj.notify("test") is False

    shutil.copyfile(
        os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
        os.path.join(obj.store.path, "chris-pub.asc"),
    )

    # Key is a binary image; definitely not a valid key
    assert obj.notify("test") is False


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_plugin_email_prepare():
    """NotifyEmail() prepare_emails static function."""
    with pytest.raises(AppriseException):
        # No To: provided
        for _e in email.NotifyEmail.prepare_emails(
            subject="Email Subject",
            body="Email Body",
            from_addr=(None, "test@test.com"),
            to=[],
        ):
            pass

    # Most basic call (a lot of defaults are used)
    _iterator = email.NotifyEmail.prepare_emails(
        subject="Email Subject",
        body="Email Body",
        from_addr=(None, "test@test.com"),
        to=[
            ("Apprise User", "apprise@test.com"),
        ],
    )
    entries = list(_iterator)
    assert len(entries) == 1


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_plugin_pgp(tmpdir):
    """Pretty Good Privacy Testing."""

    p_obj = utils.pgp.ApprisePGPController(path=None)
    # No Path
    assert p_obj.keygen() is False
    assert p_obj.public_keyfile() is None

    p_obj = utils.pgp.ApprisePGPController(path=None, email="l2g@email.com")
    # No Path
    assert p_obj.keygen() is False

    tmpdir0 = tmpdir.mkdir("tmp00")
    p_obj = utils.pgp.ApprisePGPController(
        path=str(tmpdir0), email="l2g@email.com"
    )

    # A key can be generated with a path defined
    assert p_obj.keygen() is True
    assert p_obj.public_keyfile() is not None
    # A key can be generated with a path defined
    assert p_obj.keygen(name="Apprise", force=True) is True
    assert (
        p_obj.keygen(email="l2g@email.com", name="Apprise", force=True) is True
    )

    assert utils.pgp.PGP_SUPPORT is True
    utils.pgp.PGP_SUPPORT = False

    with pytest.raises(AppriseException):
        assert p_obj.public_keyfile()

    # Return the PGP status for remaining checks
    utils.pgp.PGP_SUPPORT = True

    tmpdir1 = tmpdir.mkdir("tmp01")
    p_obj = utils.pgp.ApprisePGPController(
        path=str(tmpdir1), pub_keyfile="bad-file"
    )
    assert p_obj.public_keyfile() is False


@pytest.mark.skipif("pgpy" not in sys.modules, reason="Requires PGPy")
def test_pgp_public_keyfile_skips_self_email(tmpdir):
    """Test pgp.public_keyfile() when self.email is None and skipped."""

    key_dir = tmpdir.mkdir("pgpkeytest2")
    key_path = os.path.join(str(key_dir), "externaluser-pub.asc")

    # Create a fake matching keyfile to trigger discovery
    with open(key_path, "w") as f:
        f.write("-----BEGIN PGP PUBLIC KEY BLOCK-----\n")

    # Controller without setting self.email
    pgp = utils.pgp.ApprisePGPController(path=str(key_dir), email=None)

    # Should skip over `if self.email:` logic entirely
    result = pgp.public_keyfile("externaluser@email.com")

    assert result.endswith("externaluser-pub.asc")
