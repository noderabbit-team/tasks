import os

"""
ZeroMQ socket over which the nodemaster on this node will take control
messages.
"""
CONTROL_SOCKET_FILE = '/tmp/nodemaster-control.ipc'
CONTROL_ADDR = 'ipc://' + CONTROL_SOCKET_FILE

# Worker address format, using bundle name and worker id as ordered params
WORKER_ADDR_FORMAT = 'ipc:///tmp/worker-%s-%s.ipc'

HERE = os.path.abspath(os.path.dirname(__file__))
WORKER_EXE = os.path.join(HERE, "bundleworker.py")
