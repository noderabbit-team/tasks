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
                            "deployment_%s.py" % self.appserver_name):
            self.assertTrue(os.path.isfile(os.path.join(
                        bundle_dir,
                        build_file)),
                            "Couldn't find %s in extracted bundle dir %s." % (
                    build_file, bundle_dir))

        print "---> RUNNABLE! %s <---" % os.path.join(
            bundle_dir,
            "deployment_%s.py" % self.appserver_name)
        #import ipdb;ipdb.set_trace()

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
