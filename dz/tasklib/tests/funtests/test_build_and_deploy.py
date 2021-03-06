from os import path
import os
import urllib
from psycopg2 import ProgrammingError

from dz.tasklib import (build_and_deploy,
                        bundle_storage_local,
                        database,
                        deploy,
                        taskconfig,
                        utils)
from dz.tasklib.tests.stub_zoomdb import StubZoomDB
from dz.tasklib.tests.dztestcase import DZTestCase, requires_internet


class BuildAndDeployTestcase(DZTestCase):
    """
    Test the build and deploy job, which calls out to other subtasks.
    """

    def setUp(self):
        self.dir = self.makeDir(prefix="test_build_dep_cust_")
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.dir)
        self.app_id = "test001"

    def tearDown(self):
        # TODO: instead of just manually throwing away DB stuff, add a
        # destroy_project_data function that could be user-accessible in
        # case a user ever wants to throw away their DB and start over.
        try:
            database.drop_database(self.app_id)
            database.drop_user(self.app_id)
        except ProgrammingError:  # probably indicates DB/user doesn't exist
            pass

        # chown cust dir to me so we can delete it
        utils.chown_to_me(self.dir)

        # delete any lingering supervisor conf files
        utils.local("rm -f %s/%s*" % (taskconfig.SUPERVISOR_APP_CONF_DIR,
                                      self.app_id))

    @requires_internet
    def test_build_and_deploy(self):
        """Invoke the build and deploy task."""
        zoomdb = StubZoomDB()

        src_repo_type = "git"
        src_url = "git://github.com/shimon/djangotutorial.git"

        here = path.abspath(path.split(__file__)[0])
        app_fixture = path.join(here, '../fixtures', 'app')
        zcfg_fixture = path.join(app_fixture, "zoombuild.cfg")

        zoombuild_cfg_content = file(zcfg_fixture).read()

        self.assertFalse(zoomdb.is_flushed)
        self.assertEqual(len(zoomdb.get_all_bundles()), 0)
        self.assertEqual(len(zoomdb.get_project_workers()), 0)

        self.assertEqual(len(zoomdb.get_project_virtual_hosts()), 1)
        zoomdb.test_vhosts = ["awesomesite.com", "foo.co.br"]
        self.assertEqual(len(zoomdb.get_project_virtual_hosts()), 3)

        deployed_addresses = build_and_deploy.build_and_deploy(
            zoomdb, self.app_id, src_repo_type, src_url,
            zoombuild_cfg_content,
            use_subtasks=False,
            bundle_storage_engine=bundle_storage_local,
            )

        print "build_and_deploy returned: %r" % deployed_addresses

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

        for (instance_id, node_name, host_ip, host_port) in deployed_addresses:
            polls_url = "http://%s:%d/polls/" % (host_ip,
                                                 host_port)
            print "Testing Polls URL: %s" % polls_url
            polls_src = urllib.urlopen(polls_url).read()
            self.assertTrue("No polls are available." in polls_src)

        # now check the nginx service
        hosts = zoomdb.get_project_virtual_hosts()

        # ensure each hostname works!
        for host in hosts:
            #GZIP DEBUG# import ipdb; ipdb.set_trace()
            
            self.check_can_eventually_load_custom("127.0.0.1",
                                                  "/polls/",
                                                  host,
                                                  "No polls are available.")

        # for nginx to serve static files, the cust dir has to be
        # world-read/executable. This should be the default on the
        # proxy server ONLY.
        os.chmod(self.dir, 0755)

        image_src = self.check_can_eventually_load_custom(
            "127.0.0.1",
            "/static/img/polls.jpg",
            hosts[0])
        local_image_file = os.path.join(app_fixture,
                                        "src", "static", "polls.jpg")
        self.assertEqual(image_src, open(local_image_file).read())

        # try a collectstatic-handled file
        collectstatic_src = self.check_can_eventually_load_custom(
            "127.0.0.1",
            "/staticfiles/polls/Lineup.jpg",
            hosts[0])
        local_collectstatic_file = os.path.join(app_fixture,
                                                "src",
                                                "polls",
                                                "static",
                                                "polls",
                                                "Lineup.jpg")
        self.assertEqual(collectstatic_src,
                         open(local_collectstatic_file).read())

        # OK, now undeploy.
        deploy.undeploy(zoomdb, self.app_id, bundle_ids=None,
                        use_subtasks=False)

        # check that URLs are no longer accessible
        for (instance_id, node_name, host_ip, host_port) in deployed_addresses:
            polls_url = "http://%s:%d/polls/" % (host_ip,
                                                 host_port)
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
