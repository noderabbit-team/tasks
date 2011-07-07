#!/usr/bin/env python
"""
Command-line tool to control nodemaster.
"""
import sys
from eventlet.green import zmq

import mafconfig


class NodeMasterControlClient(object):
    def __init__(self):
        self.ctx = zmq.Context()
        self.control_socket = self.ctx.socket(zmq.REQ)
        self.control_socket.connect(mafconfig.CONTROL_ADDR)

    def send_command(self, cmd, *args):
        self.control_socket.send_pyobj([cmd] + list(args))
        return self.control_socket.recv_pyobj()


if __name__ == "__main__":
    nmc = NodeMasterControlClient()
    cmd = sys.argv[1:]
    if not len(cmd):
        print "Please pass a command."
        sys.exit(1)
    print "Sending command %r..." % cmd
    resp = nmc.send_command(*cmd)
    print "Got response: %r" % resp
