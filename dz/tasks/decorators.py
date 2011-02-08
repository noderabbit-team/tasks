"""
Decorators to make task creation easier.
"""

from celery.task import task
from dz.tasklib.db import ZoomDatabase


def task_inject_zoomdb(**celery_kwargs):
    """
    Decorator that takes the same parameters as celery.task.task, but:
    1. it's assumed that this function will be called using one parameter,
       a job_id
    2. this decorator will apply the celery decorator and also insert
       a zoomdb argument holding a DB wrapper object.

    This is a convenience to avoid the need to repeat DB lookup code in each
    task function.
    """

    assert "name" in celery_kwargs, ("You must specify a task name if " +
                                     "using the task_with_job_id decorator," +
                                     " or else celery will get confused.")

    def decorator(taskfunc):
        def db_constructor(job_id):
            session = db_constructor.backend.ResultSession()
            zoomdb = ZoomDatabase(session.bind, job_id)
            return taskfunc(job_id, zoomdb)

        db_constructor = task(**celery_kwargs)(db_constructor)

        return db_constructor

    return decorator
