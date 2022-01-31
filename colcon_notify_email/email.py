# Copyright 2022 Scott K Logan
# Licensed under the Apache License, Version 2.0

import os
from smtplib import SMTP
from socket import gethostname

from colcon_core.environment_variable import EnvironmentVariable


EMAIL_FROM_VARIABLE = EnvironmentVariable(
    'COLCON_EMAIL_FROM_ADDRESS',
    "Set the E-mail address to show in the 'From:' field for messages sent by"
    'colcon (default: <current_user>@<current_hostname>)')


EMAIL_SERVER_VARIABLE = EnvironmentVariable(
    'COLCON_EMAIL_SERVER_ADDRESS',
    'Set the IP address of the SMTP server to use when sending E-mail messages'
    'from colcon (default: localhost)')


def send_message(message, subject, recipients):
    """
    Send an email message.

    :param message: Formatted E-mail message
    :param recipients: List of formatted addresses to send the message to
    """
    from_addr = os.environ.get(EMAIL_FROM_VARIABLE.name)
    server_addr = os.environ.get(EMAIL_SERVER_VARIABLE.name, 'localhost')

    if not from_addr:
        from_addr = _determine_from_addr()

    message = 'From: {}\nTo: {}\nSubject: {}\n{}'.format(
        from_addr, ', '.join(recipients), subject, message)

    with SMTP(server_addr) as smtp:
        smtp.sendmail(from_addr, recipients, message)


def _determine_from_addr():
    return 'colcon <{}@{}>'.format(os.getlogin(), gethostname())
