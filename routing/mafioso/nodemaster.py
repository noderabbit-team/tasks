#!/usr/bin/env python
import eventlet
import eventlet.wsgi
from eventlet.green import zmq

ASLEEP = "ASLEEP"
WAKING = "WAKING"
AWAKE = "AWAKE"

import mafconfig

POOL = eventlet.GreenPool(10000)


class BundleWorker(object):
    """
    Represents a worker process running on this machine, associated with
    a particular bundle.

    This class starts the actual worker in a subprocess using
    bundleworker.py, and communicates with that worker using zmq.
    """
    def __init__(self, bundle_name):
        self.bundle_name = bundle_name
        self.started

    def process_request(self, env, start_response):
        """Marshal this request to a running instance."""
        # TODO:
        # 1. run a subprocess
        # 2. communicate with it
        # 3. have it run my bundle's code
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return ['Hello, bundle %s\r\n' % (
            self.bundle_name)]


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

        self.ctx = zmq.Context()
        self.control_socket = self.ctx.socket(zmq.REP)
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
        POOL.spawn_n(sb.listen_http, sock, port)

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
        control = POOL.spawn(self.control_loop)
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
