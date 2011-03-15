"""
This module contains common steps that may appear in multiple different
tasks.
"""

from dz.tasklib import (taskconfig,
                        utils)
import os


def checkout_code(zoomdb, opts):
    """
    Checkout code from opts["SRC_URL"] into opts["CO_DIR"].
    """
    d = opts["CO_DIR"]
    source_code_url = opts["SRC_URL"]

    if not os.path.exists(d):
        os.makedirs(d)

    if source_code_url.startswith(taskconfig.TEST_REPO_URL_PREFIX):
        repourl = os.path.join(taskconfig.TEST_REPO_DIR,
                               source_code_url[len(
                    taskconfig.TEST_REPO_URL_PREFIX):])
    else:
        repourl = source_code_url

    cur_dir = os.getcwd()
    try:
        os.chdir(d)

        if os.path.exists(".git"):
            zoomdb.log("Updating code from repository.")
            cmd = ["git", "pull"]
        else:
            zoomdb.log("Cloning your repository.")
            cmd = ["git", "clone", repourl, "."]

        output, stderr, p = utils.subproc(cmd)
        if p.returncode != 0:
            raise utils.ProjectConfigurationException(
                "Error updating code from repository %s:\n%s" % (
                    repourl, stderr))
        zoomdb.log("Running %s..." % " ".join(cmd))

    finally:
        os.chdir(cur_dir)
