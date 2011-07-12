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
        log_list = list(logs.get_available_logs("nonexistentapp"))
        self.assertEqual(len(log_list), 0)

    def _ensure_test_logs_exist(self):
        glob_expr = os.path.join(
            taskconfig.LOG_DIR_SUPERVISOR,
            "bundle_%s_*---supervisor-*.log" % self.app_id)
        if not len(glob.glob(glob_expr)):
            raise SkipTest("Please run a build_and_deploy test using app id "
                           "%s before looking for logs. (Looking for %s.)" % (
                               self.app_id,
                               glob_expr))

    def test_logs_present(self):
        self._ensure_test_logs_exist()

        log_list = list(logs.get_available_logs(self.app_id))

        for expected_caption in ("Application Standard Output",
                                 "Application Standard Error",
                                 "Web Server Access Log"):
            self.assertTrue(expected_caption in l["caption"] for l in log_list)

    def test_getting_log_content(self):
        self._ensure_test_logs_exist()

        log_list = list(logs.get_available_logs(self.app_id))
        self.assertTrue(len(log_list) > 0, log_list)

        for loginfo in log_list:
            log_id = loginfo["log_id"]
            caption = loginfo["caption"]
            filesize = loginfo["filesize"]
            mod_time = loginfo["mod_time"]

            self.assertTrue(isinstance(mod_time, float))

            print "LOG: %s: %s, %d bytes" % (caption, log_id, filesize)

            content = logs.get_log_content(self.app_id, log_id)
            self.assertTrue(isinstance(content, str), content)

    def test_getting_wrong_log_content(self):
        with self.assertRaises(logs.UnavailableLogError):
            logs.get_log_content(self.app_id, "/etc/passwd")
