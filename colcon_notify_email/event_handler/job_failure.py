# Copyright 2022 Scott K Logan
# Licensed under the Apache License, Version 2.0

from collections import defaultdict

from colcon_core.event.job import JobEnded
from colcon_core.event.output import StderrLine
from colcon_core.event.output import StdoutLine
from colcon_core.event_handler import EventHandlerExtensionPoint
from colcon_core.logging import colcon_logger
from colcon_core.plugin_system import satisfies_version
from colcon_core.subprocess import SIGINT_RESULT
from colcon_core.verb.build import BuildPackageArguments
from colcon_core.verb.test import TestPackageArguments
from colcon_notify_email.email import send_message
from colcon_package_selection.package_selection.previous \
    import get_previous_result
from colcon_package_selection.package_selection.previous \
    import TEST_FAILURE_RESULT

logger = colcon_logger.getChild(__name__)

NUM_LINES = 100

FAILURE_TEMPLATE = """A {} job has failed for package '{}' (return code {}).

Last ~100 lines of the log:
{}"""

SUCCESS_TEMPLATE = """The {} job for package '{}' is back to normal."""

TARGET_VERBS = {
    BuildPackageArguments: 'build',
    TestPackageArguments: 'test',
}


class EmailJobFailureEventHandler(EventHandlerExtensionPoint):
    """
    Send an E-mail to concerned parties when a job fails.

    This extension relies on package identification and augmentation extensions
    to populate the 'notify_emails' metadata for packages.
    """

    # For obvious reasons, we really don't want this extension enabled
    # unless specifically requested.
    ENABLED_BY_DEFAULT = False

    # This extension must have higher priority than StoreResultEventHandler
    # from colcon-package-selection in order to read the result of the previous
    # build before it is updated with the current result.
    PRIORITY = 110

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(
            EventHandlerExtensionPoint.EXTENSION_POINT_VERSION, '^1.0')
        self.enabled = EmailJobFailureEventHandler.ENABLED_BY_DEFAULT
        self._lines = defaultdict(list)

    def __call__(self, event):  # noqa: D102
        data = event[0]

        if isinstance(data, (StderrLine, StdoutLine)):
            job = event[1]
            self._lines[job].append(data.line)
            del self._lines[job][:-NUM_LINES]
        elif isinstance(data, JobEnded):
            job = event[1]
            self._handle_job_ended(job, data.rc)
            if job in self._lines:
                del self._lines[job]

    def _handle_job_ended(self, job, rc):
        if rc == SIGINT_RESULT:
            return

        for verb_type, verb_name in TARGET_VERBS.items():
            if isinstance(job.task_context.args, verb_type):
                break
        else:
            verb_name = getattr(job.task_context.args, 'verb_name', '')
            if verb_name not in ('ros-buildfarm',):
                logger.debug('Ignoring unsupported verb')
                return

        emails = job.task_context.pkg.metadata.get('notify_emails')
        if not emails:
            logger.debug(
                'Nobody to notify of {verb_name} failure for '
                '{job.identifier}'.format_map(locals()))
            return

        if rc:
            message = FAILURE_TEMPLATE.format(
                verb_name, job.task_context.pkg.name, rc,
                '\n'.join(line.decode() for line in self._lines[job]))
            logger.info('Sending job failure E-mail to: {}'.format(
                ', '.join(emails)))
            send_message(
                message, 'Job failed in colcon: {}'.format(job.identifier),
                emails)
        else:
            previous = get_previous_result(
                job.task_context.args.build_base, verb_name)
            if previous in (None, '0', 0):
                logger.debug('Ignoring repeat success')
                return
            if verb_name == 'build' and previous == TEST_FAILURE_RESULT:
                logger.debug('Ignoring repeat success (build)')
                return

            message = SUCCESS_TEMPLATE.format(
                verb_name, job.task_context.pkg.name)
            logger.info('Sending job success E-mail to: {}'.format(
                ', '.join(emails)))
            send_message(
                message,
                'The colcon job is back to normal: {}'.format(job.identifier),
                emails)
