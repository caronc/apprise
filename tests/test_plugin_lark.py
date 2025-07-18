# Disable logging for a cleaner testing output
import logging

from helpers import AppriseURLTester
import requests

from apprise.plugins.lark import NotifyLark

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "lark://",
        {
            # Teams Token missing
            "instance": TypeError,
        },
    ),
    (
        "lark://:@/",
        {
            # We don't have strict host checking on for lark, so this URL
            # actually becomes parseable and :@ becomes a hostname.
            # The below errors because a second token wasn't found
            "instance": TypeError,
        },
    ),
    (
        "lark://{}".format("abcd-1234"),
        {
            # token provided - we're good
            "instance": NotifyLark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "lark://****/",
        },
    ),
    (
        "lark://{}".format("abcd-1234"),
        {
            # token provided - we're good
            "instance": NotifyLark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "lark://****/",
        },
    ),
    (
        "lark://?token={}".format("abcd-1234"),
        {
            # token provided - we're good
            "instance": NotifyLark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "lark://****/",
        },
    ),
    # Support Native URLs with arguments
    (
        "https://open.larksuite.com/open-apis/bot/v2/hook/{}".format(
            "abcd-1234"
        ),
        {
            # token provided - we're good
            "instance": NotifyLark,
        },
    ),
    (
        "lark://{}".format("abcd-1234"),
        {
            "instance": NotifyLark,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "lark://{}".format("abcd-1234"),
        {
            "instance": NotifyLark,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "lark://{}".format("a" * 80),
        {
            "instance": NotifyLark,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_lark_urls():
    """NotifyLark() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
