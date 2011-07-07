"""
ZeroMQ socket over which the nodemaster on this node will take control
messages.
"""
CONTROL_SOCKET_FILE = '/tmp/nodemaster-control'
CONTROL_ADDR = 'ipc://' + CONTROL_SOCKET_FILE
