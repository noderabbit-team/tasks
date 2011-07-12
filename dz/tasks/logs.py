"""
This module contains 'jobs' for getting application log segments. These are
implemented as broadcast commands, rather than celery jobs, in order to
faciliate a rapid response. This approach probably does not scale well,
though.
"""

import datetime

from celery.task.control import broadcast
from celery.worker.control import Panel
from dz.tasklib import (logs,
                        utils,
                        taskconfig)

MY_HOSTNAME = utils.node_meta("name")

LOG_SERVICE_NOT_AVAILABLE = object()


@Panel.register
def distlog_get_available_logs(panel, app_id=None):
    panel.logger.info("Remote control distlog_get_available_logs request, "
                      "app_id=%s." % app_id)

    if not app_id:
        raise ValueError("distlog_get_available_logs: "
                         "Missing parameter app_id.")

    result = []
    for loginfo in logs.get_available_logs(app_id):
        loginfo["hostname"] = MY_HOSTNAME
        result.append(loginfo)
    return result


@Panel.register
def distlog_get_log_content(panel, app_id=None, hostname=None,
                            log_id=None, lines=100):
    panel.logger.info("Remote control distlog_get_log_content request, "
                      "app_id=%s hostname=%s log_id=%s lines=%d." % (
                          app_id, hostname, log_id, lines))
    if not (app_id and log_id and hostname):
        return None

    if hostname != MY_HOSTNAME:
        return None

    return logs.get_log_content(app_id, log_id, lines)


def find_available_logs(app_id):
    """
    Query all log-keeping servers for logs pertaining to the given app.
    """
    found_logs = broadcast("distlog_get_available_logs",
                           arguments={"app_id": app_id}, reply=True,
                           timeout=taskconfig.LOGS_CELERY_BCAST_TIMEOUT)
    if not found_logs:
        return LOG_SERVICE_NOT_AVAILABLE

    result = []
    for nodedict in found_logs:
        for node, logs_from_node in nodedict.items():
            if logs_from_node:
                for loginfo in logs_from_node:
                    loginfo["mod_dt"] = datetime.datetime.fromtimestamp(
                        loginfo["mod_time"])
                    result.append(loginfo)
    return result


def retrieve_log_page(app_id, hostname, log_id):
    """
    Get a page of log content.
    """
    log_contents = broadcast("distlog_get_log_content",
                             destination=[hostname],
                             arguments={"app_id": app_id,
                                        "hostname": hostname,
                                        "log_id": log_id},
                             reply=True,
                             timeout=taskconfig.LOGS_CELERY_BCAST_TIMEOUT)
    for host_response in log_contents:
        for host, result in host_response.iteritems():
            if result:
                return result

    return ""
