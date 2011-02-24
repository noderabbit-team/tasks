"""
Tasks
-----

Create database for project
===========================

 - project id
 - owner name + project name, in short form.

 - should push database name and server, username, password (salted?)
   back to project model.
"""

from celery.task import task
from dz.tasklib import database


@task(name="setup_database_for_app", queue="database")
def setup_database_for_app(app_id):
    (created, db_host, db_name, db_username, db_password) = \
        database.get_or_create_database(app_id)

    return (created, db_host, db_name, db_username, db_password)
