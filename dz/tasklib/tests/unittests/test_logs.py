import glob
import os

from nose.plugins.skip import SkipTest

from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib import (logs,
                        taskconfig)


class LogsTestCase(DZTestCase):
    """
    Test logging.
    """

    def setUp(self):
        self.app_id = "test001"

    def test_get_no_logs(self):
        log_list = logs.get_available_logs("nonexistentapp")
        self.assertEqual(len(log_list), 0)

    def _ensure_test_logs_exist(self):
        if not len(glob.glob(os.path.join(
            taskconfig.LOG_DIR_SUPERVISOR,
            "bundle_%s_*.log" % self.app_id))):
            raise SkipTest("Please run a build_and_deploy test using app id "
                           "%s before looking for logs." % self.app_id)

    def test_logs_present(self):
        self._ensure_test_logs_exist()

        log_list = logs.get_available_logs(self.app_id)

        self.assertTrue("Application Standard Output"
                        in l[1] for l in log_list)
        self.assertTrue("Application Standard Error"
                        in l[1] for l in log_list)
        self.assertTrue("Web Server Access Log"
                        in l[1] for l in log_list)

    def test_getting_log_content(self):
        self._ensure_test_logs_exist()

        log_list = logs.get_available_logs(self.app_id)
        self.assertTrue(len(log_list) > 0)

        for filename, caption, filesize in log_list:
            print "LOG: %s: %s, %d bytes" % (caption, filename, filesize)
