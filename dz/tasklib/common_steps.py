"""
This module contains common steps that may appear in multiple different
tasks.
"""

from dz.tasklib import (taskconfig,
                        utils,
                        vcs_handlers)
import os
import shutil


def _get_remote_origin_url(repodir):
    gitdir = os.path.join(repodir, ".git")
    output, stderr, p = utils.subproc(["git",
                                       "--git-dir=%s" % gitdir,
                                       "remote", "show", "origin"],
                                      redir_stderr_to_stdout=True)
    if p.returncode != 0:
        raise utils.InfrastructureException(
            "Error trying to determine current remote URL for repo: %s"
            % output)

    prefix = "  Fetch URL: "
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()

    raise utils.InfrastructureException("Could not find remote origin URL "
                                        "in git output:\n%s" % output)


def checkout_code(zoomdb, opts):
    """
    Checkout code from opts["SRC_URL"] into opts["CO_DIR"].
    """
    dest_dir = opts["CO_DIR"]
    source_code_url = opts["SRC_URL"]
    repo_type = opts.get("SRC_REPO_TYPE", "git")

    vcs_handler = vcs_handlers.get_handler(repo_type)
    vcs_handler.checkout_latest_matching_version(source_code_url, dest_dir,
                                                 zoomdb.log)
