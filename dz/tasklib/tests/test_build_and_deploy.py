from os import path
import urllib

from dz.tasklib import (taskconfig,
                        build_and_deploy,
                        database,
                        bundle_storage_local)
from dz.tasklib.tests.stub_zoomdb import StubZoomDB
from dz.tasklib.tests.dztestcase import DZTestCase


class BuildAndDeployTestcase(DZTestCase):
    """
    Test the build and deploy job, which calls out to other subtasks.
    """

    def setUp(self):
        self.dir = self.makeDir()
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.dir)
        self.app_id = "p001"

    def tearDown(self):
        # TODO: instead of just manually throwing away DB stuff, add a
        # destroy_project_data function that could be user-accessible in
        # case a user ever wants to throw away their DB and start over.
        database.drop_database(self.app_id)
        database.drop_user(self.app_id)

    def test_build_and_deploy(self):
        """Invoke the build and deploy task."""
        zoomdb = StubZoomDB()

        src_url = "git://github.com/shimon/djangotutorial.git"

        here = path.abspath(path.split(__file__)[0])
        app_fixture = path.join(here, 'fixtures', 'app')
        django_tarball = path.join(here, 'fixtures', 'Django-1.2.5.tar.gz')
        zcfg_fixture = path.join(app_fixture, "zoombuild.cfg")

        zoombuild_cfg_content = file(zcfg_fixture).read()

        # cut out the Django requirement - we don't want to download and
        # upload that!
        zoombuild_cfg_content = zoombuild_cfg_content.replace(
            "pip_reqs: Django==1.2.5", "pip_reqs: %s" % django_tarball)
        self.assertTrue("Django==" not in zoombuild_cfg_content,
                        "Expected to remove Django version from " +
                        "zoombuild.cfg for test speedup. Contents:\n" +
                        zoombuild_cfg_content)

        self.assertFalse(zoomdb.is_flushed)
        self.assertEqual(len(zoomdb.get_all_bundles()), 0)
        self.assertEqual(len(zoomdb.get_project_workers()), 0)

        # Note: if you get a database-related utils.InfrastructureError
        # on the below, you might have a lingering test DB or user. Remove
        # it by running:
        # dropdb -U nrweb p001; dropuser -U nrweb p001;

        deployed_addresses = build_and_deploy.build_and_deploy(
            zoomdb, self.app_id, src_url,
            zoombuild_cfg_content,
            use_subtasks=False,
            bundle_storage_engine=bundle_storage_local,
            #post_build_hooks=[]
            )

        zoombuild_cfg_output_filename = path.join(self.dir,
                                                  self.app_id,
                                                  "zoombuild.cfg")
        self.assertTrue(path.isfile(zoombuild_cfg_output_filename))
        self.assertEqual(file(zoombuild_cfg_output_filename).read(),
                         zoombuild_cfg_content)

        p = zoomdb.get_project()

        for attr in ("db_host", "db_name", "db_username", "db_password"):
            print "project.%s = %s" % (attr, getattr(p, attr))
            self.assertTrue(getattr(p, attr))

        self.assertTrue(zoomdb.is_flushed)
        self.assertEqual(len(zoomdb.get_all_bundles()), 1)
        self.assertEqual(len(zoomdb.get_project_workers()), 1)

        # check the deployed app!
        self.assertEqual(len(deployed_addresses), 1)

        appserver_host, appserver_port = deployed_addresses[0]
        polls_src = urllib.urlopen(
            "http://%s:%d/polls/" % (appserver_host, appserver_port)).read()
        self.assertTrue("No polls are available." in polls_src)

        # TODO: More stuff to test:
        # - we get an accurate port # or URL back
        # - deployment info is logged into DB
        # - database creds are logged into DB
        # - app actually loads (should be doable once database creds happen)
        # - tear down app (so we don't pollute /etc/supervisor/conf.d with
        #                  stuff that doesn't even exist anymore)
        #   - remove supervisor conf.d entry
        #   - remove postgres database and user
