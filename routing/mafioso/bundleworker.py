#!/usr/bin/env python

import sys

import zmq


context = zmq.Context()


class WorkerProcess(object):
    def run(self, bind_addr):
        socket = context.socket(zmq.REP)
        socket.bind(bind_addr)

        print "Running a worker!"

        while 1:
            message = socket.recv_pyobj()
            cmd = message[0]
            params = message[1:]
            if cmd == "ready?":
                response = "OK"
            elif cmd == "r":
                env = params[0]
                response = (
                    ('200 OK', [('Content-Type', 'text/plain')]),
                    ["Hello to %s from a worker at %s!" % (
                        str(env.keys()),
                        bind_addr)],
                    )
            else:
                response = "ERROR"
            socket.send_pyobj(response)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "A bind address is required."
        sys.exit(1)
    wp = WorkerProcess()
    wp.run(sys.argv[1])
