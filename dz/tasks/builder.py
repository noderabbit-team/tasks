"""

Builds out app server bundle

 - configures app server settings
 - uploads zipped bundle to s3.

"""

from celery.task import task
from tasklib import bundle, db

@task(queue="build", serializer="json")
def check_repo():
    """
    Checkout an app and inspect settings for use by the database.
    """


@task(queue="build", serializer="json")
def build_app():
    """
    Checkout an app, and then generates a zoombuild info config file.
    """


@task(queue="build", serializer="json")
def build_bundle(app_id):
    """
    Build bundle, and upload to s3.
    """
    session = build_bundle.backend.ResultSession()
    zoom_db = db.ZoomDatabase(session, build_bundle.request.id)
    bundle_name = bundle.bundle_app(zoom_db, app_id)
    bundle.zip_and_upload_bundle(zoom_db, app_id, bundle_name)
