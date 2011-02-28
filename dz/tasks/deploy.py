"""
Frontend for deployment-related celery tasks.
"""

from celery.task import task
from dz.tasklib import deploy


@task(name="deploy_to_appserver",
      queue="__QUEUE_MUST_BE_SPECIFIED_DYNAMICALLY__")
def deploy_to_appserver(app_id, bundle_name, appserver_name,
                        db_host, db_name, db_username, db_password):
    return deploy.deploy_app_bundle(app_id, bundle_name, appserver_name,
                                    db_host, db_name, db_username, db_password)


@task(name="managepy_command",
      queue="__QUEUE_MUST_BE_SPECIFIED_DYNAMICALLY__")
def managepy_command(app_id, bundle_name, command):
    return deploy.managepy_command(app_id, bundle_name, command)
