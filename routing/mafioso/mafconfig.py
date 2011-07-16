from dz.tasklib import taskconfig
import os

"""
ZeroMQ socket over which the nodemaster on this node will take control
messages.
"""
CONTROL_SOCKET_FILE = '/tmp/nodemaster-control.ipc'
CONTROL_ADDR = 'ipc://' + CONTROL_SOCKET_FILE

# Worker address format, using bundle name and worker id as ordered params
#WORKER_ADDR_FORMAT = 'ipc:///tmp/worker-%s-%s.ipc'

# Worker ZMQ address format, with a dict containing keys:
# app_id, bundle_name, worker_id
#
# First, a directory to contain files specific to this worker.
# This should be created, owned by the app_id user, mode 0755
WORKER_DIR_FORMAT = (taskconfig.NR_CUSTOMER_DIR + '/%(app_id)s/' +
                     'worker-%(bundle_name)s-%(worker_id)s')
# Now the path to the IPC transport, in the above dir.
WORKER_ADDR_FORMAT = 'ipc://%(worker_dir)s/worker.ipc'
# And the worker script
WORKER_USERENV_BUNDLEWORKER_PATH_FORMAT = '%(worker_dir)s/bundleworker.py'

HERE = os.path.abspath(os.path.dirname(__file__))
WORKER_EXE = os.path.join(HERE, "bundleworker.py")
