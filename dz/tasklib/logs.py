"""
Functions for fetching log files.

- Get app's access log from nginx on proxy
- Given an instance (and implied bundle), get:
  * process stdout
  * process stderr
"""

import glob
import os

from dz.tasklib import taskconfig


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


def get_available_logs(app_id):
    """
    Returns locally available logs for the given app_id.
    Format: list of (filename, caption, size).
    """

    result = []

    # first look for supervisor logs
    # bundle_test001_2011-07-08-03.40.29-stderr---supervisor-oDRZja.log
    # bundle_test001_2011-07-08-03.40.29-stdout---supervisor-TuBrcm.log
    for suffix, caption in (("stderr", "Application Standard Error"),
                            ("stdout", "Application Standard Output")):
        filename = _supervisor_log_filename(app_id, suffix)
        if filename:
            result.append((filename, caption, _filesize(filename)))

    # now look for nginx logs
    nginx_log_path = os.path.join("/tmp", "%s.access.log")
    if os.path.isfile(nginx_log_path):
        result.append((nginx_log_path,
                       "Web Server Access Log",
                       _filesize(nginx_log_path)))

    return result
