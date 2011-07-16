#!/usr/bin/env python

import os
import sys

import pprint

import zmq


context = zmq.Context()
IPC_FILE_PREFIX = "ipc://"


class WorkerProcess(object):

    def __init__(self):
        self.bind_addr = None

    def get_wsgi_callable(self):
        pass

    def get_wsgi_response(self, env):
        response = (
            ('200 OK', [('Content-Type', 'text/plain')]),
            ["Hello from a worker at %s!\n%s" % (
                self.bind_addr,
                pprint.pformat(env),
                )],
            )
        return response

    def run(self, bind_addr):
        try:
            self.bind_addr = bind_addr
            socket = context.socket(zmq.REP)
            socket.bind(bind_addr)

            if bind_addr.startswith(IPC_FILE_PREFIX):
                # need to chmod this so that the nodemaster can access it
                socket_file = bind_addr[len(IPC_FILE_PREFIX):]
                os.chmod(socket_file, 0777)

        except:
            print "Could not bind to address: %s" % bind_addr
            raise

        #print "Worker running!"

        while True:
            message = socket.recv_pyobj()
            cmd = message[0]
            params = message[1:]
            if cmd == "ready?":
                response = "OK"
            elif cmd == "shutdown":
                response = "OK Shutting down."
            elif cmd == "r":
                env = params[0]
                response = self.get_wsgi_response(env)
            else:
                response = "ERROR"
            socket.send_pyobj(response)
            if cmd == "shutdown":
                break

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "A bind address is required."
        sys.exit(1)
    wp = WorkerProcess()
    wp.run(sys.argv[1])
