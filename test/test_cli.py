import unittest
from datetime import datetime
from contextlib import contextmanager

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import sys

from itertools import cycle
from mock import Mock, patch, ANY
from string import ascii_letters, digits
from hypothesis import given, assume
from hypothesis.strategies import text, fixed_dictionaries

from ecs_update_monitor import (
    cli, ECSMonitor, InProgressEvent
)


IDENTIFIERS = ascii_letters + digits + '-_'
ROLE_NAMES = ascii_letters + digits + '+=,.@_-/'
SESSION_NAMES = ascii_letters + digits + '=,.@-'


@contextmanager
def capture_stderr():
    output = StringIO()
    save = sys.stderr
    try:
        sys.stderr = output
        yield output
    finally:
        sys.stderr = save


class TestECSMonitorCLI(unittest.TestCase):

    def test_required_parameters(self):
        # Given

        # When
        with self.assertRaises(SystemExit) as exit, capture_stderr() as errors:
            cli.main([])

        # Then
        assert exit.exception.code != 0
        try:
            assert 'the following arguments are required: {}'.format(
                '--cluster, --service, --taskdef, --region'
            ) in errors.getvalue()
        except AssertionError:
            print("python version is {}".format(sys.version_info))
            if sys.version_info.major == 2:
                # use a slightly watered down assertion for python 2
                assert 'argument --cluster is required' in errors.getvalue()
            else:
                raise

    @given(fixed_dictionaries({
        'cluster': text(min_size=1, alphabet=IDENTIFIERS),
        'service': text(min_size=1, alphabet=IDENTIFIERS),
        'taskdef': text(min_size=1, alphabet=IDENTIFIERS),
        'region': text(min_size=1, alphabet=IDENTIFIERS),
        'caller_arn': text(min_size=1, alphabet=IDENTIFIERS),
    }))
    def test_command_line_paramters_used(self, fixtures):

        assume(fixtures['cluster'][0] != '-')
        assume(fixtures['service'][0] != '-')
        assume(fixtures['taskdef'][0] != '-')
        assume(fixtures['region'][0] != '-')
        assume(fixtures['caller_arn'][0] != '-')

        # Given
        with patch('ecs_update_monitor.cli.Session') as Session, \
                patch('ecs_update_monitor.cli.run') as run:

            cluster = fixtures['cluster']
            service = fixtures['service']
            taskdef = fixtures['taskdef']
            region = fixtures['region']
            caller_arn = fixtures['caller_arn']

            session = Mock()
            Session.return_value = session
            mock_sts = Mock()
            mock_sts.get_caller_identity.return_value = {
                "Arn": caller_arn
            }
            session.client.return_value = mock_sts

            # When
            cli.main([
                '--cluster', cluster, '--service', service,
                '--taskdef', taskdef, '--region', region,
                '--caller-arn', caller_arn
            ])

            # Then
            Session.assert_called_once_with(region_name=region)
            session.client.assert_called_once_with('sts')
            mock_sts.get_caller_identity.assert_called_once_with()
            run.assert_called_once_with(
                cluster, service, taskdef, session
            )

    @given(fixed_dictionaries({
        'region': text(min_size=1, alphabet=IDENTIFIERS),
        'role': text(min_size=1, max_size=64, alphabet=ROLE_NAMES),
        'session_name': text(min_size=1, max_size=64, alphabet=SESSION_NAMES),
        'account_id': text(min_size=1, alphabet=digits),
        'access_key': text(min_size=1, alphabet=IDENTIFIERS),
        'secret_key': text(min_size=1, alphabet=IDENTIFIERS),
        'token': text(min_size=1, alphabet=IDENTIFIERS),
    }))
    def test_role_assumed(self, fixtures):

        assume(fixtures['region'][0] != '-')

        # Given
        with patch('ecs_update_monitor.cli.Session') as Session, \
                patch('ecs_update_monitor.cli.run') as run:

            root_session = Mock()
            assumed_session = Mock()

            def SessionContructor(
                aws_access_key_id=None, aws_secret_access_key=None,
                aws_session_token=None, region_name=None
            ):
                if aws_access_key_id is not None:
                    return assumed_session
                else:
                    return root_session

            Session.side_effect = SessionContructor
            mock_sts = Mock()
            mock_sts.get_caller_identity.return_value = {
                'Arn': 'something-not-the-same'
            }
            mock_sts.assume_role.return_value = {
                'Credentials': {
                    'AccessKeyId': fixtures['access_key'],
                    'SecretAccessKey': fixtures['secret_key'],
                    'SessionToken': fixtures['token'],
                    'Expiration': datetime(2015, 1, 1),
                }
            }
            root_session.client.return_value = mock_sts

            # When
            cli.main([
                '--cluster', 'dummy', '--service', 'dummy',
                '--taskdef', 'dummy', '--region', fixtures['region'],
                '--caller-arn', 'arn:aws:sts::{}:assumed-role/{}/{}'.format(
                    fixtures['account_id'], fixtures['role'],
                    fixtures['session_name']
                ),
            ])

            # Then
            Session.assert_any_call(region_name=fixtures['region'])
            root_session.client.assert_called_once_with('sts')
            mock_sts.get_caller_identity.assert_called_once_with()
            mock_sts.assume_role.assert_called_once_with(
                RoleArn='arn:aws:iam::{}:role/{}'.format(
                    fixtures['account_id'], fixtures['role']
                ),
                RoleSessionName=fixtures['session_name'],
            )
            Session.assert_any_call(
                region_name=fixtures['region'],
                aws_access_key_id=fixtures['access_key'],
                aws_secret_access_key=fixtures['secret_key'],
                aws_session_token=fixtures['token'],
            )
            run.assert_called_once_with(
                ANY, ANY, ANY, assumed_session
            )

    @patch('ecs_update_monitor.ECSMonitor')
    @patch('ecs_update_monitor.ECSEventIterator')
    @patch('ecs_update_monitor.cli.Session')
    def test_run_failure_error(self, mock_session, mock_iter, mock_monitor):
        # Given
        root_session = Mock()
        assumed_session = Mock()

        def SessionContructor(
            aws_access_key_id=None, aws_secret_access_key=None,
            aws_session_token=None, region_name=None
        ):
            if aws_access_key_id is not None:
                return assumed_session
            else:
                return root_session

        mock_session.side_effect = SessionContructor
        mock_arn = 'arn:aws:sts::{}:assumed-role/{}/{}'.format(
                '1234567890', 'role', 'session_name'
        )
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {
            'Arn': mock_arn
        }
        mock_sts.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': 'access_key',
                'SecretAccessKey': 'secret_key',
                'SessionToken': 'token',
                'Expiration': datetime(2015, 1, 1),
            }
        }
        root_session.client.return_value = mock_sts
        mock_iter.return_value = Mock()
        ecs_event_iterator = [
            # running, pending, desired, previous
            InProgressEvent(0, 1, 2, 2, []),
            InProgressEvent(1, 1, 2, 2, []),
            InProgressEvent(2, 0, 2, 2, []),
            InProgressEvent(1, 0, 2, 2, []),
            InProgressEvent(1, 1, 2, 2, []),
            InProgressEvent(2, 0, 2, 2, []),
            InProgressEvent(1, 0, 2, 2, []),
            InProgressEvent(1, 1, 2, 2, []),
            InProgressEvent(2, 0, 2, 2, []),
            InProgressEvent(1, 0, 2, 2, []),
        ]
        ecs_monitor = ECSMonitor(ecs_event_iterator, 'dummy', mock_session)
        ecs_monitor._INTERVAL = 0
        mock_monitor.return_value = ecs_monitor
        # When
        with unittest.TestCase.assertLogs(
            self, 'ecs_update_monitor.logger', level='ERROR'
        ) as logs, self.assertRaises(SystemExit) as exit:
            cli.main([
                '--cluster', 'dummy', '--service', 'dummy',
                '--taskdef', 'dummy', '--region', 'region',
                '--caller-arn', mock_arn
            ])

        # Then
        assert logs.output == [(
            'ERROR:ecs_update_monitor.logger:Deployment failed - '
            '3 new tasks have failed'
        )]
        assert exit.exception.code != 0

    @patch('ecs_update_monitor.ECSMonitor')
    @patch('ecs_update_monitor.ECSEventIterator')
    @patch('ecs_update_monitor.cli.Session')
    def test_run_timeout_error(self, mock_session, mock_iter, mock_monitor):
        # Given
        root_session = Mock()
        assumed_session = Mock()

        def SessionContructor(
            aws_access_key_id=None, aws_secret_access_key=None,
            aws_session_token=None, region_name=None
        ):
            if aws_access_key_id is not None:
                return assumed_session
            else:
                return root_session

        mock_session.side_effect = SessionContructor
        mock_arn = 'arn:aws:sts::{}:assumed-role/{}/{}'.format(
                '1234567890', 'role', 'session_name'
        )
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {
            'Arn': mock_arn
        }
        mock_sts.assume_role.return_value = {
            'Credentials': {
                'AccessKeyId': 'access_key',
                'SecretAccessKey': 'secret_key',
                'SessionToken': 'token',
                'Expiration': datetime(2015, 1, 1),
            }
        }
        root_session.client.return_value = mock_sts
        mock_iter.return_value = Mock()

        ecs_event_iterator = cycle([
            InProgressEvent(0, 0, 2, 0, []),
            InProgressEvent(0, 0, 2, 0, []),
        ])
        ecs_monitor = ECSMonitor(ecs_event_iterator, 'dummy', mock_session)
        ecs_monitor._INTERVAL = 0.1
        ecs_monitor._TIMEOUT = 0.1
        mock_monitor.return_value = ecs_monitor
        # When
        with unittest.TestCase.assertLogs(
            self, 'ecs_update_monitor.logger', level='ERROR'
        ) as logs, self.assertRaises(SystemExit) as exit:
            cli.main([
                '--cluster', 'dummy', '--service', 'dummy',
                '--taskdef', 'dummy', '--region', 'region',
                '--caller-arn', mock_arn
            ])

        # Then
        assert logs.output == [(
            'ERROR:ecs_update_monitor.logger:Deployment timed out - '
            'didn\'t complete within 0.1 seconds'
        )]
        assert exit.exception.code != 0
