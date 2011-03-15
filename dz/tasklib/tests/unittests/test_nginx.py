from dz.tasklib import (nginx,
                        bundle_storage_local,
                        taskconfig,
                        utils)
from dz.tasklib.tests.dztestcase import DZTestCase

import os


class NginxTestCase(DZTestCase):

    def setUp(self):

        self.app_id = "test_nginx_001"
        self.bundle_name = "bundle_test_nginx_001-2011blah"

        # appservers in (instance_id, node_name, host_ip, host_port) form
        self.appservers = [("foo", "foo_node", "10.0.0.1", 123),
                           ("bar", "bar_node", "10.0.0.2", 456)]

        self.virtual_hostnames = [
            "%s.djangozoom.net" % self.app_id,
            "myfoobar.djangozoom.net",
            "myfoobar.com",
            ]

        self.site_media_map = {"/static/": "/path/to/static",
                               "/otherstatic/": "/somewhere/else",
                               "/media/somepackage":
                                   "{SITE_PACKAGES}/somepackage/media",
                               "/media/srcpackage":
                                   "{SRC_PACKAGES}/something",
                               }

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

        nginx.update_local_proxy_config(
            self.app_id,
            self.bundle_name,
            self.appservers,
            self.virtual_hostnames,
            self.site_media_map,
            bundle_storage_engine=nginx.SKIP_BUNDLE_INSTALL)

        self.assertEqual(len(self.local_privileged_cmds), 1)
        self.assertEqual(self.local_privileged_cmds[0], ["kick_nginx"])

        self.assertTrue(os.path.isfile(expected_site_file))

        file_content = file(expected_site_file).read()

        self.assertTrue(len(file_content) > 0, "doh, conf file appears empty")

        for (instance_id, node_name, host_ip, host_port) in self.appservers:
            upstream_line = "server %s:%d" % (host_ip, host_port)
            self.assertTrue(upstream_line in file_content)

    def test_downloads_bundle_when_new(self):
        """
        Test that serving a bundle downloads it (so static media are on
        disk).
        """
        # first just make the bundle and ensure it's in local storage
        cust_dir = self.makeDir()
        self.patch(taskconfig, "NR_CUSTOMER_DIR", cust_dir)

        bundle_name = "bundle_test_deploy_app_2011-fixture"
        app_id = "test_deploy_app"
        bundle_in_storage = os.path.join(taskconfig.NR_CUSTOMER_DIR,
                                         "bundle_storage_local",
                                         bundle_name + ".tgz")

        self.assertFalse(os.path.isfile(bundle_in_storage))

        from test_deploy import create_test_bundle_in_local_storage
        bundle_tgz_name = create_test_bundle_in_local_storage()

        self.assertTrue(os.path.isfile(bundle_in_storage))
        self.assertTrue(bundle_in_storage.endswith(bundle_tgz_name))

        bundle_dir = os.path.join(cust_dir, app_id, bundle_name)

        self.assertFalse(os.path.isdir(bundle_dir))

        # ok, now serve it
        nginx.update_local_proxy_config(
            app_id,
            bundle_name,
            self.appservers,
            self.virtual_hostnames,
            self.site_media_map,
            bundle_storage_engine=bundle_storage_local)

        self.assertTrue(os.path.isdir(bundle_dir))

    def _do_update_and_get_site_conf_contents(self):
        expected_site_file = os.path.join(taskconfig.NGINX_SITES_ENABLED_DIR,
                                          self.app_id)

        nginx.update_local_proxy_config(
            self.app_id,
            self.bundle_name,
            self.appservers,
            self.virtual_hostnames,
            self.site_media_map,
            bundle_storage_engine=nginx.SKIP_BUNDLE_INSTALL)

        return file(expected_site_file).read()

    def test_static_media_mapping(self):
        """
        Test static media dir aliases in nginx conf.
        """
        file_content = self._do_update_and_get_site_conf_contents()
        # print file_content
        for url_path, file_path in self.site_media_map.items():
            self.assertTrue(("location %s" % url_path) in file_content)

    def test_file_path_variables(self):
        """
        Test the {SITE_PACKAGES} and {SRC_PACKAGES} variables.
        """
        file_content = self._do_update_and_get_site_conf_contents()
        flattened_contents = [" ".join(x.strip().split())
                              for x in file_content.split('}\n')]

        self.assertTrue("location /media/somepackage { alias " +
                        os.path.join(taskconfig.NR_CUSTOMER_DIR,
                                     self.app_id,
                                     self.bundle_name,
                                     "lib/python2.6/site-packages",
                                     "somepackage/media") + "/;"
                        in flattened_contents)

        self.assertTrue("location /media/srcpackage { alias " +
                        os.path.join(taskconfig.NR_CUSTOMER_DIR,
                                     self.app_id,
                                     self.bundle_name,
                                     "src",
                                     "something") + "/;"
                        in flattened_contents)

    def test_admin_media(self):
        """
        Test that django admin media is served in the right place.
        """
        self.assertTrue(taskconfig.DZ_ADMIN_MEDIA["url_path"].endswith("/"))
        file_content = self._do_update_and_get_site_conf_contents()
        flattened_contents = [" ".join(x.strip().split())
                              for x in file_content.split('}\n')]
        self.assertTrue("location %s { alias %s/;" % (
                taskconfig.DZ_ADMIN_MEDIA["url_path"],
                os.path.join(taskconfig.NR_CUSTOMER_DIR,
                             self.app_id,
                             self.bundle_name,
                             taskconfig.DZ_ADMIN_MEDIA["bundle_file_path"]))
                        in flattened_contents)

    def test_fail_when_no_appservers(self):
        """
        Test that >0 appservers must be provided.
        """
        with self.assertRaises(utils.InfrastructureException):
            nginx.update_local_proxy_config(self.app_id,
                                            self.bundle_name,
                                            [],  # no appservers
                                            self.virtual_hostnames,
                                            self.site_media_map)

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
        nginx.update_local_proxy_config(
            self.app_id,
            self.bundle_name,
            self.appservers,
            self.virtual_hostnames,
            self.site_media_map,
            bundle_storage_engine=nginx.SKIP_BUNDLE_INSTALL)
        self.assertTrue(os.path.isfile(expected_site_file))

        self.assertEqual(len(self.local_privileged_cmds), 1)
        self.assertEqual(self.local_privileged_cmds[0], ["kick_nginx"])

        # now remove for real
        nginx.remove_local_proxy_config(self.app_id)
        self.assertFalse(os.path.isfile(expected_site_file))

        self.assertEqual(len(self.local_privileged_cmds), 2)
        self.assertEqual(self.local_privileged_cmds[1], ["kick_nginx"])
