from dz.tasklib import userenv
from dz.tasklib.tests.dztestcase import DZTestCase
from os import path
import random


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
        self.assertEqual(self.ue.subproc(["whoami"]).strip(),
                         self.ue.username)

    def test_subproc_nonzero(self):
        """Test that a failed subprocess causes an exception to be raised."""
        with self.assertRaises(userenv.ErrorInsideEnvironment):
            self.ue.subproc(["cat", "/nonexistent"])

    def test_chroot_isolation(self):
        """Test that only a limited set of directories are available thanks
        to chroot."""
        self.assertEqual(self.ue.subproc(["pwd"]).strip(),
                         "/")
        self.assertEqual(sorted(self.ue.subproc(["ls"]).splitlines()),
                         ['bin', 'etc', 'lib', 'lib64', 'usr'])

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
        file_content = self.ue.subproc(["cat", filename])
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
        file_content = self.ue.subproc(["cat", filename])
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
