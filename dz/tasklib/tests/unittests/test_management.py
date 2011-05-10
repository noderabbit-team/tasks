from dz.tasklib import (management,
                        taskconfig)
from dz.tasklib.tests.dztestcase import DZTestCase
import os


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
