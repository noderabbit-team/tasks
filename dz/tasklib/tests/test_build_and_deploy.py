from os import path

from dz.tasklib import (taskconfig,
                        build_and_deploy,
                        bundle_storage_local)
from dz.tasks import database
from dz.tasklib.tests.stub_zoomdb import StubZoomDB
from dz.tasklib.tests.dztestcase import DZTestCase


class BuildAndDeployTestcase(DZTestCase):
    """
    Test the build and deploy job, which calls out to other subtasks.
    """

    def setUp(self):
        self.dir = self.makeDir()
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.dir)

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

        build_and_deploy.build_and_deploy(
            zoomdb, app_id, src_url,
            zoombuild_cfg_content,
            use_subtasks=False,
            bundle_storage_engine=bundle_storage_local,
            post_build_hooks=[])

        zoombuild_cfg_output_filename = path.join(self.dir,
                                                  app_id,
                                                  "zoombuild.cfg")
        self.assertTrue(path.isfile(zoombuild_cfg_output_filename))
        self.assertEqual(file(zoombuild_cfg_output_filename).read(),
                         zoombuild_cfg_content)

        p = zoomdb.get_project()

        for attr in ("db_host", "db_name", "db_username", "db_password",
                     "is_flushed"):
            print "project.%s = %s" % (attr, getattr(p, attr))
            self.assertTrue(getattr(p, attr))

        # TODO: More stuff to test:
        # - we get an accurate port # or URL back
        # - deployment info is logged into DB
        # - database creds are logged into DB
        # - app actually loads (should be doable once database creds happen)
        # - tear down app (so we don't pollute /etc/supervisor/conf.d with
        #                  stuff that doesn't even exist anymore)
