from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib import (bundle,
                        bundle_storage_local,
                        database,
                        deploy,
                        taskconfig,
                        utils)

from dz.tasklib.tests.stub_zoomdb import StubZoomDB

import os
import shutil
import time
import urllib


class DeployTestCase(DZTestCase):
    """
    Test deployment tasks.
    """

    def setUp(self):
        self.customer_directory = taskconfig.NR_CUSTOMER_DIR

        self.app_id = "test_deploy_app"
        self.appserver_name = "localhost"
        self.bundle_name = "bundle_app_2011-fixture"
        self.dbinfo = database.DatabaseInfo(host="db-host-001",
                                            db_name="my_app_id",
                                            username="my_app_id",
                                            password="my_app_id_pass")

    @classmethod
    def setUpClass(cls):
        """Ensure the necessary fixtures are installed in the right places."""
        bundle_name = "bundle_app_2011-fixture"
        cls.bundle_fixture = os.path.join(taskconfig.NR_CUSTOMER_DIR,
                                          "bundle_storage_local",
                                          bundle_name + ".tgz")

        if not os.path.isfile(cls.bundle_fixture):
            print "Making a bundle fixture for testing."

            here = os.path.abspath(os.path.split(__file__)[0])
            fixture_dir = os.path.join(here, 'fixtures')
            app_name = "app"

            # force rename the bundle
            app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_name)

            if os.path.isdir(app_dir):
                shutil.rmtree(app_dir)

            shutil.copytree(os.path.join(fixture_dir, app_name),
                            app_dir)
            bundle_name, code_revision = bundle.bundle_app(
                app_name,
                force_bundle_name=bundle_name)

            bundle_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR,
                                      app_name,
                                      bundle_name)

            tarball_name = bundle.zip_and_upload_bundle(app_name,
                                                        bundle_name,
                                                        bundle_storage_local)

            print "Created bundle fixture in %s" % tarball_name

            # after upload, delete the dir where bundle was created
            shutil.rmtree(bundle_dir)

    def check_can_eventually_load(self, url, pagetext_fragment):
        """
        Check that the given URL can be loaded, within a reasonable number
        of attempts, and that pagetext_fragment appears in the response.
        """
        load_attempts = 0

        while True:
            if load_attempts >= 10:
                self.fail("Could not load URL %s after %d attempts." % (
                        url,
                        load_attempts))
            try:
                pagetext = urllib.urlopen(url).read()
                self.assertTrue(pagetext_fragment in pagetext)
                break
            except Exception, e:
                load_attempts += 1
                print "[attempt %d] Couldn't load %s: %s" % (
                    load_attempts, url, str(e))
                time.sleep(0.25)

    def test_bundle_fixture_in_local_storage(self):
        """
        Ensure the bundle fixture file exists in local bundle storage.
        """
        self.assertTrue(os.path.isfile(self.__class__.bundle_fixture),
                        "Need a bundle to test deploying - " +
                        "run python dz/tasklib/tests/make_bundle_fixture.py")

    def _install_my_bundle(self):
        """
        Convenience function used in several tests.
        """
        return deploy.install_app_bundle(
            self.app_id,
            self.bundle_name,
            self.appserver_name,
            self.dbinfo,
            bundle_storage_engine=bundle_storage_local)

    def test_deploy_and_undeploy(self):
        """
        Test the deploy_app_bundle function.
        """
        bundle_dir = os.path.join(self.customer_directory,
                                  self.app_id,
                                  self.bundle_name)

        if os.path.isdir(bundle_dir):
            shutil.rmtree(bundle_dir)

        self._install_my_bundle()
        self.assertTrue(os.path.isdir(bundle_dir))

        for  build_file in ("noderabbit_requirements.txt",
                            "dz_settings.py",
                            "thisbundle.py"):
            self.assertTrue(os.path.isfile(os.path.join(
                        bundle_dir,
                        build_file)),
                            "Couldn't find %s in extracted bundle dir %s." % (
                    build_file, bundle_dir))

        main_runner = os.path.join(bundle_dir, "thisbundle.py")

        print "---> RUNNABLE! %s <---" % main_runner

        # supress fabric freakout for this test
        import fabric.state
        import fabric.operations
        self.patch(fabric.operations, "warn", lambda msg: None)
        self.patch(fabric.state.env, "warn_only", True)

        def get_managepy_output(cmd):
            # manage.py sends syntax to stdout; list of subcommands to stderr
            return utils.local((cmd + " 2>&1") % (main_runner,))

        #print "RUNNER HELP: %s" % runner_help
        self.assertTrue("runserver" in get_managepy_output("%s help"))
        try_installed_apps = get_managepy_output(
            'echo "import settings; ' +
            '[ __import__(a) for a in settings.INSTALLED_APPS ]" | ' +
            '%s shell --plain')
        self.assertTrue("<module 'polls' from " in try_installed_apps)
        self.assertTrue("error" not in try_installed_apps.lower())

    def test_deploy_to_wrong_server_fails(self):
        """
        Ensure that all hell breaks loose if a deploy gets routed to the
        wrong server.
        """

        with self.assertRaises(utils.InfrastructureException):
            deploy.deploy_app_bundle(self.app_id,
                                     self.bundle_name,
                                     "BOGUS" + self.appserver_name,
                                     self.dbinfo)

    def test_managepy_cmd(self):
        """Test running a non-interactive manage.py command on a bundle."""

        # first ensure bundle has been deployed
        self._install_my_bundle()

        # now check to see that we can run commands
        diffsettings = deploy.managepy_command(self.app_id,
                                               self.bundle_name,
                                               "diffsettings")
        self.assertTrue(("DATABASE_HOST = '%s'" % self.dbinfo.host)
                        in diffsettings)

        # Ensure "help" command raises a RuntimeError (nonzero exit status)
        try:
            deploy.managepy_command(self.app_id, self.bundle_name, "help")
        except RuntimeError, e:  # expect a RuntimeError as "manage.py help"
                                 # should return nonzero exit status
            self.assertTrue("runserver" in e.message)
            self.assertTrue("Nonzero return code 1 from manage.py help"
                            in e.message)
        else:
            self.fail("I expected a RuntimeError to be raised from " +
                      "manage.py help, but didn't get one!")

    def test_start_serving_bundle(self):
        """
        Test actually serving a deployed bundle, then taking it down.
        """
        self._install_my_bundle()
        port = deploy.start_serving_bundle(self.app_id, self.bundle_name)

        self.assertTrue(isinstance(port, int))

        app_url = "http://localhost:%d" % port

        self.check_can_eventually_load(
            app_url,
            "Welcome to the Django tutorial polls app")

        # we shouldn't be able to serve the same bundle again from this
        # appserver
        with self.assertRaises(utils.InfrastructureException):
            deploy.start_serving_bundle(self.app_id, self.bundle_name)

        num_stopped = deploy.stop_serving_bundle(self.app_id, self.bundle_name)

        self.assertEqual(num_stopped, 1)

        with self.assertRaises(IOError):
            urllib.urlopen(app_url).read()

    def test_is_port_open(self):
        """
        Test our portscanner.
        """
        print "Testing ports..."
        for p in xrange(taskconfig.APP_SERVICE_START_PORT + 100,
                        taskconfig.APP_SERVICE_START_PORT + 200):
            is_open = deploy._is_port_open(p)
            #print "testing port %d: %s\r" % (p, is_open),
            self.assertTrue(is_open)

        # anything below 1024 is root only, so it should fail.
        # port 22 is SSH, so it should almost certainly fail.
        self.assertFalse(deploy._is_port_open(22))

    def test_undeploy(self):
        """
        Test taking down a deployed bundle.
        """
        self._install_my_bundle()
        port = deploy.start_serving_bundle(self.app_id, self.bundle_name)

        self.check_can_eventually_load(
            "http://localhost:%s" % port,
            "Welcome to the Django tutorial polls app")

        zoomdb = StubZoomDB()
        zoomdb.add_worker(1, "localhost", "127.0.0.1", port)

        self.assertFalse(deploy._is_port_open(port))

        deploy.undeploy(zoomdb,
                        self.app_id,
                        None,  # or [1],
                        use_subtasks=False)

        self.assertTrue(deploy._is_port_open(port))
