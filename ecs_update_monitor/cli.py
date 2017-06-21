import argparse

from boto3 import Session

from ecs_update_monitor import run


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description='Monitor an ECS service update.',
        prog='ecs_update_monitor',
    )
    parser.add_argument('--cluster', help='ECS cluster name.', required=True)
    parser.add_argument('--service', help='ECS service name.', required=True)
    parser.add_argument('--taskdef', help='ECS taskdef ARN.', required=True)
    parser.add_argument('--region', help='AWS region.', required=True)
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    session = Session(region_name=args.region)
    run(args.cluster, args.service, args.taskdef, session)
