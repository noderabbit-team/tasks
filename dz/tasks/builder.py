"""

Builds out app server bundle

 - configures app server settings
 - uploads zipped bundle to s3.

"""

from celery.task import task
from dz.tasklib import bundle, db
from dz.tasklib.db import ZoomDatabase

import time


@task(name="check_repo", queue="build", serializer="json")
def check_repo(job_id):
    """
    Checkout an app and inspect settings for use by the database.
    """
    session = check_repo.backend.ResultSession()
    zoom_db = db.ZoomDatabase(session.bind, job_id)

    zoom_db.log("Hello, check_repo world!")


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
