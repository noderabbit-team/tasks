import sys

from dz.tasks.decorators import task_inject_zoomdb
from dz.tasklib import recovery as recovery_lib


@task_inject_zoomdb(name="recover_appserver", queue="build")
def recover_appserver(job_id, zoomdb, appserver_ip, project_id=None):
    return recovery_lib.recover_appserver(zoomdb, appserver_ip,
                                          project_id=project_id)
