"""

 Deploy task

  - Given a bundle id, app id, as well as db info.
  - Pull bundle from s3, extract
  - Create app user if not exist
  - Chown bundle
  - Launch wsgi server, listen on a socket.
  - Update app server locations (host, socket) in nr database.

"""
