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
from dz.tasks.decorators import task_inject_zoomdb


@task(name="setup_database_for_app", queue="database")
def setup_database_for_app(app_id):
    return database.get_or_create_database(app_id)


@task_inject_zoomdb(name="enable_postgis", queue="database")
def enable_postgis(job_id, zoomdb, job_params, log_step_events=True):
    step_label = "Enabling PostGIS Extensions on Database"
    if log_step_events:
        zoomdb.log(step_label, zoomdb.LOG_STEP_BEGIN)
    zoomdb.log("Installing PostGIS into database...")
    sql_output = database.enable_postgis(job_params["app_id"])
    zoomdb.mark_postgis_enabled()
    zoomdb.log("Command output:\n" + sql_output)
    if log_step_events:
        zoomdb.log(step_label, zoomdb.LOG_STEP_END)
