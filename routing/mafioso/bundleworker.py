#!/usr/bin/env python

import sys

import zmq


context = zmq.Context()


class WorkerProcess(object):

    def __init__(self):
        self.bind_addr = None

    def get_wsgi_callable(self):
        pass

    def get_wsgi_response(self, env):
        response = (
            ('200 OK', [('Content-Type', 'text/plain')]),
            ["Hello to %s from a worker at %s!" % (
                str(env.keys()),
                self.bind_addr)],
            )
        return response

    def run(self, bind_addr):
        socket = context.socket(zmq.REP)
        socket.bind(bind_addr)

        print "Worker running!"

        # TODO: drop perms & enter userenv

        while True:
            message = socket.recv_pyobj()
            cmd = message[0]
            params = message[1:]
            if cmd == "ready?":
                response = "OK"
            elif cmd == "r":
                env = params[0]
                response = self.get_wsgi_response(env)
            else:
                response = "ERROR"
            socket.send_pyobj(response)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "A bind address is required."
        sys.exit(1)
    wp = WorkerProcess()
    wp.run(sys.argv[1])
