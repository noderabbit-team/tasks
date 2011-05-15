from dz.tasklib import (utils,
                        management)
from dz.tasklib.tests.dztestcase import DZTestCase


class ManagementTestCase(DZTestCase):

    def test_get_installed_bundles(self):
        """
        Test getting a list of installed (on-disk) bundles.
        """
        installed_bundles = management.get_installed_bundles()
        self.assertTrue(isinstance(installed_bundles, list),
                        str(installed_bundles))

    def test_get_nginx_sites_enabled(self):
        """
        Test getting a list of sites enabled with nginx.
        """
        sites_enabled = management.get_nginx_sites_enabled()
        self.assertTrue(isinstance(sites_enabled, list),
                        str(sites_enabled))

    def test_df_dump(self):
        """
        Test getting a string with human-readable ``df`` output.
        """
        df = management.get_df()
        self.assertTrue(isinstance(df, str), str(df))

    def test_get_uptime(self):
        uptime = management.get_uptime()
        self.assertTrue(isinstance(uptime, float))

    def test_get_loadavg(self):
        loadavg = management.get_loadavg()
        self.assertEqual(len(loadavg), 3)
        for x in loadavg:
            self.assertTrue(isinstance(x, float))

    def test_get_unicorns(self):
        """
        Test getting a list of unicorn processes running on this machine.
        """
        unicorns = management.get_unicorns()

        self.assertTrue(isinstance(unicorns, list), unicorns)
        for u in unicorns:
            self.assertTrue(isinstance(u, dict))
            self.assertTrue(isinstance(u["bundle_name"], str))
            self.assertTrue(isinstance(u["master_pid"], long),
                                       type(u["master_pid"]))
            self.assertTrue(isinstance(u["worker_pids"], list))
            self.assertTrue(isinstance(u["user"], str), u["user"])


    def test_gunicorn_signal(self):
        with self.assertRaises(utils.InfrastructureException):
            management.gunicorn_signal(-1, "TTIN", "NOT_AN_APPSERVER")
