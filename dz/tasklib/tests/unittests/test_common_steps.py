from dz.tasklib import (taskconfig,
                        utils,
                        common_steps)

from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib.tests.stub_zoomdb import StubZoomDB

import os


class CommonStepsTestCase(DZTestCase):
    def setUp(self):
        self.cust_dir = self.makeDir()
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.cust_dir)
        self.zoomdb = StubZoomDB()
        self.opts = {
            "CO_DIR": self.makeDir(dirname=self.cust_dir),
            }

    def test_checking_out_bad_repo(self):
        """
        Test attempting to checkout an invalid URL.
        """

        with self.assertRaises(utils.ProjectConfigurationException):
            self.opts["SRC_URL"] = "fake url"
            common_steps.checkout_code(self.zoomdb, self.opts)

    def test_change_of_repo_url(self):
        """
        Test checking out from a changed repo URL.
        """
        repos = []
        for repo_num in range(2):
            repo_dir = self.makeDir()
            utils.local("git init %s" % repo_dir)
            utils.local("touch %s/file_%d" % (repo_dir, repo_num))
            utils.local("cd %s; git add file_%d; git commit -m 'unittest'" % (
                repo_dir, repo_num))
            repos.append(dict(num=repo_num,
                              path=repo_dir))

        co_dir = self.makeDir()
        opts = {"CO_DIR": co_dir,
                "SRC_URL": repos[0]["path"]}
        common_steps.checkout_code(self.zoomdb, opts)
        self.assertTrue(os.path.isfile("%s/file_%d" % (co_dir, 0)))
        self.assertFalse(os.path.isfile("%s/file_%d" % (co_dir, 1)))

        # now change the repo source url
        opts["SRC_URL"] = repos[1]["path"]
        common_steps.checkout_code(self.zoomdb, opts)
        self.assertTrue(os.path.isfile("%s/file_%d" % (co_dir, 1)),
                        "New repo should be in place.")
        self.assertFalse(os.path.isfile("%s/file_%d" % (co_dir, 0)),
                         "Old repo shouldn't still be in place.")

        # and run again to ensure we now do a pull
        self.zoomdb.logs = []
        self.assertFalse(("Running git pull...", "i") in self.zoomdb.logs)
        common_steps.checkout_code(self.zoomdb, opts)
        self.assertTrue(("Running git pull...", "i") in self.zoomdb.logs)
