"""

 Deploy task

  - Given a bundle id, app id, as well as db info.
  - Pull bundle from s3, extract
  - Create app user if not exist
  - Chown bundle
  - Launch wsgi server, listen on a socket.
  - Update app server locations (host, socket) in nr database.

"""

import socket


def deploy_app_bundle(app_id, bundle_name,
                      db_host, db_name, db_username, db_password):
    my_hostname = socket.gethostname()
    print "dz.tasklib.deploy_to_appserver"

    return "[%s] Deployed app %s, bundle %s. [NOT YET IMPLEMENTED]" % (
        my_hostname, app_id, bundle_name)
