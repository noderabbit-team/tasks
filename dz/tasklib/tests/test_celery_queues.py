"""
Test enqueuing tasks in celery and routing them to the right celeryd. These
tests will bring up multiple celeryd processes; you shouldn't have any
others talking to the same AMQP backend if you want these to pass.
"""

import unittest
import os
import subprocess
import time

os.environ["CELERY_CONFIG_MODULE"] = "celeryconfig_testing"

import tasks_for_testing

from celery.task import control


class CeleryQueuesTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Bring up celeryd processes as required to run tests.
        """

        print "Starting celeryd..."
        cls.celeryd_hosts = {
            "test1": dict(queues=["build", "all_servers"]),
            "test2": dict(queues=["all_servers"]),
            }

        for hostname, hostinfo in cls.celeryd_hosts.items():
            hostinfo["Popen"] = subprocess.Popen(
                ['celeryd',
                 '-l', 'info',
                 '--hostname', hostname,
                 '-Q', ",".join(hostinfo["queues"]),
                 ],
                stdout=file('/dev/null'),
                # Note: don't use subprocess.PIPE above, or when we wait()
                # for celeryd to exit later, it will block because nobody
                # has read stdout. (Or use subprocess.communicate() to
                # actually read that.
                stderr=subprocess.STDOUT)
            print "celeryd [%s] started; pid=%d" % (
                hostname, hostinfo["Popen"].pid)

    @classmethod
    def tearDownClass(cls):
        """
        Shut down the celeryd processes we created earlier.
        """
        for hostname, hostinfo in cls.celeryd_hosts.items():
            print "Requesting shutdown of celeryd [%s]..." % hostname
            control.broadcast("shutdown", destination=[hostname])
            cls.celeryd_hosts[hostname]["Popen"].wait()
            print "celeryd closed."

    def test_celeries_running(self):
        """
        Ensure the expected number of celeryd instances are running.
        """
        pongs = control.ping()
        self.assertEqual(len(pongs), len(CeleryQueuesTestCase.celeryd_hosts),
                         "Number of hosts responding to ping should match " +
                         "number of test hosts.")

        for pong in pongs:
            for hostname in pong.keys():
                self.assertTrue(hostname in CeleryQueuesTestCase.celeryd_hosts)

    def test_celeries_tasks_registered(self):
        """
        Ensure all test tasks are registered with each celeryd.
        """
        test_task_names = [funcname for funcname in dir(tasks_for_testing)
                            if funcname.startswith("task_")]
        test_task_names.sort()

        for hostname, hostinfo in CeleryQueuesTestCase.celeryd_hosts.items():
            i = control.inspect([hostname])
            host_task_names = [h for h in i.registered_tasks()[hostname]
                               if not h.startswith("celery.")]
            host_task_names.sort()
            self.assertEqual(test_task_names, host_task_names)

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
