import eventlet

import subprocess
import sys
import time

from dz.tasklib.tests.dztestcase import DZTestCase  # , requires_internet

from mafioso import mafconfig
from mafioso.nodemaster import NodeMaster
from mafioso.nmctl import NodeMasterControlClient


class NodeMasterClassTestCase(DZTestCase):
    """
    Test the NodeMaster class without actually starting a server.
    """

    def setUp(self):
        super(NodeMasterClassTestCase, self).setUp()
        self.nm = NodeMaster()
        #print "Local nm in pid = %d" % os.getpid()

    def tearDown(self):
        self.nm.destroy()
        del self.nm

    def test_nodemaster(self):
        self.assertEqual(self.nm.num_bundles(), 0)

    def test_nm_serve_bundle(self):
        port = self.get_random_free_port()
        self.assertTrue(self.is_port_open(port))
        self.assertTrue(self.is_port_open(port))
        self.nm.serve_bundle("test_deploy_app",
                             "bundle_test_deploy_app_2011-fixture",
                             port)
        self.assertFalse(self.is_port_open(port))
        with self.assertRaises(ValueError):
            self.nm.serve_bundle("anyapp", "anybundle", port)

        return port

    def test_unserve(self):
        port = self.test_nm_serve_bundle()
        eventlet.sleep()
        self.assertEqual(self.nm.num_bundles(), 1)
        self.assertFalse(self.is_port_open(port))

        self.nm.unserve(port)

        self.assertTrue(self.is_port_open(port))


class ServerSubprocTestCase(DZTestCase):
    """
    Test a live nodemaster, invoked as a subprocess.
    """
    def setUp(self):
        """
        Ensure that no nodemaster process is running yet; only one process
        should exist per machine. Then start one just for this test.
        """
        #print "\n==ServerSubprocTestCase: setUp begin==\n"
        super(ServerSubprocTestCase, self).setUp()

        p = subprocess.Popen([
            "sh", "-c", "pgrep -lf nodemaster.py|grep python|grep -v pgrep"],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        # print "==Launched nm subproc: %d==" % p.pid

        output, errors = p.communicate()
        if len(output):
            sys.stderr.write(
                "It looks like a nodemaster process is already running "
                "locally. You should kill it before attempting to run "
                "the nodemaster server test suite.\n=== Processes: ===\n%s"
                % output)
            sys.exit()

        # clear socket just to prove we have permission to it
        subprocess.check_call(["rm", "-f", mafconfig.CONTROL_SOCKET_FILE])

        # run subproc using unbuffered python for sanity of output
        self.server_process = subprocess.Popen(["python", "-u",
                                                "mafioso/nodemaster.py"])
        self.client = NodeMasterControlClient()
        # print "\n==ServerSubprocTestCase: setUp done==\n"

    def tearDown(self):
        # print "\n==ServerSubprocTestCase: tearDown begin==\n"
        super(ServerSubprocTestCase, self).tearDown()
        self.check_command("exit")
        for wait_time in range(100):
            time.sleep(wait_time * 0.01)
            if self.server_process.poll() is not None:
                break

        if self.server_process.poll() is None:
            self.server_process.terminate()
            self.server_process.wait()
        # print "\n==ServerSubprocTestCase: tearDown done; poll=%r==\n" % (
        #     self.server_process.poll(),)

    def check_command(self, *args):
        """
        Send a command to server and check that result is OK.
        """
        resp = self.client.send_command(*args)
        if not resp.startswith("OK"):
            raise RuntimeError("Not OK response: %r" % resp)
        return resp

    def test_server_running(self):
        self.assertEqual(self.client.send_command("ping"), "pong")

    def test_serve_bundle(self):
        port = self.get_random_free_port()
        self.assertTrue(self.is_port_open(port))
        # print "REQ: serve_bundle on %d" % port
        resp = self.client.send_command("serve_bundle",
                                        "bundle_test_deploy_app",
                                        "bundle_test_deploy_app_2011-fixture",
                                        port)
        # print "REQ SENT"
        self.assertEqual(resp, "OK")
        self.assertFalse(self.is_port_open(port))
        self.check_can_eventually_load("http://localhost:%d" % port,
                                       "'wsgi.url_scheme': 'http'")

    def test_exception(self):
        """
        Test getting an error response from the control interface
        by attempting to add two bundles on the same port.
        """
        port = self.get_random_free_port()
        self.assertTrue(self.is_port_open(port))
        resp1 = self.client.send_command("serve_bundle",
                                         "bundle_test_deploy_app",
                                         "bundle_test_deploy_app_2011-fixture",
                                         port)
        self.assertEqual(resp1, "OK")
        self.assertTrue(not(self.is_port_open(port)))

        self.check_command("silence_errors")
        resp2 = self.client.send_command("serve_bundle",
                                         "bundle_test_deploy_app",
                                         "bundle_test_deploy_app_2011-fixture",
                                         port)
        self.assertEqual(resp2, ("ERROR:\nSorry, I'm already serving "
                                 "something on port %d") % port)

        # and we should still have the port listened
        self.assertTrue(not(self.is_port_open(port)))
