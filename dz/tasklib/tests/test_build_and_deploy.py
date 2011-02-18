from os import path
from mocker import MockerTestCase

from dz.tasklib import taskconfig
from dz.tasklib import build_and_deploy
from dz.tasklib.tests.stub_zoomdb import StubZoomDB
from dz.tasklib.tests.dztestcase import DZTestCase

class BuildAndDeployTestcase(DZTestCase):

    def setUp(self):
        self.dir = self.makeDir()
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.dir)

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

        build_and_deploy.build_and_deploy(zoomdb, app_id, src_url,
                                          zoombuild_cfg_content)
        zoombuild_cfg_output_filename = path.join(self.dir,
                                                  app_id,
                                                  "zoombuild.cfg")
        self.assertTrue(path.isfile(zoombuild_cfg_output_filename))
        self.assertEqual(file(zoombuild_cfg_output_filename).read(),
                         zoombuild_cfg_content)
