from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib import (deploy,
                        taskconfig,
                        utils)

import os

class DeployTestCase(DZTestCase):
    """
    Test deployment tasks.
    """

    def setUp(self):

        self.customer_directory = self.makeDir()
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.customer_directory)

        self.app_id = "my_app_id"
        self.appserver_name = "localhost"
        self.bundle_name = "bundle_my_app_id_20110222-01"
        self.db_host = "db-host-001"
        self.db_name = "my_app_id"
        self.db_username = "my_app_id"
        self.db_password = "my_app_id_pass"

    def test_deploy_app_bundle(self):
        """
        Test the deploy_app_bundle function.
        """

        bundle_dir = os.path.join(self.customer_directory,
                                  self.app_id,
                                  self.bundle_name)

        self.assertFalse(os.path.isdir(bundle_dir))

        r = deploy.deploy_app_bundle(self.app_id,
                                     self.bundle_name,
                                     self.appserver_name,
                                     self.db_host, self.db_name,
                                     self.db_username, self.db_password)
        self.assertTrue(isinstance(r, str))
        #self.assertTrue(os.path.isdir(bundle_dir))

    def test_deploy_to_wrong_server_fails(self):
        """
        Ensure that all hell breaks loose if a deploy gets routed to the
        wrong server.
        """

        def bogus_deploy():
            deploy.deploy_app_bundle(self.app_id,
                                     self.bundle_name,
                                     "BOGUS" + self.appserver_name,
                                     self.db_host, self.db_name,
                                     self.db_username, self.db_password)

        self.assertRaises(utils.InfrastructureException, bogus_deploy)
