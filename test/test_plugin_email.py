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

import os
import re
import six
import mock
import smtplib
from email.header import decode_header

from apprise import plugins
from apprise import NotifyType
from apprise import Apprise
from apprise import AttachBase
from apprise import AppriseAttachment
from apprise.plugins import NotifyEmailBase

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

TEST_URLS = (
    ##################################
    # NotifyEmail
    ##################################
    ('mailto://', {
        'instance': None,
    }),
    ('mailtos://', {
        'instance': None,
    }),
    ('mailto://:@/', {
        'instance': None
    }),
    # No Username
    ('mailtos://:pass@nuxref.com:567', {
        # Can't prepare a To address using this expression
        'instance': TypeError,
    }),

    # Pre-Configured Email Services
    ('mailto://user:pass@gmail.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@hotmail.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@live.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@prontomail.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@yahoo.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@yahoo.ca', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@fastmail.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@sendgrid.com', {
        'instance': plugins.NotifyEmail,
    }),

    # Yandex
    ('mailto://user:pass@yandex.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@yandex.ru', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@yandex.fr', {
        'instance': plugins.NotifyEmail,
    }),

    # Custom Emails
    ('mailtos://user:pass@nuxref.com:567', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@nuxref.com:567?format=html', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailtos://user:pass@nuxref.com:567?to=l2g@nuxref.com', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailtos://user:pass@nuxref.com:567/l2g@nuxref.com', {
        'instance': plugins.NotifyEmail,
    }),
    (
        'mailto://user:pass@example.com:2525?user=l2g@example.com'
        '&pass=l2g@apprise!is!Awesome', {
            'instance': plugins.NotifyEmail,
        },
    ),
    (
        'mailto://user:pass@example.com:2525?user=l2g@example.com'
        '&pass=l2g@apprise!is!Awesome&format=text', {
            'instance': plugins.NotifyEmail,
        },
    ),
    (
        # Test Carbon Copy
        'mailtos://user:pass@example.com?smtp=smtp.example.com'
        '&name=l2g&cc=noreply@example.com,test@example.com', {
            'instance': plugins.NotifyEmail,
        },
    ),
    (
        # Test Blind Carbon Copy
        'mailtos://user:pass@example.com?smtp=smtp.example.com'
        '&name=l2g&bcc=noreply@example.com,test@example.com', {
            'instance': plugins.NotifyEmail,
        },
    ),
    (
        # Test Carbon Copy with bad email
        'mailtos://user:pass@example.com?smtp=smtp.example.com'
        '&name=l2g&cc=noreply@example.com,@', {
            'instance': plugins.NotifyEmail,
        },
    ),
    (
        # Test Blind Carbon Copy with bad email
        'mailtos://user:pass@example.com?smtp=smtp.example.com'
        '&name=l2g&bcc=noreply@example.com,@', {
            'instance': plugins.NotifyEmail,
        },
    ),
    # headers
    ('mailto://user:pass@localhost.localdomain'
        '?+X-Customer-Campaign-ID=Apprise', {
            'instance': plugins.NotifyEmail,
        }),
    # No Password
    ('mailtos://user:@nuxref.com', {
        'instance': plugins.NotifyEmail,
    }),
    # Invalid From Address
    ('mailtos://user:pass@nuxref.com?from=@', {
        'instance': TypeError,
    }),
    # Invalid From Address
    ('mailtos://nuxref.com?user=&pass=.', {
        'instance': TypeError,
    }),
    # Invalid To Address is accepted, but we won't be able to properly email
    # using the notify() call
    ('mailtos://user:pass@nuxref.com?to=@', {
        'instance': plugins.NotifyEmail,
        'response': False,
    }),
    # Valid URL, but can't structure a proper email
    ('mailtos://nuxref.com?user=%20!&pass=.', {
        'instance': TypeError,
    }),
    # Invalid From (and To) Address
    ('mailtos://nuxref.com?to=test', {
        'instance': TypeError,
    }),
    # Invalid Secure Mode
    ('mailtos://user:pass@example.com?mode=notamode', {
        'instance': TypeError,
    }),
    # STARTTLS flag checking
    ('mailtos://user:pass@gmail.com?mode=starttls', {
        'instance': plugins.NotifyEmail,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'mailtos://user:****@gmail.com',
    }),
    # SSL flag checking
    ('mailtos://user:pass@gmail.com?mode=ssl', {
        'instance': plugins.NotifyEmail,
    }),
    # Can make a To address using what we have (l2g@nuxref.com)
    ('mailtos://nuxref.com?user=l2g&pass=.', {
        'instance': plugins.NotifyEmail,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'mailtos://l2g:****@nuxref.com',
    }),
    ('mailto://user:pass@localhost:2525', {
        'instance': plugins.NotifyEmail,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_smtplib_exceptions': True,
    }),
    # Test no auth at all
    ('mailto://localhost?from=test@example.com&to=test@example.com', {
        'instance': plugins.NotifyEmail,
        'privacy_url': 'mailto://localhost',
    }),
    # Test multi-emails where some are bad
    ('mailto://user:pass@localhost/test@example.com/test2@/$@!/', {
        'instance': plugins.NotifyEmail,
        'privacy_url': 'mailto://user:****@localhost/'
    }),
    ('mailto://user:pass@localhost/?bcc=test2@,$@!/', {
        'instance': plugins.NotifyEmail,
    }),
    ('mailto://user:pass@localhost/?cc=test2@,$@!/', {
        'instance': plugins.NotifyEmail,
    }),
)


@mock.patch('smtplib.SMTP')
@mock.patch('smtplib.SMTP_SSL')
def test_plugin_email(mock_smtp, mock_smtpssl):
    """
    NotifyEmail() General Checks

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # iterate over our dictionary and test it out
    for (url, meta) in TEST_URLS:

        # Our expected instance
        instance = meta.get('instance', None)

        # Our expected server objects
        self = meta.get('self', None)

        # Our expected Query response (True, False, or exception type)
        response = meta.get('response', True)

        # Our expected privacy url
        # Don't set this if don't need to check it's value
        privacy_url = meta.get('privacy_url')

        test_smtplib_exceptions = meta.get(
            'test_smtplib_exceptions', False)

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
                    0, 'smtplib.SMTPHeloError() not handled'),
                smtplib.SMTPException(
                    0, 'smtplib.SMTPException() not handled'),
                RuntimeError(
                    0, 'smtplib.HTTPError() not handled'),
                smtplib.SMTPRecipientsRefused(
                    'smtplib.SMTPRecipientsRefused() not handled'),
                smtplib.SMTPSenderRefused(
                    0, 'smtplib.SMTPSenderRefused() not handled',
                    'addr@example.com'),
                smtplib.SMTPDataError(
                    0, 'smtplib.SMTPDataError() not handled'),
                smtplib.SMTPServerDisconnected(
                    'smtplib.SMTPServerDisconnected() not handled'),
            )

        try:
            obj = Apprise.instantiate(url, suppress_exceptions=False)

            if obj is None:
                # We're done (assuming this is what we were expecting)
                assert instance is None
                continue

            if instance is None:
                # Expected None but didn't get it
                print('%s instantiated %s (but expected None)' % (
                    url, str(obj)))
                assert False

            assert isinstance(obj, instance)

            if isinstance(obj, plugins.NotifyBase):
                # We loaded okay; now lets make sure we can reverse this url
                assert isinstance(obj.url(), six.string_types) is True

                # Test url() with privacy=True
                assert isinstance(
                    obj.url(privacy=True), six.string_types) is True

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
                if not isinstance(obj_cmp, plugins.NotifyBase):
                    # Assert messages are hard to trace back with the way
                    # these tests work. Just printing before throwing our
                    # assertion failure makes things easier to debug later on
                    print('TEST FAIL: {} regenerated as {}'.format(
                        url, obj.url()))
                    assert False

            if self:
                # Iterate over our expected entries inside of our object
                for key, val in self.items():
                    # Test that our object has the desired key
                    assert hasattr(key, obj)
                    assert getattr(key, obj) == val

            try:
                if test_smtplib_exceptions is False:
                    # check that we're as expected
                    assert obj.notify(
                        title='test', body='body',
                        notify_type=NotifyType.INFO) == response

                else:
                    for exception in test_smtplib_exceptions:
                        mock_socket.sendmail.side_effect = exception
                        try:
                            assert obj.notify(
                                title='test', body='body',
                                notify_type=NotifyType.INFO) is False

                        except AssertionError:
                            # Don't mess with these entries
                            raise

                        except Exception:
                            # We can't handle this exception type
                            raise

            except AssertionError:
                # Don't mess with these entries
                print('%s AssertionError' % url)
                raise

            except Exception as e:
                # Check that we were expecting this exception to happen
                if not isinstance(e, response):
                    raise

        except AssertionError:
            # Don't mess with these entries
            print('%s AssertionError' % url)
            raise

        except Exception as e:
            # Handle our exception
            if(instance is None):
                raise

            if not isinstance(e, instance):
                raise


@mock.patch('smtplib.SMTP')
@mock.patch('smtplib.SMTP_SSL')
def test_plugin_email_webbase_lookup(mock_smtp, mock_smtpssl):
    """
    NotifyEmail() Web Based Lookup Tests

    """

    # Insert a test email at the head of our table
    NotifyEmailBase.EMAIL_TEMPLATES = (
        (
            # Testing URL
            'Testing Lookup',
            re.compile(r'^(?P<id>[^@]+)@(?P<domain>l2g\.com)$', re.I),
            {
                'port': 123,
                'smtp_host': 'smtp.l2g.com',
                'secure': True,
                'login_type': (NotifyEmailBase.WebBaseLogin.USERID, )
            },
        ),
    ) + NotifyEmailBase.EMAIL_TEMPLATES

    obj = Apprise.instantiate(
        'mailto://user:pass@l2g.com', suppress_exceptions=True)

    assert isinstance(obj, plugins.NotifyEmail)
    assert len(obj.targets) == 1
    assert (False, 'user@l2g.com') in obj.targets
    assert obj.from_addr == 'user@l2g.com'
    assert obj.password == 'pass'
    assert obj.user == 'user'
    assert obj.secure is True
    assert obj.port == 123
    assert obj.smtp_host == 'smtp.l2g.com'

    # We get the same results if an email is identified as the username
    # because the USERID variable forces that we can't use an email
    obj = Apprise.instantiate(
        'mailto://_:pass@l2g.com?user=user@test.com', suppress_exceptions=True)
    assert obj.user == 'user'


@mock.patch('smtplib.SMTP')
def test_plugin_email_smtplib_init_fail(mock_smtplib):
    """
    NotifyEmail() Test exception handling when calling smtplib.SMTP()

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    obj = Apprise.instantiate(
        'mailto://user:pass@gmail.com', suppress_exceptions=False)
    assert isinstance(obj, plugins.NotifyEmail)

    # Support Exception handling of smtplib.SMTP
    mock_smtplib.side_effect = RuntimeError('Test')

    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is False

    # A handled and expected exception
    mock_smtplib.side_effect = smtplib.SMTPException('Test')
    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is False


@mock.patch('smtplib.SMTP')
def test_plugin_email_smtplib_send_okay(mock_smtplib):
    """
    NotifyEmail() Test a successfully sent email

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Defaults to HTML
    obj = Apprise.instantiate(
        'mailto://user:pass@gmail.com', suppress_exceptions=False)
    assert isinstance(obj, plugins.NotifyEmail)

    # Support an email simulation where we can correctly quit
    mock_smtplib.starttls.return_value = True
    mock_smtplib.login.return_value = True
    mock_smtplib.sendmail.return_value = True
    mock_smtplib.quit.return_value = True

    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is True

    # Set Text
    obj = Apprise.instantiate(
        'mailto://user:pass@gmail.com?format=text', suppress_exceptions=False)
    assert isinstance(obj, plugins.NotifyEmail)

    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO) is True

    # Create an apprise object to work with as well
    a = Apprise()
    assert a.add('mailto://user:pass@gmail.com?format=text')

    # Send Attachment with success
    attach = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO,
        attach=attach) is True

    # same results happen from our Apprise object
    assert a.notify(body='body', title='test', attach=attach) is True

    # test using an Apprise Attachment object
    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO,
        attach=AppriseAttachment(attach)) is True

    # same results happen from our Apprise object
    assert a.notify(
        body='body', title='test', attach=AppriseAttachment(attach)) is True

    max_file_size = AttachBase.max_file_size
    # Now do a case where the file can't be sent

    AttachBase.max_file_size = 1
    assert obj.notify(
        body='body', title='test', notify_type=NotifyType.INFO,
        attach=attach) is False

    # same results happen from our Apprise object
    assert a.notify(body='body', title='test', attach=attach) is False

    # Restore value
    AttachBase.max_file_size = max_file_size


@mock.patch('smtplib.SMTP')
def test_plugin_email_smtplib_internationalization(mock_smtp):
    """
    NotifyEmail() Internationalization Handling

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Defaults to HTML
    obj = Apprise.instantiate(
        'mailto://user:pass@gmail.com?name=Например%20так',
        suppress_exceptions=False)
    assert isinstance(obj, plugins.NotifyEmail)

    class SMTPMock(object):
        def sendmail(self, *args, **kwargs):
            """
            over-ride sendmail calls so we can check our our
            internationalization formatting went
            """

            match_subject = re.search(
                r'\n?(?P<line>Subject: (?P<subject>(.+?)))\n(?:[a-z0-9-]+:)',
                args[2], re.I | re.M | re.S)
            assert match_subject is not None

            match_from = re.search(
                r'^(?P<line>From: (?P<name>.+) <(?P<email>[^>]+)>)$',
                args[2], re.I | re.M)
            assert match_from is not None

            # Verify our output was correctly stored
            assert match_from.group('email') == 'user@gmail.com'

            if six.PY2:  # Python 2.x (backwards compatible)
                assert decode_header(match_from.group('name'))[0][0]\
                    .decode('utf-8') == u'Например так'

                assert decode_header(match_subject.group('subject'))[0][0]\
                    .decode('utf-8') == u'دعونا نجعل العالم مكانا أفضل.'

            else:  # Python 3+
                assert decode_header(match_from.group('name'))[0][0]\
                    .decode('utf-8') == 'Например так'

                assert decode_header(match_subject.group('subject'))[0][0]\
                    .decode('utf-8') == 'دعونا نجعل العالم مكانا أفضل.'

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
    assert obj.notify(
        # Google Translated to Arabic: "Let's make the world a better place."
        title='دعونا نجعل العالم مكانا أفضل.',
        # Google Translated to Hungarian: "One line of code at a time.'
        body='Egy sor kódot egyszerre.',
        notify_type=NotifyType.INFO) is True


def test_plugin_email_url_escaping():
    """
    NotifyEmail() Test that user/passwords are properly escaped from URL

    """
    # quote(' %20')
    passwd = '%20%2520'

    # Basically we want to check that ' ' equates to %20 and % equates to %25
    # So the above translates to ' %20' (a space in front of %20).  We want
    # to verify the handling of the password escaping and when it happens.
    # a very bad response would be '  ' (double space)
    obj = plugins.NotifyEmail.parse_url(
        'mailto://user:{}@gmail.com?format=text'.format(passwd))

    assert isinstance(obj, dict) is True
    assert 'password' in obj

    # Escaping doesn't happen at this stage because we want to leave this to
    # the plugins discretion
    assert obj.get('password') == '%20%2520'

    obj = Apprise.instantiate(
        'mailto://user:{}@gmail.com?format=text'.format(passwd),
        suppress_exceptions=False)
    assert isinstance(obj, plugins.NotifyEmail) is True

    # The password is escaped only 'once'
    assert obj.password == ' %20'


def test_plugin_email_url_variations():
    """
    NotifyEmail() Test URL variations to ensure parsing is correct

    """
    # Test variations of username required to be an email address
    # user@example.com
    obj = Apprise.instantiate(
        'mailto://{user}:{passwd}@example.com'.format(
            user='apprise%40example21.ca',
            passwd='abcd123'),
        suppress_exceptions=False)
    assert isinstance(obj, plugins.NotifyEmail) is True

    assert obj.password == 'abcd123'
    assert obj.user == 'apprise@example21.ca'

    # test username specified in the url body (as an argument)
    # this always over-rides the entry at the front of the url
    obj = Apprise.instantiate(
        'mailto://_:{passwd}@example.com?user={user}'.format(
            user='apprise%40example21.ca',
            passwd='abcd123'),
        suppress_exceptions=False)
    assert isinstance(obj, plugins.NotifyEmail) is True

    assert obj.password == 'abcd123'
    assert obj.user == 'apprise@example21.ca'

    # test user and password specified in the url body (as an argument)
    # this always over-rides the entries at the front of the url
    obj = Apprise.instantiate(
        'mailto://_:_@example.com?user={user}&pass={passwd}'.format(
            user='apprise%40example21.ca',
            passwd='abcd123'),
        suppress_exceptions=False)
    assert isinstance(obj, plugins.NotifyEmail) is True

    assert obj.password == 'abcd123'
    assert obj.user == 'apprise@example21.ca'
    assert len(obj.targets) == 1
    assert (False, 'apprise@example.com') in obj.targets
    assert obj.targets[0][1] == obj.from_addr

    # test user and password specified in the url body (as an argument)
    # this always over-rides the entries at the front of the url
    # this is similar to the previous test except we're only specifying
    # this information in the kwargs
    obj = Apprise.instantiate(
        'mailto://example.com?user={user}&pass={passwd}'.format(
            user='apprise%40example21.ca',
            passwd='abcd123'),
        suppress_exceptions=False)
    assert isinstance(obj, plugins.NotifyEmail) is True

    assert obj.password == 'abcd123'
    assert obj.user == 'apprise@example21.ca'
    assert len(obj.targets) == 1
    assert (False, 'apprise@example.com') in obj.targets
    assert obj.targets[0][1] == obj.from_addr
    assert obj.smtp_host == 'example.com'

    # test a complicated example
    obj = Apprise.instantiate(
        'mailtos://{user}:{passwd}@{host}:{port}'
        '?smtp={smtp_host}&format=text&from={this}&to={that}'.format(
            user='apprise%40example21.ca',
            passwd='abcd123',
            host='example.com',
            port=1234,
            this='from@example.jp',
            that='to@example.jp',
            smtp_host='smtp.example.edu'),
        suppress_exceptions=False)
    assert isinstance(obj, plugins.NotifyEmail) is True

    assert obj.password == 'abcd123'
    assert obj.user == 'apprise@example21.ca'
    assert obj.host == 'example.com'
    assert obj.port == 1234
    assert obj.smtp_host == 'smtp.example.edu'
    assert len(obj.targets) == 1
    assert (False, 'to@example.jp') in obj.targets
    assert obj.from_addr == 'from@example.jp'


def test_plugin_email_dict_variations():
    """
    NotifyEmail() Test email dictionary variations to ensure parsing is correct

    """
    # Test variations of username required to be an email address
    # user@example.com
    obj = Apprise.instantiate({
        'schema': 'mailto',
        'user': 'apprise@example.com',
        'password': 'abd123',
        'host': 'example.com'}, suppress_exceptions=False)
    assert isinstance(obj, plugins.NotifyEmail) is True
