"""
Overarching user-visible tasks relating to building and deploying projects.
"""

from dz.tasks.decorators import task_inject_zoomdb
import dz.tasklib.check_repo
import dz.tasklib.bundle
import dz.tasklib.build_and_deploy


@task_inject_zoomdb(name="check_repo", queue="build")
def check_repo(job_id, zoomdb, job_params):
    """
    Checkout an app and inspect settings for use by the database.
    """
    dz.tasklib.check_repo.check_repo(zoomdb,
                                     job_params["app_id"],
                                     job_params["src_url"])


@task_inject_zoomdb(name="build_and_deploy", queue="build")
def build_and_deploy(job_id, zoomdb, job_params):
    """
    Checkout an app and inspect settings for use by the database.
    """
    return dz.tasklib.build_and_deploy.build_and_deploy(
        zoomdb,
        job_params["app_id"],
        job_params["src_url"],
        job_params["zoombuild_cfg_content"])
