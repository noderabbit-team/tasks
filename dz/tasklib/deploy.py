"""
 Deploy task

  - Given a bundle id, app id, as well as db info.
  - Pull bundle from s3, extract
  - Create app user if not exist
  - Chown bundle
  - Launch wsgi server, listen on a socket.
  - Update app server locations (host, socket) in nr database.

"""
import os
import socket
import subprocess

from dz.tasklib import (bundle_storage,
                        taskconfig,
                        utils,
                        )


def _get_and_extract_bundle(bundle_name, app_dir, bundle_storage_engine):
    bundletgz = bundle_storage_engine.get(bundle_name + ".tgz")
    if not os.path.isdir(app_dir):
        os.makedirs(app_dir)
    current_dir = os.getcwd()
    os.chdir(app_dir)

    try:
        p = subprocess.Popen(["tar", "xzf", bundletgz], close_fds=True)
        os.waitpid(p.pid, 0)
    finally:
        os.chdir(current_dir)

    os.remove(bundletgz)


def _write_deployment_config(outfilename, bundle_name, dbinfo):
    utils.render_tpl_to_file(
        'deploy/thisbundle.py.tmpl',
        outfilename,
        bundle_name=bundle_name,
        dbinfo=dbinfo)
    os.chmod(outfilename, 0700)


def _app_and_bundle_dirs(app_id, bundle_name):
    app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_id)
    bundle_dir = os.path.join(app_dir, bundle_name)
    return app_dir, bundle_dir


def deploy_app_bundle(app_id, bundle_name, appserver_name, dbinfo,
                      bundle_storage_engine=bundle_storage):

    my_hostname = socket.gethostname()

    if appserver_name not in (my_hostname, "localhost"):
        raise utils.InfrastructureException(
            "Incorrect appserver received deploy_app_bundle task; " +
            "I am %s but the deploy is requesting %s." % (my_hostname,
                                                          appserver_name))

    install_app_bundle(app_id, bundle_name, appserver_name, dbinfo,
                       bundle_storage_engine=bundle_storage)

    port = start_serving_bundle(app_id, bundle_name)
    return port


def install_app_bundle(app_id, bundle_name, appserver_name, dbinfo,
                       bundle_storage_engine=bundle_storage):
    app_dir, bundle_dir = _app_and_bundle_dirs(app_id, bundle_name)

    if not os.path.exists(bundle_dir):
        _get_and_extract_bundle(bundle_name, app_dir,
                                bundle_storage_engine)

    _write_deployment_config(os.path.join(bundle_dir, "thisbundle.py"),
                             bundle_name, dbinfo)


def managepy_command(app_id, bundle_name, command, nonzero_exit_ok=False):
    app_dir, bundle_dir = _app_and_bundle_dirs(app_id, bundle_name)

    if not os.path.isdir(bundle_dir):
        raise utils.InfrastructureException(
            "This server doesn't seem to have the requested app bundle " +
            "currently deployed: app=%s, bundle=%s." % (app_id, bundle_name))

    procargs = [os.path.join(bundle_dir, "thisbundle.py")]
    if isinstance(command, list):
        procargs += command
    else:
        procargs.append(command)
    stdout, stderr, proc = utils.subproc(procargs)

    result = stdout + "\n" + stderr

    if proc.returncode != 0 and not(nonzero_exit_ok):
        raise RuntimeError(
            ("Nonzero return code %d from manage.py %s:\n" % (proc.returncode,
                                                              command)) +
            result)

    return result


def _is_port_open(port):
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


def _get_active_bundles():
    for filename in  os.listdir(taskconfig.SUPERVISOR_APP_CONF_DIR):
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

    for active_bundle in _get_active_bundles():
        if active_bundle["port"] > max_used_port:
            max_used_port = active_bundle["port"]

    port_to_use = max_used_port + 1

    while not(_is_port_open(port_to_use)):
        port_to_use += 1
        if port_to_use > taskconfig.APP_SERVICE_MAX_PORT:
            raise utils.InfrastructureException("This appserver has run out " +
                                                "of TCP ports to listen on.")
    return port_to_use


def start_serving_bundle(app_id, bundle_name):
    """
    Serve the given bundle under supervisor, and return the port on which
    the service is running.
    """
    port_to_use = _get_a_free_port()

    config_filename = os.path.join(taskconfig.SUPERVISOR_APP_CONF_DIR,
                                   "%s.%s.port.%d.conf" % (app_id,
                                                           bundle_name,
                                                           port_to_use))

    app_dir, bundle_dir = _app_and_bundle_dirs(app_id, bundle_name)
    utils.render_tpl_to_file(
        'deploy/supervisor_entry.conf',
        config_filename,
        bundle_name=bundle_name,
        bundle_runner=os.path.join(bundle_dir, "thisbundle.py"),
        bundle_dir=bundle_dir,
        bundle_user=app_id,
        port=port_to_use)

    _kick_supervisor()

    return port_to_use


def stop_serving_bundle(app_id, bundle_name):
    """
    Remove the supervisor entry for this bundle, and ask supervisor to
    terminate the supervised worker process.

    :returns: the number of bundles that were stopped.
    """
    num_stopped = 0

    for bundle in _get_active_bundles():
        if bundle["app_id"] == app_id and bundle["bundle_name"] == bundle_name:
            config_filename = os.path.join(taskconfig.SUPERVISOR_APP_CONF_DIR,
                                           bundle["filename"])
            print "Removing supervisor conf file: %s" % config_filename
            os.remove(config_filename)
            num_stopped += 1

    _kick_supervisor()

    return num_stopped
