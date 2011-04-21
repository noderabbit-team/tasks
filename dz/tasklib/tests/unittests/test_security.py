from dz.tasklib import (taskconfig,
                        utils,
                        bundle)
from dz.tasklib.tests.dztestcase import DZTestCase

from os import path
import os
import shutil


class SecurityTestCase(DZTestCase):
    def setUp(self):
        self.project_name = "app"
        self.cust_dir = self.makeDir()
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.cust_dir)

    def test_safe_build(self):
        """
        Test that build actions run under the proper user.
        """
        # use the app fixture and create a repo
        here = path.abspath(path.split(__file__)[0])
        src = path.join(here, '../fixtures', self.project_name)
        dest = path.join(self.cust_dir, self.project_name)
        shutil.copytree(src, dest)
        utils.local('(cd %s; git init; git add -A; git commit -m test)' %
                    path.join(dest, 'src'))

        (bundle_name, code_revision) = bundle.bundle_app(self.project_name)
        bundle_dir = path.join(self.cust_dir, self.project_name, bundle_name)

        a_bundle_file = path.join(bundle_dir, "user-repo", "settings.py")
        self.assertFileOwnedBy(a_bundle_file, self.project_name)
