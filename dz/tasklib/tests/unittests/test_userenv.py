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
