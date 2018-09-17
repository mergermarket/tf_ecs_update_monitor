import argparse
import sys
from re import match

from boto3 import Session

from ecs_update_monitor import run, UserFacingError
from ecs_update_monitor.logger import logger


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description='Monitor an ECS service update.',
        prog='ecs_update_monitor',
    )
    parser.add_argument('--cluster', help='ECS cluster name.', required=True)
    parser.add_argument('--service', help='ECS service name.', required=True)
    parser.add_argument('--taskdef', help='ECS taskdef ARN.', required=True)
    parser.add_argument('--region', help='AWS region.', required=True)
    parser.add_argument(
        '--caller-arn', help='ARN of caller.', required=False
    )
    return parser.parse_args(argv)


def switch_role(sts, caller_arn, region):
    m = match(
        r'arn:aws:sts::(\d+):assumed-role/'
        r'([\w+=,.@_/-]{1,64})/([\w=,.@-]{0,64})$',
        caller_arn
    )
    if m is None:
        raise Exception(
            'IAM caller did not match terraform, but caller arn did not '
            'match expected pattern ("{}")'.format(caller_arn)
        )
    response = sts.assume_role(
        RoleArn='arn:aws:iam::{}:role/{}'.format(m.group(1), m.group(2)),
        RoleSessionName=m.group(3)
    )
    return Session(
        aws_access_key_id=response['Credentials']['AccessKeyId'],
        aws_secret_access_key=response['Credentials']['SecretAccessKey'],
        aws_session_token=response['Credentials']['SessionToken'],
        region_name=region
    )


def main(argv):
    args = parse_args(argv)
    session = Session(region_name=args.region)
    sts = session.client('sts')
    caller = sts.get_caller_identity()
    if caller['Arn'] != args.caller_arn:
        session = switch_role(sts, args.caller_arn, args.region)
    try:
        run(args.cluster, args.service, args.taskdef, session)
    except UserFacingError as e:
        logger.error(str(e))
        sys.exit(1)
