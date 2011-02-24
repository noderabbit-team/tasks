"""
Frontend for deployment-related celery tasks.
"""

from celery.task import task
from dz.tasklib import deploy


@task(name="deploy_to_appserver",
      queue="__QUEUE_MUST_BE_SPECIFIED_DYNAMICALLY__")
def deploy_to_appserver(app_id, bundle_name, appserver_name,
                        db_host, db_name, db_username, db_password):
    print "dz.tasks.deploy_to_appserver"
    return deploy.deploy_app_bundle(app_id, bundle_name, appserver_name,
                                    db_host, db_name, db_username, db_password)
