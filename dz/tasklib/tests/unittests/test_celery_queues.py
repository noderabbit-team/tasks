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

from dz.tasklib.tests import tasks_for_testing

from celery.task import control


def _does_taskmeta_include_date_done():
    """
    Create a celery task, run it and wait for the result, and then indicate
    whether a query for taskmeta includes a "date_done" attribute.
    """
    r = tasks_for_testing.task_a.delay()
    r.wait()  # ignore result
    from celery.backends import default_backend
    taskmeta = default_backend.get_task_meta(r.task_id)
    return "date_done" in taskmeta


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
            "test2": dict(queues=["appserver", "bar", "appserver:bar"]),
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
                # NOTE: if you need to further debug an error, comment out this line
                stdout=file('/dev/null'),
                # Note: don't use subprocess.PIPE above, or when we wait()
                # for celeryd to exit later, it will block because nobody
                # has read stdout. (Or use subprocess.communicate() to
                # actually read that.
                # NOTE: if you need to further debug an error, comment out this line
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
        def _get_hostnames_for_queue(queue):
            return [hostname
                    for (hostname, hostinfo)
                    in CeleryQueuesTestCase.celeryd_hosts.items()
                    if queue in hostinfo["queues"]]

        TASKS_AND_QUEUES = {
            "task_a": dict(func=tasks_for_testing.task_a,
                           queue="build",
                           expected_outcome="a"),
            "task_b": dict(func=tasks_for_testing.task_b,
                           queue="appserver",
                           expected_outcome="b"),
            "task_b_custom": dict(func=tasks_for_testing.task_b,
                                  queue="appserver:bar",
                                  force_queue=True,
                                  expected_outcome="b"),
            }

        for task in TASKS_AND_QUEUES.values():
            if task.get("force_queue", False):
                # force the task to run in a specific queue
                task["result"] = task["func"].apply_async(
                    queue=task["queue"])
            else:
                task["result"] = task["func"].delay()

        for task in TASKS_AND_QUEUES.values():
            task["outcome"] = task["result"].wait()
            self.assertEqual(task["outcome"]["result"],
                             task["expected_outcome"])
            self.assertEqual([task["outcome"]["TEST_CELERYD_NAME"]],
                             _get_hostnames_for_queue(task["queue"]))

    def test_celery_taskmeta_finally_provides_date_done(self):
        """
        Ensure celery does not^H^H^H ACTUALLY DOES, SEE UPDATE 3/6 BELOW
        provide a date_done entry in taskmeta when used with the database
        results backend. This seems to be a bug; see
        https://github.com/ask/celery/issues/issue/325

        UPDATE 2/19/2011: Ask says it was accidentally removed, and has
        committed a fix. Look for this test to fail and the monkeypatch
        become unneccessary in the next Celery release.
        https://github.com/ask/celery/issues/325#comment_789370

        UPDATE 3/6/2011: Celery 2.2.4 appears to include a fix for this
        issue. I'm renaming this function from 
        test_celery_taskmeta_provides_no_date_done
        to
        test_celery_taskmeta_finally_provides_date_done
        and inverting the test logic.
        """
        self.assertTrue(_does_taskmeta_include_date_done())

    def test_celery_taskmeta_monkeypatch(self):
        """
        Test our monkeypatch for getting date_done from celery database
        backend.
        """

        pre_monkey_result = _does_taskmeta_include_date_done()

        import dz.tasks
        dz.tasks.monkey_patch_celery_db_models_Task()

        self.assertTrue(_does_taskmeta_include_date_done())

        dz.tasks.undo_monkey_patch_celery_db_models_Task()

        self.assertEqual(_does_taskmeta_include_date_done(),
                         pre_monkey_result)
