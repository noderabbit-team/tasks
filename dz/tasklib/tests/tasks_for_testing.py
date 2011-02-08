from celery.task import task
import os
from time import sleep


def _faketask(result):
    sleep(0.5)
    return dict(result=result,
                TEST_CELERYD_NAME=os.environ.get("TEST_CELERYD_NAME"))


@task(name="task_a", queue="build")
def task_a():
    return _faketask("a")


@task(name="task_b", queue="appserver")
def task_b():
    return _faketask("b")
