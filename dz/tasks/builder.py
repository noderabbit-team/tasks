"""
Overarching user-visible tasks relating to building and deploying projects.
"""

from dz.tasks.decorators import task_inject_zoomdb
import dz.tasklib.check_repo
import dz.tasklib.bundle
import dz.tasklib.build_and_deploy
import dz.tasklib.deploy


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
        job_params["zoombuild_cfg_content"],
        num_workers=job_params["num_workers"],
        requires_postgis=job_params["requires_postgis"])


@task_inject_zoomdb(name="deactivate_instances", queue="build")
def deactivate_instances(job_id, zoomdb, job_params):
    """
    Deactivate a set of instances for the project, based on ID.
    """
    dz.tasklib.deploy.undeploy(
        zoomdb,
        job_params["app_id"],
        dep_ids=job_params["dep_ids"],
        also_update_proxies=True,
        zoombuild_cfg_content=job_params["zoombuild_cfg_content"],
        zero_undeploys_ok=True)

@task_inject_zoomdb(name="delete_versions", queue="build")
def delete_versions(job_id, zoomdb, job_params):
    """
    Delete a set of versions (bundles) in the project, based on ID.
    The versions are assumed to be inactive (i.e. not currently deployed).
    """
    dz.tasklib.bundle.delete_bundles(zoomdb,
                                     job_params["app_id"],
                                     job_params["bundle_ids"])
