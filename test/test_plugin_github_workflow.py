# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

import requests
import pytest
from apprise import Apprise
from apprise import NotifyType
from apprise.plugins.github_workflow import NotifyGitHubWorkflow
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyGitHubWorkflow
    ##################################
    ('github+workflow://', {
        # invalid host details (parsing fails very early)
        'instance': None,
    }),
    ('github+workflow://:@/', {
        # invalid host details (parsing fails very early)
        'instance': None,
    }),
    ('github+workflow://token@repository/workflow', {
        # All tokens provided - we're good
        'instance': NotifyGitHubWorkflow,
    }),
    ('github+workflow://token@repository/workflow', {
        'instance': NotifyGitHubWorkflow,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('github+workflow://token@repository/workflow', {
        'instance': NotifyGitHubWorkflow,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('github+workflow://token@repository/workflow', {
        'instance': NotifyGitHubWorkflow,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_github_workflow_urls():
    """
    NotifyGitHubWorkflow() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@pytest.fixture
def github_workflow_url():
    return 'github+workflow://token@repository/workflow'


@pytest.fixture
def request_mock(mocker):
    """
    Prepare requests mock.
    """
    mock_post = mocker.patch("requests.post")
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.no_content
    return mock_post


def test_plugin_github_workflow_send_success(request_mock, github_workflow_url):
    """
    NotifyGitHubWorkflow() Send - success.
    Test cases where URL and JSON is valid.
    """

    # Instantiate our URL
    obj = Apprise.instantiate(github_workflow_url)

    assert isinstance(obj, NotifyGitHubWorkflow)
    assert obj.notify(
        body="body", title='title',
        notify_type=NotifyType.INFO) is True

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        'https://api.github.com/repos/repository/actions/workflows/workflow/dispatches')

    # Our Posted JSON Object
    posted_json = request_mock.call_args_list[0][1]['json']
    assert 'ref' in posted_json
    assert posted_json['ref'] == 'main'
    assert 'inputs' in posted_json
    assert posted_json['inputs']['title'] == 'title'
    assert posted_json['inputs']['body'] == 'body'


def test_plugin_github_workflow_send_failure(request_mock, github_workflow_url):
    """
    NotifyGitHubWorkflow() Send - failure.
    Test cases where URL and JSON is invalid.
    """

    # Instantiate our URL
    obj = Apprise.instantiate(github_workflow_url)

    assert isinstance(obj, NotifyGitHubWorkflow)

    # Simulate a failure response
    request_mock.return_value.status_code = requests.codes.bad_request

    assert obj.notify(
        body="body", title='title',
        notify_type=NotifyType.INFO) is False

    assert request_mock.called is True
    assert request_mock.call_args_list[0][0][0].startswith(
        'https://api.github.com/repos/repository/actions/workflows/workflow/dispatches')

    # Our Posted JSON Object
    posted_json = request_mock.call_args_list[0][1]['json']
    assert 'ref' in posted_json
    assert posted_json['ref'] == 'main'
    assert 'inputs' in posted_json
    assert posted_json['inputs']['title'] == 'title'
    assert posted_json['inputs']['body'] == 'body'


def test_plugin_github_workflow_edge_cases():
    """
    NotifyGitHubWorkflow() Edge Cases

    """
    # Initializes the plugin with an invalid token
    with pytest.raises(TypeError):
        NotifyGitHubWorkflow(token='@', repository='repo', workflow='workflow')
    with pytest.raises(TypeError):
        NotifyGitHubWorkflow(token='', repository='repo', workflow='workflow')

    with pytest.raises(TypeError):
        NotifyGitHubWorkflow(token=None, repository='repo', workflow='workflow')
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyGitHubWorkflow(token='  ', repository='repo', workflow='workflow')

    with pytest.raises(TypeError):
        NotifyGitHubWorkflow(token='token', repository=None, workflow='workflow')
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyGitHubWorkflow(token='token', repository='  ', workflow='workflow')

    with pytest.raises(TypeError):
        NotifyGitHubWorkflow(token='token', repository='repo', workflow=None)
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyGitHubWorkflow(token='token', repository='repo', workflow='  ')

    # test case where no tokens are specified
    obj = NotifyGitHubWorkflow(token='token', repository='repo', workflow='workflow')
    assert isinstance(obj, NotifyGitHubWorkflow)
