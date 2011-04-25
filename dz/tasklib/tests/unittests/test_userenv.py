from dz.tasklib import userenv
from dz.tasklib.tests.dztestcase import DZTestCase
from os import path


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
        self.assertEqual(self.ue.username, self.project_sysid)

    def test_subproc(self):
        self.assertEqual(self.ue.subproc(["whoami"]).strip(),
                         self.ue.username)

    def test_chroot_isolation(self):
        self.assertEqual(self.ue.subproc(["pwd"]).strip(),
                         "/")
        self.assertEqual(sorted(self.ue.subproc(["ls"]).splitlines()),
                         ['bin', 'etc', 'lib', 'lib64', 'usr'])

    def test_subproc_requires_list(self):
        with self.assertRaises(AssertionError):
            self.ue.subproc("echo")

    def test_cleanup(self):
        self.assertTrue(path.isdir(self.ue.container_dir))
        self.ue.destroy()
        self.assertFalse(path.isdir(self.ue.container_dir))

        with self.assertRaises(userenv.AlreadyDestroyed):
            self.ue.destroy()
