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


def _write_deployment_config(outfilename,
                             db_host, db_name, db_username, db_password):
    utils.render_tpl_to_file(
        'deploy/deployment_config.py.tmpl',
        outfilename,
        db_host=db_host,
        db_name=db_name,
        db_username=db_username,
        db_password=db_password)
    os.chmod(outfilename, 0500)


def deploy_app_bundle(app_id, bundle_name, appserver_name,
                      db_host, db_name, db_username, db_password,
                      bundle_storage_engine=bundle_storage):

    my_hostname = socket.gethostname()

    print "dz.tasklib.deploy_to_appserver"

    if appserver_name not in (my_hostname, "localhost"):
        raise utils.InfrastructureException(
            "Incorrect appserver received deploy_app_bundle task; " +
            "I am %s but the deploy is requesting %s." % (my_hostname,
                                                          appserver_name))
    app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR,
                           app_id)
    bundle_dir = os.path.join(app_dir, bundle_name)

    if not os.path.exists(bundle_dir):
        _get_and_extract_bundle(bundle_name, app_dir,
                                bundle_storage_engine)

    _write_deployment_config(os.path.join(bundle_dir,
                                          "deployment_%s.py" % appserver_name),
                             db_host, db_name, db_username, db_password)

    return "[%s] Deployed app %s, bundle %s. [NOT YET IMPLEMENTED]" % (
        my_hostname, app_id, bundle_name)
