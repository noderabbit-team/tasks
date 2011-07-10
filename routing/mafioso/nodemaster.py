#!/usr/bin/env python

import subprocess

import eventlet
import eventlet.wsgi
from eventlet.green import zmq

ASLEEP = "ASLEEP"
WAKING = "WAKING"
AWAKE = "AWAKE"

import mafconfig

context = zmq.Context()
pool = eventlet.GreenPool(10000)


class BundleWorker(object):
    """
    Represents a worker process running on this machine, associated with
    a particular bundle.

    This class starts the actual worker in a subprocess using
    WORKER_EXE, and communicates with that worker using zmq.

    That subprocess will start, bind to the appropriate zmq socket(s) so I
    can control it, and then become available to respond to requests.
    """
    def __init__(self, bundle_name):
        self.bundle_name = bundle_name
        self.addr = mafconfig.WORKER_ADDR_FORMAT % (self.bundle_name,
                                                    str(id(self)))

        print "LAUNCHING NM WORKER", self.addr, "...",
        self.subproc = subprocess.Popen([mafconfig.WORKER_EXE, self.addr])
        self.sock = context.socket(zmq.REQ)
        self.sock.connect(self.addr)

        # make the first request to the worker before returning
        self.sock.send_pyobj(["ready?"])
        rep = self.sock.recv_pyobj()
        print "worker subprocess says: %r" % (rep,)

    def process_request(self, env, start_response):
        """Marshal this request to a running instance."""

        # we can't just send env directly because it has filehandles.
        # so we screen those out.
        safe_env = dict()

        for k, v in env.iteritems():
            # TODO: figure out how to make all this stuff work over IPC
            if k not in ("eventlet.posthooks",
                         "eventlet.input",
                         "wsgi.input",
                         "wsgi.errors"):
                safe_env[k] = v

        self.sock.send_pyobj(["r", safe_env])
        (start_response_args, result) = self.sock.recv_pyobj()

        #start_response('200 OK', [('Content-Type', 'text/plain')])
        # return ['Hello, bundle %s\r\n' % (
        #     self.bundle_name)]
        start_response(*start_response_args)
        return result


class ServedBundle(object):
    STATES = set([ASLEEP,  # no worker process running
                  WAKING,  # worker process starting but not ready
                  AWAKE])  # worker running & ready for requests

    def __init__(self, bundle_name):
        self.bundle_name = bundle_name
        self.state = ASLEEP
        self.port = None
        self.workers = []
        self.worker_pointer = 0

    def get_worker(self):
        """
        Select an existing worker or create a new one if there isn't one
        around already.
        TODO: dynamically change the worker pool size based on demand.
        """
        l = len(self.workers)
        if l:
            result = self.workers[self.worker_pointer % l]
        else:
            result = BundleWorker(self.bundle_name)
            self.workers.append(result)

        self.worker_pointer += 1
        return result

    def wsgi_responder(self, env, start_response):
        worker = self.get_worker()
        return worker.process_request(env, start_response)

    def listen_http(self, sock, port):
        if self.port is not None:
            raise RuntimeError(("This bundle [%s] is already listening on "
                                "port %d. Can't listen on %d too!") %
                               (self.bundle_name, self.port))
        self.port = port
        eventlet.wsgi.server(sock, self.wsgi_responder)


class NodeMaster(object):
    """
    Master process for WSGI workers. We expect to run one nodemaster process
    per appserver node, with the front-end proxy distributing load across
    multiple appservers.
    """

    def __init__(self):
        self.bundles_by_port = {}
        self.servers_by_port = {}

        self.control_socket = context.socket(zmq.REP)
        self.control_socket.bind(mafconfig.CONTROL_ADDR)

    def num_bundles(self):
        """
        Get the number of bundle instances currently being served by this
        nodemaster.
        """
        return len(self.bundles_by_port)

    def serve_bundle(self, bundle_name, port):
        if port in self.bundles_by_port:
            raise ValueError("Sorry, I'm already serving something on port %d"
                             % port)
        sb = ServedBundle(bundle_name)
        self.bundles_by_port[port] = sb
        # call eventlet.listen() here so that the port is grabbed
        # before I return
        sock = eventlet.listen(('', port))
        pool.spawn_n(sb.listen_http, sock, port)

    def control_loop(self):
        while 1:
            msg_list = self.control_socket.recv_pyobj()
            resp = "ERROR"

            try:
                cmd = msg_list[0]
                params = msg_list[1:]
                resp = "Unknown command: %r" % cmd

                if cmd == "ping":
                    resp = "pong"
                elif cmd == "serve_bundle" and len(params) == 2:
                    bundle_name = params[0]
                    port = int(params[1])
                    self.serve_bundle(bundle_name, port)
                    resp = "OK"

                print "CONTROL: %r --> %r" % (msg_list, resp)

            except Exception, e:
                resp = "ERROR:\n" + str(e)

            finally:
                self.control_socket.send_pyobj(resp)

    def mainloop(self):
        print "Nodemaster starting... ",
        control = pool.spawn(self.control_loop)
        # chat = eventlet.spawn(self.chatserver_loop)
        print "ready."

        try:
            control.wait()
            # chat.wait()
        except (SystemExit, KeyboardInterrupt):
            print "\nNodemaster exiting."
            pass


if __name__ == "__main__":
    nm = NodeMaster()
    nm.mainloop()
