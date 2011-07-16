#!/usr/bin/env python

import os
import re
import shutil
import signal
import sys
import traceback

import eventlet
import eventlet.wsgi
from eventlet.green import zmq, socket

from dz.tasklib import (utils,
                        userenv)

ASLEEP = "ASLEEP"
WAKING = "WAKING"
AWAKE = "AWAKE"

# what chars are allowed in app and bundle names
SAFE_CHARS = re.compile(r'^[0-9A-Za-z\-_]+$')

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
    def __init__(self, served_bundle):
        self.served_bundle = served_bundle
        fmt_info = {
            "app_id": served_bundle.app_id,
            "bundle_name": served_bundle.bundle_name,
            "worker_id": str(id(self))}
        self.worker_dir = wd = mafconfig.WORKER_DIR_FORMAT % fmt_info
        self.addr = mafconfig.WORKER_ADDR_FORMAT % {"worker_dir": wd}
        bundleworker_path = (mafconfig.WORKER_USERENV_BUNDLEWORKER_PATH_FORMAT
                             % {"worker_dir": wd})
        print "LAUNCHING NM WORKER", self.addr, "...",

        ue = self.served_bundle.userenv
        if not os.path.isdir(wd):
            os.makedirs(wd)
        utils.local_privileged(["project_chown", served_bundle.app_id, wd])
        ue.subproc(["chmod", "0755", wd])
        ue.write_string_to_file(open(mafconfig.WORKER_EXE).read(),
                                bundleworker_path)
        self.worker_proc = ue.popen(["/usr/bin/python", bundleworker_path,
                                     self.addr])
        #print "Worker proc launched: %r" % self.worker_proc
        #self.subproc = subprocess.Popen([mafconfig.WORKER_EXE, self.addr])
        self.sock = context.socket(zmq.REQ)
        self.sock.connect(self.addr)
        #print "connected to worker"
        # make the first request to the worker before returning
        self.sock.send_pyobj(["ready?"])
        print "Waiting for worker to be ready ... ",
        rep = self.sock.recv_pyobj()
        print "OK: %r" % (rep,)

    def destroy(self):
        # first, attempt to send a polite shutdown request
        self.sock.send_pyobj(["shutdown"])

        #print "CLOSING ZMQ WORKER SOCKET"
        self.sock.close()

        # give it a little time to exit
        for wait in range(20):
            if self.worker_proc.poll() is None:
                eventlet.sleep(0.1 * wait)
            else:
                break

        # didn't work? try SIGTERM and SIGKILL
        pid = self.worker_proc.pid
        for signum in (signal.SIGTERM, signal.SIGKILL):
            if self.worker_proc.poll() is None:
                utils.local_privileged(["kill_worker", signum, str(pid)])

                for wait in range(20):
                    eventlet.sleep(0.1 * wait)
                    if self.worker_proc.poll() is not None:
                        break

        # if it's still alive, CRAZY ERROR
        if self.worker_proc.poll() is None:
            print ("ERROR: cannot terminate worker %s, process %d" %
                   (self.worker_dir, self.worker_proc.pid))
            return

        utils.chown_to_me(self.worker_dir)
        shutil.rmtree(self.worker_dir)

    def process_request(self, env, start_response):
        """Marshal this request to a running instance."""

        # we can't just send env directly because it has filehandles.
        # so we screen those out.
        safe_env = dict()

        for k, v in env.iteritems():
            # TODO: figure out how to make all this stuff work over IPC
            # In particular wsgi.input is a filehandle, need to pass it
            # to the worker.
            #
            # According to eventlet.wsgi:
            # - wsgi.errors defaults to sys.stderr
            # - wsgi.input and eventlet.input are an eventlet.wsgi.Input
            #   object, which wraps a file obj for async reads and writes.
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

    def __init__(self, app_id, bundle_name):
        self.app_id = app_id
        self.bundle_name = bundle_name
        self.state = ASLEEP
        self.port = None
        self.workers = []
        self.worker_pointer = 0
        self.userenv = None  # instantiate userenv dynamically
        self.sock = None
        self.server_thread = None

    def destroy(self):
        """Kill my workers cleanly. Stop listening on the port."""

        # Stop the server thread, so it doesn't attempt any more socket reads
        # when I close the socket.
        if self.server_thread:
            #print "KILLING SERVER THREAD"
            self.server_thread.kill()

        # Shut down the socket.
        if self.sock:
            #print "CLOSING SERVER SOCKET"
            self.sock.close()
            #self.sock.shutdown(socket.SHUT_RDWR)

        # Stop the worker processes.
        for w in self.workers:
            w.destroy()
        if self.userenv and not(self.userenv.destroyed):
            self.userenv.destroy()

    def get_worker(self):
        """
        Select an existing worker or create a new one if there isn't one
        around already.
        TODO: dynamically change the worker pool size based on demand.
        """

        if not self.userenv:
            self.userenv = userenv.UserEnv(self.app_id)

        l = len(self.workers)
        if l:
            result = self.workers[self.worker_pointer % l]
        else:
            result = BundleWorker(self)
            self.workers.append(result)

        self.worker_pointer += 1
        return result

    def wsgi_responder(self, env, start_response):
        worker = self.get_worker()
        return worker.process_request(env, start_response)

    def listen_http(self, port):
        """
        Spawn a listening server.
        """
        if self.port is not None:
            raise RuntimeError(("This bundle [%s] is already listening on "
                                "port %d. Can't listen on %d too!") %
                               (self.bundle_name, self.port))
        self.port = port
        self.sock = eventlet.listen(('', port))
        # print "LISTENING (pid=%d): %r" % (os.getpid(),
        #                                   self.sock.getsockname())
        self.server_thread = pool.spawn(
            eventlet.wsgi.server, self.sock, self.wsgi_responder)
        # eventlet.wsgi.server(sock, self.wsgi_responder)


class NodeMaster(object):
    """
    Master process for WSGI workers. We expect to run one nodemaster process
    per appserver node, with the front-end proxy distributing load across
    multiple appservers.
    """

    def __init__(self):
        self.bundles_by_port = {}

        self.control_socket = context.socket(zmq.REP)
        self.control_socket.bind(mafconfig.CONTROL_ADDR)
        self.silence_errors = False

    def destroy(self):
        """
        Terminate workers in preparation for immediate exit.
        """
        eventlet.sleep()  # let pending stuff start, so I can kill it!

        print "NodeMaster: Preparing to exit... ",

        for port, bundle in self.bundles_by_port.iteritems():
            bundle.destroy()

        self.bundles_by_port = {}

    def num_bundles(self):
        """
        Get the number of bundle instances currently being served by this
        nodemaster.
        """
        return len(self.bundles_by_port)

    def serve_bundle(self, app_id, bundle_name, port):
        if port in self.bundles_by_port:
            raise ValueError("Sorry, I'm already serving something on port %d"
                             % port)
        if not SAFE_CHARS.match(app_id):
            raise ValueError(
                "Sorry, the app_id %r contains disallowed characters." %
                app_id)
        if not SAFE_CHARS.match(bundle_name):
            raise ValueError(
                "Sorry, the bundle_name %r contains disallowed characters." %
                bundle_name)

        sb = ServedBundle(app_id, bundle_name)
        self.bundles_by_port[port] = sb
        # tell sb to listen right away (sync) and respond (async)
        sb.listen_http(port)

    def unserve(self, port):
        if port not in self.bundles_by_port:
            raise KeyError("Sorry, port %d is not currently served." % port)
        self.bundles_by_port[port].destroy()
        del self.bundles_by_port[port]

    def control_loop(self):
        while 1:
            msg_list = self.control_socket.recv_pyobj()
            resp = "ERROR"

            try:
                cmd = msg_list[0]
                params = msg_list[1:]
                resp = "Unknown command or invalid parameters: %r" % cmd

                if cmd == "ping":
                    resp = "pong"
                elif cmd == "serve_bundle" and len(params) == 3:
                    app_id = params[0]
                    bundle_name = params[1]
                    port = int(params[2])
                    self.serve_bundle(app_id, bundle_name, port)
                    resp = "OK"
                elif cmd == "unserve" and len(params) == 1:
                    port = int(params[0])
                    self.unserve(port)
                    resp = "OK"
                elif cmd == "exit":
                    resp = "OK exiting."
                    # exit actually handled below in finally: clause
                elif cmd == "silence_errors":
                    self.silence_errors = True
                    resp = "OK errors silenced."

                print "CONTROL: %r --> %r" % (msg_list, resp)

            except Exception, e:
                if not self.silence_errors:
                    print >> sys.stderr, (
                        "\n*** Nodemaster Error during Request: ***")
                    traceback.print_exc()
                    print >> sys.stderr, "*** end of Nodemaster Error ***\n"
                resp = "ERROR:\n" + str(e)

            finally:
                self.control_socket.send_pyobj(resp)
                if cmd == "exit":
                    return

    def mainloop(self):
        print "Nodemaster starting... ",
        control = pool.spawn(self.control_loop)
        # chat = eventlet.spawn(self.chatserver_loop)
        print "ready."
        return control.wait()


if __name__ == "__main__":
    nm = NodeMaster()

    def signal_handler(signum, strackframe):
        nm.destroy()
        sys.exit(100)

    signal.signal(signal.SIGTERM, signal_handler)

    try:
        nm.mainloop()
    finally:
        nm.destroy()
        print "Nodemaster exiting OK."
