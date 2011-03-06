from os import path
import os
import urllib
import httplib

from dz.tasklib import (build_and_deploy,
                        bundle_storage_local,
                        database,
                        deploy,
                        taskconfig,
                        utils)
from dz.tasklib.tests.stub_zoomdb import StubZoomDB
from dz.tasklib.tests.dztestcase import DZTestCase


class BuildAndDeployTestcase(DZTestCase):
    """
    Test the build and deploy job, which calls out to other subtasks.
    """

    def setUp(self):
        self.dir = self.makeDir()
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.dir)
        self.app_id = "test001"

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

        deployed_addresses = build_and_deploy.build_and_deploy(
            zoomdb, self.app_id, src_url,
            zoombuild_cfg_content,
            use_subtasks=False,
            bundle_storage_engine=bundle_storage_local,
            )

        # # call the tasks module directly instead, so we get that tested too.
        # # actually this doesn't work because of the decorator; doh!
        # deployed_addresses = builder.build_and_deploy(zoomdb._job_id, zoomdb,
        #         {
        #         "app_id": self.app_id,
        #         "src_url": src_url,
        #         "zoombuild_cfg_content": zoombuild_cfg_content,
        #         })

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
        site_nginx_conf_file = os.path.join(taskconfig.NGINX_SITES_ENABLED_DIR,
                                            self.app_id)
        self.assertTrue(os.path.isfile(site_nginx_conf_file),
                        "expected to find a config file in nginx's "
                        "sites-enabled directory, but didn't")

        # check the deployed app!
        self.assertEqual(len(deployed_addresses), 1)

        for appserver_host, appserver_port in deployed_addresses:
            polls_url = "http://%s:%d/polls/" % (appserver_host,
                                                 appserver_port)
            polls_src = urllib.urlopen(polls_url).read()
            self.assertTrue("No polls are available." in polls_src)

        # now check the nginx service
        host = zoomdb.get_project_virtual_hosts()[0]

        def get_via_nginx():
            conn = httplib.HTTPConnection("127.0.0.1")
            conn.putrequest("GET", "/polls/", skip_host=True)
            conn.putheader("Host", host)
            conn.endheaders()
            res = conn.getresponse()
            res_src = res.read()
            return res_src

        page_src = get_via_nginx()
        self.assertTrue("No polls are available." in page_src,
                        "Couldn't find polls text in "
                        "page src (%r)." % page_src)

        # OK, now undeploy.
        deploy.undeploy(zoomdb, self.app_id, bundle_ids=None,
                        use_subtasks=False)

        # check that URLs are no longer accessible
        for appserver_host, appserver_port in deployed_addresses:
            polls_url = "http://%s:%d/polls/" % (appserver_host,
                                                 appserver_port)
            with self.assertRaises(IOError):
                urllib.urlopen(polls_url).read()

        # check that Nginx conf file is gone
        self.assertFalse(os.path.isfile(site_nginx_conf_file),
                        "expected nginx config file gone")

        # check that supervisor files are gone
        for fname in os.listdir(taskconfig.SUPERVISOR_APP_CONF_DIR):
            self.assertFalse(fname.startswith("%s." % self.app_id),
                             "There is a lingering supervisor config "
                             "file: %s" % fname)

        # check that DB still exists though
        dblist = utils.local("psql -l -U nrweb | awk '{print $1}'")
        self.assertTrue(self.app_id in dblist.splitlines())

        # DB and dbuser will be deleted in tearDown().
