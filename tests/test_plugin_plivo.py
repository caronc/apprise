# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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

# Disable logging for a cleaner testing output
import logging

from helpers import AppriseURLTester

from apprise.plugins.plivo import NotifyPlivo

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "plivo://",
        {
            # No hostname/apikey specified
            "instance": TypeError,
        },
    ),
    (
        "plivo://{}@{}/15551232000".format("a" * 10, "a" * 25),
        {
            # invalid auth id
            "instance": TypeError,
        },
    ),
    (
        "plivo://{}@{}/15551232000".format("a" * 25, "a" * 10),
        {
            # invalid token
            "instance": TypeError,
        },
    ),
    (
        "plivo://{}@{}/123".format("a" * 25, "a" * 40),
        {
            # invalid phone number
            "instance": TypeError,
        },
    ),
    (
        "plivo://{}@{}/abc".format("a" * 25, "a" * 40),
        {
            # invalid phone number
            "instance": TypeError,
        },
    ),
    (
        "plivo://{}@{}/15551231234".format("a" * 25, "b" * 40),
        {
            # target phone number becomes who we text too; all is good
            "instance": NotifyPlivo,
        },
    ),
    (
        "plivo://{}@{}/15551232000/abcd".format("a" * 25, "a" * 40),
        {
            # invalid target phone number
            "instance": NotifyPlivo,
            # Notify will fail because it couldn't send to anyone
            "response": False,
        },
    ),
    (
        "plivo://{}@{}/15551232000/123".format("a" * 25, "a" * 40),
        {
            # invalid target phone number
            "instance": NotifyPlivo,
            # Notify will fail because it couldn't send to anyone
            "response": False,
        },
    ),
    (
        "plivo://{}@{}/?from=15551233000&to=15551232000&batch=yes".format(
            "a" * 25, "a" * 40
        ),
        {
            # reference to to= and from=
            "instance": NotifyPlivo,
        },
    ),
    (
        "plivo://?id={}&token={}&from=15551233000&to=15551232000".format(
            "a" * 25, "a" * 40
        ),
        {
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "plivo://a...a@a...a/+15551233000/+15551232000",
            # reference to to= and from=
            "instance": NotifyPlivo,
        },
    ),
    (
        "plivo://15551232123?id={}&token={}&from=15551233000"
        "&to=15551232000".format("a" * 25, "a" * 40),
        {
            # reference to to= and from=
            "instance": NotifyPlivo,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "plivo://a...a@a...a/+15551233000/+15551232123",
        },
    ),
    (
        "plivo://{}@{}/15551232000".format("a" * 25, "a" * 40),
        {
            "instance": NotifyPlivo,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "plivo://{}@{}/15551232000".format("a" * 25, "a" * 40),
        {
            "instance": NotifyPlivo,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_plivo_urls():
    """NotifyPlivo() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
