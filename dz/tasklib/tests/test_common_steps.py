from dz.tasklib import (taskconfig,
                        utils,
                        common_steps)

from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib.tests.stub_zoomdb import StubZoomDB


class CommonStepsTestCase(DZTestCase):
    def setUp(self):
        self.cust_dir = self.makeDir()
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.cust_dir)
        self.zoomdb = StubZoomDB()
        self.opts = {
            "CO_DIR": self.makeDir(dirname=self.cust_dir),
            }

    def test_checking_out_bad_repo(self):
        """
        Test attempting to checkout an invalid URL.
        """

        with self.assertRaises(utils.ProjectConfigurationException):
            self.opts["SRC_URL"] = "fake url"
            common_steps.checkout_code(self.zoomdb, self.opts)
