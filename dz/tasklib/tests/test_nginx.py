from dz.tasklib import (nginx,
                        taskconfig,
                        utils)
from dz.tasklib.tests.dztestcase import DZTestCase

import os

class NginxTestCase(DZTestCase):

    def setUp(self):
        self.app_id = "test_nginx_001"
        self.appservers = [("foo", 123),
                           ("bar", 456)]
        self.virtual_hostnames = [
            "%s.djangozoom.net" % self.app_id,
            "myfoobar.djangozoom.net",
            "myfoobar.com",
            ]
        self.nginx_dir = self.makeDir()
        self.patch(taskconfig, "NGINX_SITES_ENABLED_DIR", self.nginx_dir)

        self.local_privileged_cmds = local_privileged_cmds = []
        def mock_local_privileged(cmd):
            print "Running mock utils.local_privileged(%r)..." % cmd
            local_privileged_cmds.append(cmd)

        self.patch(utils, "local_privileged", mock_local_privileged)


    def test_creating_new(self):
        """
        Test creating a new nginx config file for an app.
        """
        expected_site_file = os.path.join(taskconfig.NGINX_SITES_ENABLED_DIR,
                                          self.app_id)
        self.assertFalse(os.path.isfile(expected_site_file))


        self.assertEqual(len(self.local_privileged_cmds), 0)

        nginx.update_local_proxy_config(self.app_id,
                                        self.appservers,
                                        self.virtual_hostnames)

        self.assertEqual(len(self.local_privileged_cmds), 1)
        self.assertEqual(self.local_privileged_cmds[0], ["kick_nginx"])

        self.assertTrue(os.path.isfile(expected_site_file))

        file_content = file(expected_site_file).read()
        file_lines = file_content.splitlines()

        #print file_content

        self.assertTrue(len(file_content) > 0, "doh, conf file appears empty")

        for a in self.appservers:
            upstream_line = "server %s:%d" % a
            self.assertTrue(upstream_line in file_content)

    def test_fail_when_no_appservers(self):
        """
        Test that >0 appservers must be provided.
        """
        with self.assertRaises(utils.InfrastructureException):
            nginx.update_local_proxy_config(self.app_id,
                                            [],  # no appservers
                                            self.virtual_hostnames)

    def test_remove_proxy_config(self):
        """
        Test removing proxy service for an app.
        """

        expected_site_file = os.path.join(taskconfig.NGINX_SITES_ENABLED_DIR,
                                          self.app_id)

        # first try remove before it's created; that should crash
        self.assertFalse(os.path.isfile(expected_site_file))
        with self.assertRaises(utils.InfrastructureException):
            nginx.remove_local_proxy_config(self.app_id)

        # now create
        nginx.update_local_proxy_config(self.app_id,
                                        self.appservers,
                                        self.virtual_hostnames)
        self.assertTrue(os.path.isfile(expected_site_file))

        self.assertEqual(len(self.local_privileged_cmds), 1)
        self.assertEqual(self.local_privileged_cmds[0], ["kick_nginx"])

        # now remove for real
        nginx.remove_local_proxy_config(self.app_id)
        self.assertFalse(os.path.isfile(expected_site_file))

        self.assertEqual(len(self.local_privileged_cmds), 2)
        self.assertEqual(self.local_privileged_cmds[1], ["kick_nginx"])