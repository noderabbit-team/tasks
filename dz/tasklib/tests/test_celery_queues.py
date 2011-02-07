"""
Test enqueuing tasks in celery and routing them to the right celeryd.

To run a celeryd for testing:
CELERY_CONFIG_MODULE=celeryconfig_testing celeryd -l info
"""

import unittest
import os
import subprocess
import time

os.environ["CELERY_CONFIG_MODULE"] = "celeryconfig_testing"

import tasks_for_testing


class CeleryQueuesTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print "Starting celeryd..."
        cls.celeryd = subprocess.Popen(['celeryd', '-l', 'info'],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
        print "celeryd started; pid=%d" % cls.celeryd.pid

    @classmethod
    def tearDownClass(cls):
        print "Killing celeryd..."
        cls.celeryd.terminate()
        print "sent TERM signal..."
        cls.celeryd.wait()
        print "celeryd killed."

    def test_enqueue_task(self):
        """
        Ensure I can connect to celeryd to enqueue tasks.
        """
        tasks_for_testing.task_a.delay()

    def test_waiting_result(self):
        """
        Ensure I get a proper result from a task when waiting for it.
        """
        r = tasks_for_testing.task_a.apply()
        self.assertEqual(r.result, "a")

    def test_async_result(self):
        """
        Ensure I get a proper result for a task and it executes asynchronously.
        """
        delayed_result = tasks_for_testing.task_a.delay()
        i = 0

        while not delayed_result.ready():
            i += 1
            time.sleep(1)
            self.assertTrue(i < 10)  # this better not take too long

        self.assertEqual(delayed_result.result, "a")
        self.assertTrue(i > 0)

    # def test_enqueue_task_into_queue(self):
    #     t = _maketask(queue=
