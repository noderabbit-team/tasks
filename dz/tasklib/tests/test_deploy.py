from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib import (bundle_storage_local,
                        deploy,
                        taskconfig,
                        utils)

import os
import shutil


class DeployTestCase(DZTestCase):
    """
    Test deployment tasks.
    """

    def setUp(self):
        self.customer_directory = taskconfig.NR_CUSTOMER_DIR

        self.app_id = "app"
        self.appserver_name = "localhost"
        self.bundle_name = "bundle_app_2011-fixture"
        self.db_host = "db-host-001"
        self.db_name = "my_app_id"
        self.db_username = "my_app_id"
        self.db_password = "my_app_id_pass"

    def test_bundle_fixture_in_local_storage(self):
        """
        Ensure the bundle fixture file exists in local bundle storage.
        """
        self.assertTrue(os.path.isfile(
                "/cust/bundle_storage_local/bundle_app_2011-fixture.tgz"),
                        "Need a bundle to test deploying - " +
                        "run python make_bundle_fixture.py")

    def test_deploy_app_bundle(self):
        """
        Test the deploy_app_bundle function.
        """
        bundle_dir = os.path.join(self.customer_directory,
                                  self.app_id,
                                  self.bundle_name)

        if os.path.isdir(bundle_dir):
            shutil.rmtree(bundle_dir)

        r = deploy.deploy_app_bundle(
            self.app_id,
            self.bundle_name,
            self.appserver_name,
            self.db_host, self.db_name,
            self.db_username, self.db_password,
            bundle_storage_engine=bundle_storage_local)
        self.assertTrue(isinstance(r, str))
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
                                     self.db_host, self.db_name,
                                     self.db_username, self.db_password)

    # COMING SOON:
    # def test_generate_supervisor_conf_file(self):
    # def test reload_supervisord(self):

    def test_manage_cmd(self):
        """Test running a non-interactive manage.py command on a bundle."""

        # first ensure bundle has been deployed
        deploy.deploy_app_bundle(
            self.app_id,
            self.bundle_name,
            self.appserver_name,
            self.db_host, self.db_name,
            self.db_username, self.db_password,
            bundle_storage_engine=bundle_storage_local)

        # now check to see that we can run commands
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
