import subprocess
import sys

from dz.tasklib.tests.dztestcase import DZTestCase, requires_internet

from mafioso import mafconfig
from mafioso.nodemaster import NodeMaster
from mafioso.nmctl import NodeMasterControlClient


class NodeMasterClassTestCase(DZTestCase):
    """
    Test the NodeMaster class without actually starting a server
    """

    # def setUp(self):
    #     super(WsgiServerTestCase, self).setUp()

    def test_nodemaster(self):
        nm = NodeMaster()
        self.assertEqual(nm.num_bundles(), 0)

    def test_nm_serve_bundle(self):
        nm = NodeMaster()
        port = 12345
        nm.serve_bundle("bundle_test_deploy_app_2011-fixture", port)
        with self.assertRaises(ValueError):
            nm.serve_bundle("anything", port)


class ServerSubprocTestCase(DZTestCase):
    """
    Test a live nodemaster, invoked as a subprocess.
    """
    def setUp(self):
        """
        Ensure that no nodemaster process is running yet; only one process
        should exist per machine. Then start one just for this test.
        """
        super(ServerSubprocTestCase, self).setUp()

        p = subprocess.Popen([
            "sh", "-c", "pgrep -lf nodemaster.py|grep python|grep -v pgrep"],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
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

        self.server_process = subprocess.Popen(["mafioso/nodemaster.py"])
        self.client = NodeMasterControlClient()

    def tearDown(self):
        super(ServerSubprocTestCase, self).tearDown()
        self.server_process.terminate()
        self.server_process.wait()

    def test_server_running(self):
        self.assertEqual(self.client.send_command("ping"), "pong")

    def test_serve_bundle(self):
        port = self.get_random_free_port()
        self.assertTrue(self.is_port_open(port))
        resp = self.client.send_command("serve_bundle",
                                        "bundle_test_deploy_app_2011-fixture",
                                        port)
        self.assertEqual(resp, "OK")
        self.assertFalse(self.is_port_open(port))

    def test_exception(self):
        """
        Test getting an error response from the control interface
        by attempting to add two bundles on the same port.
        """
        port = self.get_random_free_port()
        self.assertTrue(self.is_port_open(port))
        resp1 = self.client.send_command("serve_bundle",
                                         "bundle_test_deploy_app_2011-fixture",
                                         port)
        self.assertEqual(resp1, "OK")
        self.assertTrue(not(self.is_port_open(port)))

        resp2 = self.client.send_command("serve_bundle",
                                         "bundle_test_deploy_app_2011-fixture",
                                         port)
        self.assertEqual(resp2, ("ERROR:\nSorry, I'm already serving " 
                                 "something on port %d") % port)

        # and we should still have the port listened
        self.assertTrue(not(self.is_port_open(port)))
