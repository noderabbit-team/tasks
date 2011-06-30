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


VCSes = ("git", "hg")


class RepoCheckoutTestCase(DZTestCase):
    def setUp(self):
        self.zoomdb = StubZoomDB()

        self.work_dir = self.makeDir()
        self.opts = {
            "CO_DIR": self.work_dir,
            }
        self.repo_dirs = {}

        for vcs in VCSes:
            self.repo_dirs[vcs] = self.makeDir()
            repo_archive = self.get_fixture_path("test-repo-%s.tar.gz" % vcs)
            utils.local("cd %s; tar xvzf %s" % (self.repo_dirs[vcs],
                                                repo_archive))
        super(RepoCheckoutTestCase, self).setUp()

    def _set_to_use_repo(self, repo_type):
        self.opts["SRC_URL"] = "file://%s/test-repo-%s" % (
            self.repo_dirs[repo_type],
            repo_type)
        self.opts["SRC_REPO_TYPE"] = repo_type

    def _test_checkout_repo(self, repo_type):
        """
        Test checking out a repo of the given type.
        """
        self._set_to_use_repo(repo_type)
        test_file = os.path.join(self.opts["CO_DIR"], "test.txt")
        self.assertFalse(os.path.isfile(test_file))
        self.assertFalse(("Cloning your repository.", "i") in self.zoomdb.logs)

        common_steps.checkout_code(self.zoomdb, self.opts)

        self.assertTrue(os.path.isfile(test_file))
        self.assertEqual(open(test_file).read(), "Hello world\n")
        self.assertTrue(("Cloning your repository.", "i") in self.zoomdb.logs)

    def test_checkout_hg(self):
        """
        Test checking out a mercurial repo.
        """
        return self._test_checkout_repo("hg")

    def test_checkout_git(self):
        """
        Test checking out a git repo.
        """
        return self._test_checkout_repo("git")
