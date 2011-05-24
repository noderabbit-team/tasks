"""
Frontend for deployment-related celery tasks.
"""

from celery.task import task
from dz.tasklib import deploy
from dz.tasks.decorators import task_inject_zoomdb


@task(name="deploy_to_appserver",
      queue="__QUEUE_MUST_BE_SPECIFIED_DYNAMICALLY__")
def deploy_to_appserver(app_id, bundle_name, appserver_name, dbinfo,
                        num_workers=1):
    return deploy.deploy_app_bundle(app_id, bundle_name, appserver_name,
                                    dbinfo, num_workers=num_workers)


@task(name="managepy_command",
      queue="__QUEUE_MUST_BE_SPECIFIED_DYNAMICALLY__")
def managepy_command(app_id, bundle_name, command,
                     nonzero_exit_ok=False,
                     return_exit_code=False):
    return deploy.managepy_command(app_id, bundle_name, command,
                                   nonzero_exit_ok, return_exit_code)


@task(name="managepy_shell",
      queue="__QUEUE_MUST_BE_SPECIFIED_DYNAMICALLY__")
def managepy_shell(app_id, bundle_name, some_python_code):
    return deploy.managepy_shell(app_id, bundle_name, some_python_code)


@task_inject_zoomdb(name="user_manage_py_command", queue="appserver")
def user_manage_py_command(job_id, zoomdb, job_params):
    app_id = job_params["app_id"]
    deployment_id = job_params["deployment_id"]

    # parameter must be split into a list to ensure the parts inside
    # are passed as separate args to the thisbundle.py script -- if
    # passed as a string, this would run under a shell and be insecure!
    parameters = job_params["parameter"].split()

    worker = zoomdb.get_project_worker_by_id(deployment_id)
    bundle = zoomdb.get_bundle(worker.bundle_id)

    step_label = "Running 'manage.py %s' on worker %s" % (
        " ".join(parameters),
        worker.server_instance_id)

    async_result = managepy_command.apply_async(
        args=[app_id,
              bundle.bundle_name,
              parameters],
        kwargs=dict(nonzero_exit_ok=True,
                    return_exit_code=True),
        queue="appserver:" + worker.server_instance_id)

    zoomdb.log(step_label,
               zoomdb.LOG_STEP_BEGIN)

    exit_code, cmd_output = async_result.wait()
    zoomdb.log("Command output:\n" + cmd_output)

    if exit_code != 0:
        zoomdb.log("Warning: the command returned a non-zero exit code, "
                   "indicating a possible error in executing your management "
                   "command. The return value was %d." % exit_code,
                   log_type=zoomdb.LOG_WARN)

    zoomdb.log(step_label,
               zoomdb.LOG_STEP_END)


@task_inject_zoomdb(name="user_manage_py_shell", queue="appserver")
def user_manage_py_shell(job_id, zoomdb, job_params):
    app_id = job_params["app_id"]
    deployment_id = job_params["deployment_id"]
    some_python_code = job_params["parameter"]

    worker = zoomdb.get_project_worker_by_id(deployment_id)
    bundle = zoomdb.get_bundle(worker.bundle_id)

    step_label = "Running code under 'manage.py shell' on worker %s" % (
        worker.server_instance_id)

    async_result = managepy_shell.apply_async(
        args=[app_id,
              bundle.bundle_name,
              some_python_code],
        queue="appserver:" + worker.server_instance_id)

    zoomdb.log(step_label,
               zoomdb.LOG_STEP_BEGIN)

    cmd_output = async_result.wait()
    zoomdb.log("Command output:\n" + cmd_output)

    zoomdb.log(step_label,
               zoomdb.LOG_STEP_END)


@task_inject_zoomdb(name="undeploy", queue="build")
def undeploy(job_id, zoomdb, job_params):
    """
    Take down any running instances of the application. Bundles will remain
    in bundle storage, but are uninstalled from appservers.
    Databases and DB users are not affected.

    :param: job_params["app_id"]: sys id of app to undeploy
    :param: job_params["bundle_names"]: names of bundles to undeploy. If not
              provided, all bundles that are part of the given app are
              undeployed.
    """
    app_id = job_params["app_id"]
    bundle_ids = job_params["bundle_ids"]
    use_subtasks = job_params.get("use_subtasks", True)

    return deploy.undeploy(zoomdb, app_id, bundle_ids,
                           use_subtasks=use_subtasks)


@task_inject_zoomdb(name="undeploy_from_appserver",
                   queue="__QUEUE_MUST_BE_SPECIFIED_DYNAMICALLY__")
def undeploy_from_appserver(job_id, zoomdb, app_id, bundle_id,
                            appserver_instance_id, appserver_port,
                            zero_undeploys_ok=False,
                            ):
    return deploy.undeploy_from_appserver(zoomdb, app_id, bundle_id,
                                          appserver_instance_id,
                                          appserver_port,
                                          zero_undeploys_ok=zero_undeploys_ok,
                                          )
