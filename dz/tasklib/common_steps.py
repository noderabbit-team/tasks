"""
This module contains common steps that may appear in multiple different
tasks.
"""

from dz.tasklib import (taskconfig,
                        utils)
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
    d = opts["CO_DIR"]
    source_code_url = opts["SRC_URL"]

    if not os.path.exists(d):
        os.makedirs(d)

    if source_code_url.startswith(taskconfig.TEST_REPO_URL_PREFIX):
        suffix = source_code_url[len(taskconfig.TEST_REPO_URL_PREFIX):]
        suffix = suffix.lstrip("/")
        assert "/" not in suffix, "Bad test repo path."
        assert ".." not in suffix, "Bad test repo path."
        repourl = os.path.join(taskconfig.TEST_REPO_DIR, suffix)
    else:
        repourl = source_code_url

    cur_dir = os.getcwd()
    try:
        os.chdir(d)

        if os.path.exists(".git") and \
               _get_remote_origin_url(d) == source_code_url:
            zoomdb.log("Updating code from repository.")
            cmd = ["git", "pull"]
        else:
            if os.path.exists(".git"):
                zoomdb.log("Repository URL has changed, making a fresh clone.")
                os.chdir(cur_dir)
                shutil.rmtree(d)
                os.makedirs(d)
                os.chdir(d)

            zoomdb.log("Cloning your repository.")
            cmd = ["git", "clone", repourl, "."]

        zoomdb.log("Running %s..." % " ".join(cmd))
        output, stderr, p = utils.subproc(cmd)
        if p.returncode != 0:
            raise utils.ProjectConfigurationException(
                "Error updating code from repository %s:\n%s\n%s" % (
                    repourl, output, stderr))
        else:
            zoomdb.log("Command output:\n%s\n%s" % (output, stderr))

    finally:
        os.chdir(cur_dir)
