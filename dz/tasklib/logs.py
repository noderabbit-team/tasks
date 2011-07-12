"""
Functions for fetching log files.

- Get app's access log from nginx on proxy
- Given an instance (and implied bundle), get:
  * process stdout
  * process stderr
"""

import glob
import os

from dz.tasklib import (taskconfig,
                        utils)


class UnavailableLogError(Exception):
    """
    Indicates that the specified log is not available. May indicate that the
    file was deleted, or that the requested log id isn't associated with the
    specified app_id.
    """


def _supervisor_log_filename(app_id, suffix):
    glob_expr = os.path.join(
        taskconfig.LOG_DIR_SUPERVISOR,
        "bundle_%s_*-%s---supervisor-*.log" % (app_id, suffix))
    matches = glob.glob(glob_expr)
    if len(matches) == 0:
        return None
    return sorted(matches)[-1]


def _filesize(path):
    return os.path.getsize(path)


def _mod_time(path):
    return os.path.getmtime(path)


def get_available_logs(app_id):
    """
    Returns locally available logs for the given app_id.
    :returns: A list of (log_id, caption, size). ``log_id`` is a string
              (usually a filename).>
    """
    # first look for supervisor logs
    # bundle_test001_2011-07-08-03.40.29-stderr---supervisor-oDRZja.log
    # bundle_test001_2011-07-08-03.40.29-stdout---supervisor-TuBrcm.log
    for suffix, caption in (("stderr", "Application Standard Error"),
                            ("stdout", "Application Standard Output")):
        filename = _supervisor_log_filename(app_id, suffix)
        if filename:
            yield dict(log_id=filename,
                       caption=caption,
                       filesize=_filesize(filename),
                       mod_time=_mod_time(filename))

    # now look for nginx logs
    nginx_log_path = os.path.join("/tmp", "%s.access.log" % app_id)
    if os.path.isfile(nginx_log_path):
        yield dict(log_id=nginx_log_path,
                   caption="Web Server Access Log",
                   filesize=_filesize(nginx_log_path),
                   mod_time=_mod_time(filename))


def get_log_content(app_id, log_id, lines=100):
    """
    Get the bottom ``lines`` of content from the given log.

    :returns: A string containing no more than ``lines`` lines.
    """
    is_allowed = any(x["log_id"] == log_id for x in get_available_logs(app_id))
    if not is_allowed:
        raise UnavailableLogError(
            "Requested log %s is not available [app_id: %s]." %
            (log_id, app_id))
    return utils.local_privileged(["logtail", str(lines), log_id])
