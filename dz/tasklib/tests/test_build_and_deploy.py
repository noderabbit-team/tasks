from os import path
from mocker import MockerTestCase

from dz.tasklib import (taskconfig,
                        build_and_deploy)
from dz.tasks import database 
from dz.tasklib.tests.stub_zoomdb import StubZoomDB
from dz.tasklib.tests.dztestcase import DZTestCase

class BuildAndDeployTestcase(DZTestCase):

    def setUp(self):
        self.dir = self.makeDir()
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.dir)

        class MockDBResult(object):
            def __call__(self, app_id):
                self._app_id = app_id
                return self

            def wait(self):
                return (True, "a_db_host", "a_db_name", "a_db_username",
                        "a_db_password")

        self.patch(database.setup_database_for_app, "delay", MockDBResult())

    """
    Test the build and deploy job, which calls out to other subtasks.
    """
    def test_build_and_deploy(self):
        """Invoke the build and deploy task."""
        zoomdb = StubZoomDB()

        app_id = "p001"
        src_url = "git://github.com/shimon/djangotutorial.git"

        here = path.abspath(path.split(__file__)[0])
        app_fixture = path.join(here, 'fixtures', 'app')
        zcfg_fixture = path.join(app_fixture, "zoombuild.cfg")

        zoombuild_cfg_content = file(zcfg_fixture).read()

        # cut out the Django requirement - we don't want to download and
        # upload that!
        zoombuild_cfg_content = zoombuild_cfg_content.replace(
            "pip_reqs: Django==1.2.5", "pip_reqs: ")
        self.assertTrue("Django==" not in zoombuild_cfg_content,
                        "Expected to remove Django version from " +
                        "zoombuild.cfg for test speedup. Contents:\n" +
                        zoombuild_cfg_content)

        build_and_deploy.build_and_deploy(zoomdb, app_id, src_url,
                                          zoombuild_cfg_content)

        zoombuild_cfg_output_filename = path.join(self.dir,
                                                  app_id,
                                                  "zoombuild.cfg")
        self.assertTrue(path.isfile(zoombuild_cfg_output_filename))
        self.assertEqual(file(zoombuild_cfg_output_filename).read(),
                         zoombuild_cfg_content)
