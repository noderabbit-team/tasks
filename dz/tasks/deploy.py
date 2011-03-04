"""
Frontend for deployment-related celery tasks.
"""

import datetime

from celery.task import task
from dz.tasklib import deploy
from dz.tasks.decorators import task_inject_zoomdb


@task(name="deploy_to_appserver",
      queue="__QUEUE_MUST_BE_SPECIFIED_DYNAMICALLY__")
def deploy_to_appserver(app_id, bundle_name, appserver_name, dbinfo):
    return deploy.deploy_app_bundle(app_id, bundle_name, appserver_name,
                                    dbinfo)


@task(name="managepy_command",
      queue="__QUEUE_MUST_BE_SPECIFIED_DYNAMICALLY__")
def managepy_command(app_id, bundle_name, command, nonzero_exit_ok=False):
    return deploy.managepy_command(app_id, bundle_name, command,
                                   nonzero_exit_ok)


@task_inject_zoomdb(name="undeploy", queue="build")
def undeploy(job_id, zoomdb, job_params):
    """
    Take down any running instances of the application. Bundles will remain
    in bundle storage, but are uninstalled from appservers.
    Databases and DB users are not affected.

    :param: job_params["app_id"]: sys id of app to undeploy
    :param: job_params["bundle_names"]: names of bundles to undeploy. If not
              provided, all bundles that are part of the given app are
              undeployed.
    """
    app_id = job_params["app_id"]
    bundle_ids = job_params["bundle_ids"]
    use_subtasks = job_params.get("use_subtasks", True)

    return deploy.undeploy(zoomdb, app_id, bundle_ids,
                           use_subtasks=use_subtasks)


@task(name="undeploy_from_appserver",
      queue="__QUEUE_MUST_BE_SPECIFIED_DYNAMICALLY__")
def undeploy_from_appserver(zoomdb, app_id, bundle_id,
                            appserver_instance_id, appserver_port):
    return deploy.undeploy_from_appserver(zoomdb, app_id, bundle_id,
                                          appserver_instance_id,
                                          appserver_port)
