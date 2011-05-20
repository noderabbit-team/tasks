from dz.tasklib import (userenv,
                        taskconfig,
                        utils)
from dz.tasklib.tests.dztestcase import DZTestCase
from os import path
import os
import random
import time


class UtilsTestCase(DZTestCase):
    def setUp(self):
        here = path.abspath(path.split(__file__)[0])
        self.fixtures_dir = path.join(here, '../fixtures')

        self.project_sysid = "app"
        self.ue = userenv.UserEnv(self.project_sysid)

    def tearDown(self):
        try:
            self.ue.destroy()
        except userenv.AlreadyDestroyed:
            pass

        try:
            self.ue.undo_monkeypatch_pip_util_get_file_content()
        except ValueError:
            pass

    def test_init(self):
        """Test basic UE initialization."""
        self.assertEqual(self.ue.username, self.project_sysid)

    def test_subproc(self):
        """Test that a subprocess runs as the env's user."""
        stdout, stderr, p = self.ue.subproc(["whoami"])
        self.assertEqual(stdout.strip(), self.ue.username)

    def test_subproc_nonzero(self):
        """Test that a failed subprocess causes an exception to be raised."""
        with self.assertRaises(userenv.ErrorInsideEnvironment):
            self.ue.subproc(["cat", "/nonexistent"])

    def test_subproc_stdin_string(self):
        test_string = "Hello, world!"
        stdout, stderr, p = self.ue.subproc(["cat"], stdin_string=test_string)
        self.assertEqual(stdout, test_string, stdout)
        self.assertEqual(stderr, "", stderr)
        self.assertEqual(p.returncode, 0)

    def test_chroot_isolation(self):
        """Test that only a limited set of directories are available thanks
        to chroot."""
        wd, _1, _2 = self.ue.subproc(["pwd"])
        self.assertEqual(wd.strip(), "/")
        ls, _1, _2 = self.ue.subproc(["ls"])
        self.assertEqual(
            sorted(ls.splitlines()),
            sorted(['bin', 'dev', 'etc', 'lib', 'lib64', 'usr',
                    taskconfig.NR_CUSTOMER_DIR.strip("/").split("/")[0]]))

    def test_subproc_requires_list(self):
        """Test that subproc verifies that its command argument must be in
        list form (not a string)."""
        with self.assertRaises(AssertionError):
            self.ue.subproc("echo")

    def test_cleanup(self):
        """Test that when an env is destroyed, its directory is cleaned up."""
        self.assertTrue(path.isdir(self.ue.container_dir))
        self.ue.destroy()
        self.assertFalse(path.isdir(self.ue.container_dir))

    def test_cleanup_automatic(self):
        """Test that when an env goes out of scope, its directory is deleted."""
        x = userenv.UserEnv(self.project_sysid)
        x_cdir = x.container_dir
        self.assertTrue(path.isdir(x_cdir))
        del x

        num_attempts = 0
        while True:
            self.assertTrue(num_attempts < 10)
            if not(path.isdir(x_cdir)):
                break # test passes, no longer a dir
            num_attempts += 1
            time.sleep(1)

    def test_cleanup_too_much(self):
        """Test that an exception is raised if we try to destroy twice."""
        self.ue.destroy()
        with self.assertRaises(userenv.AlreadyDestroyed):
            self.ue.destroy()

    def test_open_read(self):
        """
        Test reading a file within the userenv.
        """
        f = self.ue.open("/bin/uncompress")
        self.assertEqual(f.readlines()[0], "#!/bin/bash\n")
        f.close()  # just to verify this part of the file interface works

    def test_write_string_to_file(self):
        """Test the write_string_to_file function."""
        filename = "/test_write_string_to_file.txt"
        some_crap = str(random.randint(999999999999999999999999,
                                       1999999999999999999999999))
        self.ue.write_string_to_file(some_crap, filename)
        file_content, _1, _2 = self.ue.subproc(["cat", filename])
        self.assertEqual(some_crap, file_content)

    def test_open_write(self):
        """
        Test writing a file within the userenv.
        """
        filename = "/cust/%s/test_open_write.txt" % self.project_sysid
        f = self.ue.open(filename, "w")
        some_crap = str(random.randint(999999999999999999999999,
                                       1999999999999999999999999))
        f.write(some_crap)
        f.close()
        file_content, _1, _2 = self.ue.subproc(["cat", filename])
        self.assertEqual(some_crap, file_content)

    def test_pip_monkeypatch_application(self):
        import pip.util

        orig_gfc = pip.util.get_file_content

        self.ue.monkeypatch_pip_util_get_file_content()
        self.assertNotEqual(pip.util.get_file_content, orig_gfc)

        # test that another import statement makes no difference
        import pip.util
        self.assertNotEqual(pip.util.get_file_content, orig_gfc)

        self.ue.undo_monkeypatch_pip_util_get_file_content()
        self.assertEqual(pip.util.get_file_content, orig_gfc)

        # but only one undo
        with self.assertRaises(ValueError):
            self.ue.undo_monkeypatch_pip_util_get_file_content()

    def test_pip_monkeypatch_behavior(self):
        import pip.util

        # test the behavior of the monkeypatch.
        self.ue.monkeypatch_pip_util_get_file_content()
        some_crap = str(random.randint(999999999999999999999999,
                                       1999999999999999999999999))
        filename = "/test_pip_monkeypatch.txt"
        self.ue.write_string_to_file(some_crap, filename)

        location, content = pip.util.get_file_content(filename, None)

        self.assertEqual(location, filename)
        self.assertEqual(content, some_crap)

    def test_remove(self):
        """
        Test removing a file within the UE.
        """
        filename = "/test_remove.txt"
        self.ue.write_string_to_file("hello world", filename)
        self.ue.open(filename).read()  # should work

        self.ue.remove(filename)

        with self.assertRaises(OSError):
            self.ue.open(filename).read()  # should fail

    def test_env_includes_cust_dir(self):
        """
        Test that env includes the current customer's directory.
        """
        some_crap = str(random.randint(999999999999999999999999,
                                       1999999999999999999999999))
        user_dir = path.join(taskconfig.NR_CUSTOMER_DIR, self.project_sysid)
        fake_bundle_dir = path.join(user_dir, "testbundle")
        if not path.isdir(fake_bundle_dir):
            os.mkdir(fake_bundle_dir)
        utils.local_privileged(["project_chown",
                                self.project_sysid,
                                fake_bundle_dir])

        some_crap_filename = path.join(fake_bundle_dir, "test_" + some_crap)

        self.ue.write_string_to_file(some_crap, some_crap_filename)

        self.assertTrue(path.isfile(some_crap_filename),
                        "Couldn't find %s in container" % some_crap_filename)

        self.ue.subproc(["rm", some_crap_filename])
        # note that we can't read the file, it's owned by app
