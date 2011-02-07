from celery.task import task
from time import sleep


@task(name="task_a")
def task_a():
    sleep(1)
    return "a"


@task(name="task_b")
def task_b():
    sleep(1)
    return "b"
