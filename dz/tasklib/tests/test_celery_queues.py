"""
Test enqueuing tasks in celery and routing them to the right celeryd. These
tests will bring up multiple celeryd processes; you shouldn't have any
others talking to the same AMQP backend if you want these to pass.
"""

import unittest
import os
import subprocess
import time
import sys

os.environ["CELERY_CONFIG_MODULE"] = "celeryconfig_testing"

import tasks_for_testing

from celery.task import control


class CeleryQueuesTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Bring up celeryd processes as required to run tests.
        """

        p = subprocess.Popen(['pgrep', 'celeryd'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        output, errors = p.communicate()
        if len(output):
            print "It looks like an instance of celeryd is already running",
            print "locally. You should kill it before attempting to run",
            print "the celery queues test suite, which assumes no other",
            print "concurrent celeryd processes."
            sys.exit()

        print "Starting celeryd..."
        cls.celeryd_hosts = {
            "test1": dict(queues=["foo", "build"]),
            "test2": dict(queues=["appserver", "bar"]),
            }

        for hostname, hostinfo in cls.celeryd_hosts.items():
            args = ['celeryd',
                    '-l', 'info',
                    '--hostname', hostname,
                    '-Q', ",".join(hostinfo["queues"]),
                    ]
            env = dict(os.environ)
            env.update({"TEST_CELERYD_NAME": hostname})
            hostinfo["Popen"] = subprocess.Popen(
                args,
                stdout=file('/dev/null'),
                # Note: don't use subprocess.PIPE above, or when we wait()
                # for celeryd to exit later, it will block because nobody
                # has read stdout. (Or use subprocess.communicate() to
                # actually read that.
                stderr=subprocess.STDOUT,
                env=env)
            print "celeryd [%s] started; pid=%d" % (
                " ".join(args), hostinfo["Popen"].pid)

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

    def test_sync_result(self):
        """
        Ensure I get a proper result from a task when waiting for it.
        """
        r = tasks_for_testing.task_a.apply()
        self.assertEqual(r.result["result"], "a")

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

        self.assertEqual(delayed_result.result["result"], "a")
        self.assertTrue(i > 0)

    def test_wait_result(self):
        """
        Ensure I get a proper result from an async task when wait()ing for it.
        """
        r = tasks_for_testing.task_a.delay()
        res = r.wait()
        self.assertEqual(res["result"], "a")

    def test_queue_routing(self):
        """
        Test that tasks are routed properly by queue.
        """
        build_queue_result = tasks_for_testing.task_a.delay()
        build_outcome = build_queue_result.wait()

        appserver_queue_result = tasks_for_testing.task_b.delay()
        appserver_outcome = appserver_queue_result.wait()

        self.assertEqual(build_outcome["result"], "a")

        def _get_hostnames_for_queue(queue):
            return [hostname
                    for (hostname, hostinfo)
                    in CeleryQueuesTestCase.celeryd_hosts.items()
                    if queue in hostinfo["queues"]]

        build_hostnames = _get_hostnames_for_queue("build")
        appserver_hostnames = _get_hostnames_for_queue("appserver")

        self.assertEqual([build_outcome["TEST_CELERYD_NAME"]],
                         build_hostnames)
        self.assertEqual([appserver_outcome["TEST_CELERYD_NAME"]],
                         appserver_hostnames)
