"""

Builds out app server bundle

 - configures app server settings
 - uploads zipped bundle to s3.

"""

from celery.task import task
from dz.tasks.decorators import task_inject_zoomdb
from dz.tasklib import (bundle,
                        check_repo)


@task_inject_zoomdb(name="check_repo", queue="build", serializer="json")
def check_repo(job_id, zoomdb, job_params):
    """
    Checkout an app and inspect settings for use by the database.
    """
    check_repo.check_repo(zoomdb,
                          job_params["app_id"],
                          job_params["src_url"])

@task(name="build_app", queue="build", serializer="json")
def build_app():
    """
    Checkout an app, and then generates a zoombuild info config file.
    """


@task(name="build_bundle", queue="build", serializer="json")
def build_bundle(app_id):
    """
    Build bundle, and upload to s3.
    """
    session = build_bundle.backend.ResultSession()
    zoom_db = db.ZoomDatabase(session.bind, build_bundle.request.id)
    #bundle_name = bundle.bundle_app(zoom_db, app_id)
    #bundle.zip_and_upload_bundle(zoom_db, app_id, bundle_name)
