"""
 Deploy task

  - Given a bundle id, app id, as well as db info.
  - Pull bundle from s3, extract
  - Create app user if not exist
  - Chown bundle
  - Launch wsgi server, listen on a socket.
  - Update app server locations (host, socket) in nr database.

"""
import datetime
import os
#import pwd
import shutil
import socket

from dz.tasklib import (bundle_storage,
                        bundle_storage_local,
                        bundle,
                        taskconfig,
                        utils,
                        userenv)


def _write_deployment_config(outfilename, bundle_name, dbinfo, num_workers=1):
    utils.render_tpl_to_file(
        'deploy/thisbundle.py.tmpl',
        outfilename,
        bundle_name=bundle_name,
        dbinfo=dbinfo,
        num_workers=num_workers)
    os.chmod(outfilename, 0700)


def deploy_app_bundle(app_id, bundle_name, appserver_name, dbinfo,
                      bundle_storage_engine=None,
                      num_workers=1):

    bundle_storage_engine = bundle.get_bundle_storage_engine(
        bundle_storage_engine)

    my_hostname = utils.node_meta("name")
    my_instance_id = utils.node_meta("instance_id")

    if appserver_name not in (my_hostname, my_instance_id, "localhost"):
        raise utils.InfrastructureException(
            "Incorrect appserver received deploy_app_bundle task; " +
            "I am %s but the deploy is requesting %s." % (my_hostname,
                                                          appserver_name))

    install_app_bundle(app_id, bundle_name, appserver_name, dbinfo,
                       bundle_storage_engine=bundle_storage_engine,
                       num_workers=num_workers)

    # result is a (instance_id, node_name, host_ip, port_to_use)
    return start_serving_bundle(app_id, bundle_name)


def install_app_bundle(app_id, bundle_name, appserver_name, dbinfo,
                       bundle_storage_engine=bundle_storage,
                       static_only=False, num_workers=1,
                       remove_other_bundles=False):
    app_dir, bundle_dir = utils.app_and_bundle_dirs(app_id, bundle_name)

    if not os.path.exists(bundle_dir):
        utils.get_and_extract_bundle(bundle_name, app_dir,
                                     bundle_storage_engine)

    if remove_other_bundles:
        for fname in os.listdir(app_dir):
            if (fname.startswith("bundle_")
                and os.path.isdir(fname)
                and fname != bundle_name):
                shutil.rmtree(fname)

    if not static_only:
        utils.chown_to_me(bundle_dir)
        _write_deployment_config(os.path.join(bundle_dir, "thisbundle.py"),
                                 bundle_name, dbinfo, num_workers=num_workers)
        utils.local_privileged(["project_chown", app_id, bundle_dir])
        # bundle_owner_name = pwd.getpwuid(os.stat(bundle_dir).st_uid).pw_name
        # if bundle_owner_name != app_id:
        #     utils.local_privileged(["project_chown", app_id, bundle_dir])


def install_app_bundle_static(app_id, bundle_name,
                              bundle_storage_engine=bundle_storage,
                              remove_other_bundles=False):
    return install_app_bundle(app_id, bundle_name,
                              None, None,
                              bundle_storage_engine,
                              static_only=True,
                              remove_other_bundles=remove_other_bundles)


def managepy_command(app_id, bundle_name, command, nonzero_exit_ok=False,
                     return_exit_code=False):
    app_dir, bundle_dir = utils.app_and_bundle_dirs(app_id, bundle_name)

    if not os.path.isdir(bundle_dir):
        raise utils.InfrastructureException(
            "This server doesn't seem to have the requested app bundle " +
            "currently deployed: app=%s, bundle=%s." % (app_id, bundle_name))

    procargs = [os.path.join(bundle_dir, "thisbundle.py")]
    if isinstance(command, list):
        procargs += command
    else:
        procargs.append(command)

    ue = userenv.UserEnv(app_id)
    stdout, stderr, proc = ue.subproc(procargs, nonzero_exit_ok=True)
    ue.destroy()

    result = stdout + "\n" + stderr

    if proc.returncode != 0 and not(nonzero_exit_ok):
        raise RuntimeError(
            ("Nonzero return code %d from manage.py %s:\n" % (proc.returncode,
                                                              command)) +
            result)

    if return_exit_code:
        return proc.returncode, result
    else:
        return result


def managepy_shell(app_id, bundle_name, some_python_code):
    app_dir, bundle_dir = utils.app_and_bundle_dirs(app_id, bundle_name)

    if not os.path.isdir(bundle_dir):
        raise utils.InfrastructureException(
            "This server doesn't seem to have the requested app bundle " +
            "currently deployed: app=%s, bundle=%s." % (app_id, bundle_name))

    procargs = [os.path.join(bundle_dir, "thisbundle.py"),
                "shell", "--plain"]

    ue = userenv.UserEnv(app_id)
    stdout, stderr, proc = ue.subproc(procargs,
                                      stdin_string=some_python_code)

    result = stdout
    if stderr:
        result += "\n" + stderr

    if proc.returncode != 0:
        raise RuntimeError(
            (("Nonzero return code %d from manage.py shell script:"
              "\n%s\n\nOutput of script was:\n") % (
                    proc.returncode,
                    some_python_code)) +
            result)

    return result


def is_port_open(port):
    """Test whether the given port is open for listening."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", port))
    except socket.error, e:
        print e
        return False
    else:
        return True


def _kick_supervisor():
    """
    Have supervisor re-read its config files and start any services
    that aren't started yet.
    """
    utils.local('echo -e "reread\nupdate" | sudo /usr/bin/supervisorctl')


def get_active_bundles():
    if not os.path.isdir(taskconfig.SUPERVISOR_APP_CONF_DIR):
        return

    for filename in os.listdir(taskconfig.SUPERVISOR_APP_CONF_DIR):
        if ".port." in filename and filename.endswith(".conf"):
            app_and_bundle_name, bundle_port = \
                filename[:-len(".conf")].rsplit(".port.", 1)
            try:
                bundle_port = int(bundle_port)
            except ValueError:
                continue

            app_id, bundle_name = app_and_bundle_name.split(".", 1)

            yield dict(app_id=app_id,
                       bundle_name=bundle_name,
                       port=bundle_port,
                       filename=filename)


def _get_a_free_port():
    """Select a port for serving a new bundle."""
    max_used_port = taskconfig.APP_SERVICE_START_PORT

    for active_bundle in get_active_bundles():
        if active_bundle["port"] > max_used_port:
            max_used_port = active_bundle["port"]

    port_to_use = max_used_port + 1

    while not(is_port_open(port_to_use)):
        port_to_use += 1
        if port_to_use > taskconfig.APP_SERVICE_MAX_PORT:
            raise utils.InfrastructureException("This appserver has run out " +
                                                "of TCP ports to listen on.")
    return port_to_use


def start_serving_bundle(app_id, bundle_name):
    """
    Serve the given bundle under supervisor, and return the appserver info
    for where the service is running.

    If you are running locally as dev, you need to make sure the user
    running Celery has permissions to write to the /etc/supervisor/conf.d dir.

    $ sudo chgrp nateaune /etc/supervisor/conf.d/
    $ sudo chmod g+w /etc/supervisor/conf.d/

    :returns: (instance_id, node_name, host_ip, host_port)
    """

    # check that this bundle isn't already being served here - otherwise
    # supervisor will silently ignore the redundant config files!
    for bun in get_active_bundles():
        if bun["app_id"] == app_id and bun["bundle_name"] == bundle_name:
            raise utils.InfrastructureException((
                    "Redundant bundle service request: server %s (hostname=%s)"
                    " is already serving app_id %s, bundle_name %s.") % (
                    utils.node_meta("name"),
                    socket.gethostname(),
                    app_id,
                    bundle_name))

    port_to_use = _get_a_free_port()

    config_filename = os.path.join(taskconfig.SUPERVISOR_APP_CONF_DIR,
                                   "%s.%s.port.%d.conf" % (app_id,
                                                           bundle_name,
                                                           port_to_use))

    app_dir, bundle_dir = utils.app_and_bundle_dirs(app_id, bundle_name)

    utils.render_tpl_to_file(
        'deploy/supervisor_entry.conf',
        config_filename,
        run_in_userenv=os.path.join(taskconfig.PRIVILEGED_PROGRAMS_PATH,
                                    "run_in_userenv"),
        custdir=taskconfig.NR_CUSTOMER_DIR,
        bundle_name=bundle_name,
        bundle_runner=os.path.join(bundle_dir, "thisbundle.py"),
        bundle_dir=bundle_dir,
        app_user=app_id,
        port=port_to_use)

    _kick_supervisor()

    instance_id = utils.node_meta("instance_id")
    node_name = utils.node_meta("name")
    host_ip = utils.get_internal_ip()

    return (instance_id, node_name, host_ip, port_to_use)


def stop_serving_bundle(app_id, bundle_name):
    """
    Remove the supervisor entry for this bundle, and ask supervisor to
    terminate the supervised worker process.

    :returns: the number of bundles that were stopped.
    """
    num_stopped = 0

    for bundle in get_active_bundles():
        if bundle["app_id"] == app_id and bundle["bundle_name"] == bundle_name:
            config_filename = os.path.join(taskconfig.SUPERVISOR_APP_CONF_DIR,
                                           bundle["filename"])
            print "Removing supervisor conf file: %s" % config_filename
            os.remove(config_filename)
            num_stopped += 1

    _kick_supervisor()

    return num_stopped


def undeploy(zoomdb, app_id, bundle_ids=None, use_subtasks=True,
             also_update_proxies=True, dep_ids=None,
             zero_undeploys_ok=False,
             zoombuild_cfg_content=None,
             log_step_events=True):
    """Given an app_id and list of bundle names, undeploy those bundles.

    :param bundle_ids: Database IDs of bundles to undeploy. If None, all
      bundles for this app will be undeployed.
    :param dep_ids: AppServerDeployment IDs to undeploy. This may be optionally
      specified instead of specifying bundle_ids.
    :param also_update_proxies: Update proxy configuration to point at
      remaining deployments. Requires the zoombuild_cfg_content parameter
      as well.
    :param zoombuild_cfg_content: Content of zoombuild.cfg, used only if
      also_update_proxies is true.
    """

    if also_update_proxies and (bundle_ids or dep_ids):
        assert zoombuild_cfg_content, ("tasklib.deploy.undeploy requires "
                                       "zoombuild_cfg_content parameter if "
                                       "also_update_proxies is true and "
                                       "any instances will remain up.")

    step_title = "Deactivating instances"
    if log_step_events:
        zoomdb.log(step_title, zoomdb.LOG_STEP_BEGIN)

    if not dep_ids:
        matching_deployments = zoomdb.search_workers(bundle_ids, active=True)
    else:
        all_workers = zoomdb.get_project_workers()
        matching_deployments = [w for w in all_workers if w.id in dep_ids]

    if len(matching_deployments) == 0:
        if not zero_undeploys_ok:
            raise utils.InfrastructureException(
                "No active deployments found for app_id=%s, bundle_ids=%r." %
                (app_id, bundle_ids))

    for dep in matching_deployments:
        if dep.deactivation_date:
            zoomdb.log("Deployment %s appears to be already deactivated."
                       % dep, zoomdb.LOG_WARN)

    droptasks = []

    import dz.tasks.deploy  # do this non-globally due to dependencies

    def save_undeployment(dep):
        dep.deactivation_date = datetime.datetime.utcnow()
        zoomdb.flush()
        zoomdb.log(("Dropped bundle #%d from server %s (%s:%d). "
                    "Deactivated: %s.") % (
                       dep.bundle_id, dep.server_instance_id,
                       dep.server_ip, dep.server_port,
                       dep.deactivation_date,
                       ))

    for dep in matching_deployments:
        args = [app_id,
                dep.bundle_id,
                dep.server_instance_id,
                dep.server_port]
        kwargs = {"zero_undeploys_ok": zero_undeploys_ok}

        zoomdb.log("Dropping bundle #%d from server %s (%s:%d)..." % (
            dep.bundle_id, dep.server_instance_id,
            dep.server_ip, dep.server_port))
        if use_subtasks:
            droptasks.append(
                dz.tasks.deploy.undeploy_from_appserver.apply_async(
                    args=[zoomdb.get_job_id()] + args,
                    kwargs=kwargs,
                    queue="appserver:" + dep.server_instance_id))

        else:
            result = undeploy_from_appserver(zoomdb, *args, **kwargs)
            save_undeployment(dep)

    # if using subtasks, wait for the async tasks to finish
    if use_subtasks:
        for dep, dt in zip(matching_deployments, droptasks):
            result = dt.wait()
            save_undeployment(dep)

    # now update frontend proxies
    if also_update_proxies:
        active_workers = [w for w in zoomdb.get_project_workers()
                          if not(w.deactivation_date)]
        remaining_appservers = [(w.server_instance_id,
                                 w.server_instance_id, # should be node name
                                 w.server_ip,
                                 w.server_port)
                                for w in active_workers]
        if len(remaining_appservers):
            newest_worker = max(active_workers, key=lambda x: x.creation_date)
            newest_bundle = zoomdb.get_bundle(newest_worker.bundle_id)

            zoomdb.log("Updating front-end proxy to use remaining appservers "
                       "(%r)" % (remaining_appservers,))
            if use_subtasks:
                zcfg = utils.parse_zoombuild_string(zoombuild_cfg_content)
                site_media_map = utils.parse_site_media_map(
                    zcfg.get("site_media_map", ""))

                import dz.tasks.nginx
                proxy_task = dz.tasks.nginx.update_proxy_conf.apply_async(args=[
                    zoomdb.get_job_id(),
                    app_id,
                    newest_bundle.bundle_name,  # to serve static assets
                    remaining_appservers,
                    zoomdb.get_project_virtual_hosts(),
                    site_media_map])
                proxy_task.wait()
            else:
                import dz.tasklib.nginx
                dz.tasklib.nginx.update_local_proxy_config(
                    app_id,
                    remaining_appservers,
                    zoomdb.get_project_virtual_hosts())
        else:
            # there are no more appservers; remove from proxy
            zoomdb.log(("This undeployment removes the last active appservers "
                        "for %r; stopping front-end proxy service for "
                        "associated virtual hostnames too.") % app_id)

            if use_subtasks:
                import dz.tasks.nginx
                subtask = dz.tasks.nginx.remove_proxy_conf.apply_async(
                    args=[zoomdb.get_job_id(), app_id])
                subtask.wait()
            else:
                import dz.tasklib.nginx
                dz.tasklib.nginx.remove_local_proxy_config(app_id)

    if log_step_events:
        zoomdb.log(step_title, zoomdb.LOG_STEP_END)


def undeploy_from_appserver(zoomdb, app_id, bundle_id,
                            appserver_instance_id, appserver_port,
                            zero_undeploys_ok=False):

    my_hostname = utils.node_meta("name")
    my_instance_id = utils.node_meta("instance_id")

    if appserver_instance_id not in (my_hostname, my_instance_id, "localhost"):
        raise utils.InfrastructureException(
            "Incorrect appserver received undeploy_from_appserver task; " +
            "I am %s but the undeploy is for %s." % (my_hostname,
                                                     appserver_instance_id))

    bundle = zoomdb.get_bundle(bundle_id)

    num_stopped = stop_serving_bundle(app_id, bundle.bundle_name)

    if num_stopped == 0 and zero_undeploys_ok:
        zoomdb.log("Note: no matching bundles were running on %s." %
                   my_hostname)

    elif num_stopped != 1:
        raise utils.InfrastructureException(
            ("Attempting to undeploy one bundle (app_id %s, bundle_id %s, "
             "bundle_name %s) from appserver %s:%d, but %d bundles were "
             "stopped.")
            % (app_id, bundle_id, bundle.bundle_name,
               appserver_instance_id, appserver_port, num_stopped))

    app_dir, bundle_dir = utils.app_and_bundle_dirs(app_id,
                                                    bundle.bundle_name)
    if os.path.isdir(bundle_dir):
        zoomdb.log("Removing old bundle from %s." % bundle_dir)
        utils.chown_to_me(bundle_dir)
        shutil.rmtree(bundle_dir)
