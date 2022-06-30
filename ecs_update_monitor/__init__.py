from time import sleep, time
from ecs_update_monitor.logger import logger

MAX_FAILURES = 3


class UserFacingError(Exception):
    pass


def run(cluster, service, taskdef, boto_session):
    event_iterator = ECSEventIterator(cluster, service, taskdef, boto_session)
    monitor = ECSMonitor(event_iterator)
    monitor.wait()


class ECSMonitor:

    _TIMEOUT = 600
    _INTERVAL = 15

    def __init__(self, ecs_event_iterator):
        self._ecs_event_iterator = ecs_event_iterator
        self._previous_running_count = 0
        self._failed_count = 0

    def wait(self):
        self._check_ecs_deploy_progress()

    def _check_ecs_deploy_progress(self):
        start = time()
        for event in self._ecs_event_iterator:
            self._show_deployment_progress(event)
            self._check_for_failed_tasks(event)
            if event.done:
                return True
            if time() - start > self._TIMEOUT:
                raise TimeoutError(
                    'Deployment timed out - didn\'t complete '
                    'within {} seconds'.format(self._TIMEOUT)
                )
            sleep(self._INTERVAL)

    def _show_deployment_progress(self, event):
        for message in event.messages:
            logger.info(message)

    def _check_for_failed_tasks(self, event):
        if event.running < self._previous_running_count:
            self._failed_count += self._previous_running_count - event.running
            if self._failed_count >= MAX_FAILURES:
                raise FailedTasksError
        self._previous_running_count = event.running


class ECSEventIterator:

    _INTERVAL = 15
    _NEW_SERVICE_GRACE_PERIOD = 60

    def __init__(self, cluster, service, taskdef, boto_session):
        self._cluster = cluster
        self._service = service
        self._taskdef = taskdef
        self._boto_session = boto_session
        self._done = False
        self._seen_ecs_service_events = set()
        self._new_service_deployment = None
        self._new_service_grace_period = self._NEW_SERVICE_GRACE_PERIOD
        self._ecs_client = None
        self._taskdef_images = {}

    def __iter__(self):
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        if self._done:
            raise StopIteration

        ecs_service_data = self._ecs.describe_services(
            cluster=self._cluster,
            services=[self._service]
        )

        deployments = self._get_deployments(ecs_service_data)
        primary_deployment = self._get_primary_deployment(deployments)
        self._check_taskdef(primary_deployment)

        running = primary_deployment['runningCount']
        pending = primary_deployment['pendingCount']
        desired = primary_deployment['desiredCount']
        previous_running = self._get_previous_running_count(deployments)
        messages = self._get_task_event_messages(
            ecs_service_data, primary_deployment
        )

        if self._new_service_deployment is None:
            self._new_service_deployment = previous_running == 0

        if self._deploy_in_progress(running, desired, previous_running):
            return InProgressEvent(
                running, pending, desired, previous_running, messages
            )

        self._done = True
        return DoneEvent(
            running, pending, desired, previous_running, messages
        )

    def _check_taskdef(self, primary_deployment):
        if primary_deployment['taskDefinition'] != self._taskdef:
            raise TaskdefDoesNotMatchError(
                self._taskdef, primary_deployment['taskDefinition']
            )

    def _deploy_in_progress(self, running, desired, previous_running):
        if running != desired or previous_running:
            return True
        elif (running == desired and self._new_service_deployment and
                self._new_service_grace_period > 0):
            self._new_service_grace_period -= self._INTERVAL
            return True

        return False

    @property
    def _ecs(self):
        if self._ecs_client is None:
            self._ecs_client = self._boto_session.client('ecs')
        return self._ecs_client

    def _get_new_ecs_service_events(self, ecs_service_data, since):
        filtered_ecs_events = [
            event
            for event in ecs_service_data['services'][0].get('events', [])
            if event['id'] not in self._seen_ecs_service_events and
            event['createdAt'] > since
        ]

        for event in filtered_ecs_events:
            self._seen_ecs_service_events.add(event['id'])

        return list(reversed(filtered_ecs_events))

    def _get_task_event_messages(self, ecs_service_data, primary_deployment):
        return [
            event['message']
            for event in self._get_new_ecs_service_events(
                ecs_service_data, primary_deployment['createdAt']
            )
        ]

    def _get_deployments(self, ecs_service_data):
        return [
            deployment
            for deployment in ecs_service_data['services'][0]['deployments']
        ]

    def _get_primary_deployment(self, deployments):
        deployments = [
            deployment
            for deployment in deployments
            if deployment['status'] == 'PRIMARY'
        ]
        assert len(deployments) == 1, 'assume just one primary deployment'
        return deployments[0]

    def _get_previous_running_count(self, deployments):
        return sum(
            deployment['runningCount']
            for deployment in deployments
            if deployment['status'] != 'PRIMARY'
        )


class Event:

    def __init__(self, running, pending, desired, previous_running, messages):
        self.running = running
        self.pending = pending
        self.desired = desired
        self.previous_running = previous_running
        self.messages = messages


class DoneEvent(Event):

    @property
    def done(self):
        return True


class InProgressEvent(Event):

    @property
    def done(self):
        return False


class TaskdefDoesNotMatchError(Exception):
    def __init__(self, expected, actual):
        self._expected = expected
        self._actual = actual

    def __str__(self):
        return 'found primary deployment with taskdef {} ' \
            'while waiting for deployment of taskdef {}'.format(
                self._actual, self._expected
            )


class TimeoutError(UserFacingError):
    pass


class FailedTasksError(UserFacingError):
    def __str__(_):
        return 'Deployment failed - {} new tasks have failed'.format(
            MAX_FAILURES
        )
