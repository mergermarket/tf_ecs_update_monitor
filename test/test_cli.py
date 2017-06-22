import unittest
from contextlib import contextmanager

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

import sys

from mock import Mock, patch
from string import ascii_letters, digits
from hypothesis import given, assume
from hypothesis.strategies import text, fixed_dictionaries

from ecs_update_monitor import cli


IDENTIFIERS = ascii_letters + digits + '-_'


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
    }))
    def test_command_line_paramters_used(self, fixtures):

        assume(fixtures['cluster'][0] != '-')
        assume(fixtures['service'][0] != '-')
        assume(fixtures['taskdef'][0] != '-')
        assume(fixtures['region'][0] != '-')

        # Given
        with patch('ecs_update_monitor.cli.Session') as Session, \
                patch('ecs_update_monitor.cli.run') as run:

            session = Mock()
            Session.return_value = session

            cluster = fixtures['cluster']
            service = fixtures['service']
            taskdef = fixtures['taskdef']
            region = fixtures['region']

            print("cluster {} service {} taskdef {} region {}".format(
                cluster, service, taskdef, region
            ))

            # When
            cli.main([
                '--cluster', cluster, '--service', service,
                '--taskdef', taskdef, '--region', region,
            ])

            # Then
            Session.assert_called_once_with(region_name=region)
            run.assert_called_once_with(
                cluster, service, taskdef, session
            )
