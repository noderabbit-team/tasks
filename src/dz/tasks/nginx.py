"""

Needs to know.
 - vhost name of the project
 - project app server locations
 - static media locations (aka site media)

"""
from celery import task


@task
def nginx(message):
    pass
