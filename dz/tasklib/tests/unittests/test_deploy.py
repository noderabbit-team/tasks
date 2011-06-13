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
import urllib


def create_test_bundle_in_local_storage():
    """
    Creates a bundle for testing, and uploads it to the local storage.
    Returns the bundle's tarball's name.

    This function is used from test_nginx and perhaps other tests that
    require a bundle -- modify with care.
    """
    print "Making a bundle fixture for testing."
    bundle_name = "bundle_test_deploy_app_2011-fixture"

    here = os.path.abspath(os.path.split(__file__)[0])
    fixture_dir = os.path.join(here, '../fixtures')
    app_name = "test_deploy_app"

    # force rename the bundle
    app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_name)

    if os.path.isdir(app_dir):
        utils.chown_to_me(app_dir)
        shutil.rmtree(app_dir)

    shutil.copytree(os.path.join(fixture_dir, "app"), app_dir)

    zcfg_path = os.path.join(app_dir, "zoombuild.cfg")
    zcfg_content = file(zcfg_path).read()
    # django_tarball = os.path.join(fixture_dir, 'Django-1.2.5.tar.gz')
    # we don't use pip_reqs any more
    # zcfg_content = zcfg_content.replace(
    #     "pip_reqs: Django==1.2.5", "pip_reqs: %s" % django_tarball)

    faster_zcfg = file(zcfg_path, "w")
    faster_zcfg.write(zcfg_content)
    faster_zcfg.close()

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

    return tarball_name


class AbstractDeployTestCase(DZTestCase):
    """
    Abstract base class for test cases that rely on deploying our test bundle.
    """
    def setUp(self):
        self.customer_directory = taskconfig.NR_CUSTOMER_DIR

        self.app_id = "test_deploy_app"
        self.appserver_name = "localhost"
        self.bundle_name = self.__class__.bundle_name
        self.dbinfo = database.DatabaseInfo(host="db-host-001",
                                            db_name="my_app_id",
                                            username="my_app_id",
                                            password="my_app_id_pass")

    def tearDown(self):
        """Ensure the test bundle is no longer served, cleaning up this
        bundle from /etc/supervisor/conf.d."""
        num_stopped = deploy.stop_serving_bundle(self.app_id, self.bundle_name)
        print "tearDown stopped instances: %d" % num_stopped

    @classmethod
    def setUpClass(cls):
        """Ensure the necessary fixtures are installed in the right places."""
        cls.bundle_name = "bundle_test_deploy_app_2011-fixture"
        cls.bundle_fixture = os.path.join(taskconfig.NR_CUSTOMER_DIR,
                                          "bundle_storage_local",
                                          cls.bundle_name + ".tgz")

        if not os.path.isfile(cls.bundle_fixture):
            create_test_bundle_in_local_storage()

    def install_my_bundle(self, **kwargs):
        """
        Convenience function used in several tests.
        """
        return deploy.install_app_bundle(
            self.app_id,
            self.bundle_name,
            self.appserver_name,
            self.dbinfo,
            bundle_storage_engine=bundle_storage_local, **kwargs)


class DeployTestCase(AbstractDeployTestCase):
    """
    Test deployment tasks.
    """

    def test_bundle_fixture_in_local_storage(self):
        """
        Ensure the bundle fixture file exists in local bundle storage.
        """
        self.assertTrue(os.path.isfile(self.__class__.bundle_fixture),
                        "Need a bundle to test deploying - " +
                        "run python dz/tasklib/tests/make_bundle_fixture.py")

    def test_deploy_bundle(self):
        """
        Test the deploy_app_bundle function.
        """
        bundle_dir = os.path.join(self.customer_directory,
                                  self.app_id,
                                  self.bundle_name)

        if os.path.isdir(bundle_dir):
            self.chown_to_me(bundle_dir)
            shutil.rmtree(bundle_dir)

        self.install_my_bundle()
        self.assertTrue(os.path.isdir(bundle_dir))

        for  build_file in ("noderabbit_requirements.txt",
                            "dz_settings.py",
                            "thisbundle.py"):
            self.assertTrue(os.path.isfile(os.path.join(
                        bundle_dir,
                        build_file)),
                            "Couldn't find %s in extracted bundle dir %s." % (
                    build_file, bundle_dir))

        run_in_userenv = os.path.join(taskconfig.PRIVILEGED_PROGRAMS_PATH,
                                      "run_in_userenv")
        thisbundle = os.path.join(bundle_dir, "thisbundle.py")
        main_runner = "sudo %s --custdir=%s -- %s %s" % (
            run_in_userenv,
            taskconfig.NR_CUSTOMER_DIR,
            self.app_id,
            thisbundle)

        #print "---> RUNNABLE! %s <---" % main_runner

        # supress fabric freakout for this test
        import fabric.state
        import fabric.operations
        self.patch(fabric.operations, "warn", lambda msg: None)
        self.patch(fabric.state.env, "warn_only", True)

        def get_managepy_output(cmd):
            # manage.py sends syntax to stdout; list of subcommands to stderr
            return utils.local((cmd + " 2>&1") % (main_runner,))

        #print "RUNNER HELP: %s" % runner_help
        help_output = get_managepy_output("%s help")
        self.assertTrue("runserver" in help_output, help_output)
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
        self.install_my_bundle()

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

    def test_managepy_shell(self):
        """Test running some python code through the manage.py shell."""
        # first ensure bundle has been deployed
        self.install_my_bundle()

        # now check to see that we can run commands
        output = deploy.managepy_shell(self.app_id,
                                       self.bundle_name,
                                       "print 9*9\n")
        self.assertTrue("81" in output, output)

    def test_start_serving_bundle(self):
        """
        Test actually serving a deployed bundle, then taking it down.
        """
        self.install_my_bundle()
        (instance_id, node_name, host_ip, host_port) = \
            deploy.start_serving_bundle(self.app_id, self.bundle_name)

        self.assertTrue(isinstance(instance_id, str))
        self.assertTrue(isinstance(node_name, str))
        self.assertTrue(isinstance(host_ip, str))
        self.assertTrue(isinstance(host_port, int))

        app_url = "http://%s:%d" % (host_ip, host_port)

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
        app_dir, bundle_dir = utils.app_and_bundle_dirs(self.app_id,
                                                        self.bundle_name)
        self.install_my_bundle()
        (instance_id, node_name, host_ip, host_port) = \
            deploy.start_serving_bundle(self.app_id, self.bundle_name)

        self.assertTrue(os.path.isdir(bundle_dir))

        self.check_can_eventually_load(
            "http://%s:%s" % (host_ip, host_port),
            "Welcome to the Django tutorial polls app")

        zoomdb = StubZoomDB()
        zoomdb.add_worker(1, "localhost", "127.0.0.1", host_port)

        self.assertFalse(deploy._is_port_open(host_port))

        deploy.undeploy(zoomdb,
                        self.app_id,
                        None,  # or [1],
                        use_subtasks=False,
                        also_update_proxies=False)

        self.assertTrue(deploy._is_port_open(host_port))
        #self.assertFalse(os.path.isdir(app_dir))
        self.assertFalse(os.path.isdir(bundle_dir))

    def test_undeploy_by_dep_ids(self):
        """
        Test taking down a deployed bundle based on the appserverdeployment id.
        """
        app_dir, bundle_dir = utils.app_and_bundle_dirs(self.app_id,
                                                        self.bundle_name)
        self.install_my_bundle()
        (instance_id, node_name, host_ip, host_port) = \
            deploy.start_serving_bundle(self.app_id, self.bundle_name)

        self.assertTrue(os.path.isdir(bundle_dir))

        self.check_can_eventually_load(
            "http://%s:%s" % (host_ip, host_port),
            "Welcome to the Django tutorial polls app")

        zoomdb = StubZoomDB()
        mydep = zoomdb.add_worker(1, "localhost", "127.0.0.1", host_port)

        self.assertFalse(deploy._is_port_open(host_port))

        deploy.undeploy(zoomdb,
                        self.app_id,
                        dep_ids=[mydep.id],
                        use_subtasks=False,
                        also_update_proxies=False)

        self.assertTrue(deploy._is_port_open(host_port))
        #self.assertFalse(os.path.isdir(app_dir))
        self.assertFalse(os.path.isdir(bundle_dir))

    def test_undeploy_with_proxy_update(self):
        """
        Test taking down a deployed bundle and updating the proxy config too.
        """
        app_dir, bundle_dir = utils.app_and_bundle_dirs(self.app_id,
                                                        self.bundle_name)
        self.install_my_bundle()
        (instance_id, node_name, host_ip, host_port) = \
            deploy.start_serving_bundle(self.app_id, self.bundle_name)

        # also add to nginx - fake it for this test
        here = os.path.abspath(os.path.split(__file__)[0])
        fixture_dir = os.path.join(here, '../fixtures')
        nginx_site_file = os.path.join(taskconfig.NGINX_SITES_ENABLED_DIR,
                                       self.app_id)
        shutil.copyfile(os.path.join(fixture_dir, 'test_deploy_nginx_site'),
                        nginx_site_file)

        self.check_can_eventually_load(
            "http://%s:%s" % (host_ip, host_port),
            "Welcome to the Django tutorial polls app")

        zoomdb = StubZoomDB()
        mydep = zoomdb.add_worker(1, "localhost", "127.0.0.1", host_port)

        self.assertFalse(deploy._is_port_open(host_port))

        zcfg_path = os.path.join(fixture_dir, "app", "zoombuild.cfg")
        zcfg_content = open(zcfg_path).read()

        # make sure we require proper parameters - skip zoombuild_cfg_content
        with self.assertRaises(AssertionError):
            deploy.undeploy(zoomdb,
                            self.app_id,
                            dep_ids=[mydep.id],
                            use_subtasks=False,
                            also_update_proxies=True)

        deploy.undeploy(zoomdb,
                        self.app_id,
                        dep_ids=[mydep.id],
                        use_subtasks=False,
                        also_update_proxies=True,
                        zoombuild_cfg_content=zcfg_content)

        self.assertTrue(deploy._is_port_open(host_port))
        self.assertFalse(os.path.isdir(bundle_dir))
        self.assertFalse(os.path.isfile(nginx_site_file),
                         "Expected nginx site file %s to be gone, but it isn't"
                         % nginx_site_file)

    def test_undeploy_nonexistent(self):
        """
        Test undeploying something that doesn't actually exist.
        """
        with self.assertRaises(utils.InfrastructureException):
            deploy.undeploy_from_appserver(StubZoomDB(), 1, 1,
                                           "localhost", 10001)

    def test_install_num_workers(self):
        """
        Test installing with varying numbers of workers.
        """
        bundle_dir = os.path.join(self.customer_directory,
                                  self.app_id,
                                  self.bundle_name)
        thisbundle = os.path.join(bundle_dir, "thisbundle.py")

        for num_workers in (1, 3, 17, 104):
            self.install_my_bundle(num_workers=num_workers)

            # for testing purposes only, let me read this file:
            utils.chown_to_me(thisbundle)

            thisbundle_content = [x.strip() for x in
                                  open(thisbundle).readlines()]
            self.assertIn('"--workers=%d",' %  num_workers,
                          thisbundle_content)
