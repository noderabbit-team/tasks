from dz.tasklib import (taskconfig,
                        utils,
                        bundle,
                        deploy)
from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib.tests.unittests.test_deploy import AbstractDeployTestCase

from os import path
import shutil


class SetupSecurityTestCase(DZTestCase):
    def setUp(self):
        self.project_name = "app"
        self.cust_dir = self.makeDir()
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.cust_dir)

    def tearDown(self):
        self.chown_to_me(self.cust_dir)

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


class DeploySecurityTestCase(AbstractDeployTestCase):

    def test_chown_post_install(self):
        """
        Ensure that after a bundle is extracted it is owned by the app user.
        """
        self.install_my_bundle()
        bundle_dir = path.join(self.customer_directory,
                               self.app_id,
                               self.bundle_name)
        self.assertFileOwnedBy(bundle_dir, self.app_id)

    def test_safe_deploy(self):
        """
        Test that deployed code runs under the proper user.
        """
        self.install_my_bundle()
        (instance_id, node_name, host_ip, host_port) = \
            deploy.start_serving_bundle(self.app_id, self.bundle_name)
        app_url = "http://%s:%d/securitytest/" % (host_ip, host_port)
        security_result = self.check_can_eventually_load(
            app_url)
        self.assertTrue(security_result.startswith("SECURITY TEST RESULTS"))

        # convert security lines into a dict
        # EXAMPLE (a failing result):
        """SECURITY TEST RESULTS
whoami: shimon
ls /: bin,boot,cdrom,cgroup,cust,dev,etc,home,initrd.img,initrd.img.old,lib,lib32,lib64,lost+found,media,mnt,opt,proc,root,sbin,selinux,srv,sys,tmp,usr,var,vmlinuz,vmlinuz.old
        """

        sec = {}
        for line in security_result.splitlines()[1:]:
            line = line.strip()
            if not ": " in line:
                continue
            k, v = line.split(": ", 1)
            sec[k] = v

        self.assertEqual(sec["whoami"], self.app_id,
                         ("Expected app to be running as %r, but actually "
                          "is running as %r") % (self.app_id, sec["whoami"]))
        self.assertEqual(sec["ls /"], ",".join(
            sorted(['bin', 'etc', 'lib', 'lib64', 'usr',
                    taskconfig.NR_CUSTOMER_DIR.strip("/")])))
